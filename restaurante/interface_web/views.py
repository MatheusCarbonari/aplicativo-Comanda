"""Páginas renderizadas pela interface web."""

from uuid import uuid4
from zoneinfo import ZoneInfo

from django.http import HttpRequest, HttpResponse, HttpResponseForbidden
from django.shortcuts import redirect, render
from django.urls import reverse
from django.views.decorators.http import require_GET, require_POST

from restaurante.aplicacao.cancelar_lancamento import (
    AtendimentoEncerrado,
    DescricaoCancelamentoInvalida,
    LancamentoJaCancelado,
    LancamentoNaoEncontrado,
    MotivoCancelamentoInvalido,
    cancelar_lancamento as executar_cancelamento_lancamento,
)
from restaurante.aplicacao.contencao_persistencia import (
    PersistenciaTemporariamenteIndisponivel,
)
from restaurante.aplicacao.consultar_estado_comanda import (
    EstadoComanda,
    PapelNaoPermitido,
    UsuarioOperacionalInvalido,
    consultar_estado_comanda,
)
from restaurante.aplicacao.idempotencia import (
    ChaveIdempotenciaInvalida,
    ConflitoIdempotencia,
)
from restaurante.aplicacao.registrar_primeiro_lancamento import (
    ComandaNaoEncontrada,
    ProdutoNaoEncontrado,
    registrar_primeiro_lancamento as executar_primeiro_lancamento,
)
from restaurante.aplicacao.registrar_lancamento_adicional import (
    AtendimentoAbertoNaoEncontrado,
    registrar_lancamento_adicional as executar_lancamento_adicional,
)
from restaurante.dominio.lancamentos import (
    QuantidadeInvalida,
    calcular_total_atendimento,
)
from restaurante.persistencia.models import (
    Atendimento,
    CancelamentoLancamento,
    Produto,
    UsuarioOperacional,
)


CHAVE_USUARIO_OPERACIONAL = "usuario_operacional_id"
FUSO_HORARIO_APRESENTACAO = ZoneInfo("America/Sao_Paulo")


def _buscar_usuario(identificador: object) -> UsuarioOperacional | None:
    try:
        chave_primaria = int(identificador)
    except (TypeError, ValueError):
        return None
    return UsuarioOperacional.objects.filter(pk=chave_primaria).first()


def _redirecionar_selecao_invalida(request: HttpRequest) -> HttpResponse:
    request.session.pop(CHAVE_USUARIO_OPERACIONAL, None)
    return redirect(f"{reverse('pagina_inicial')}?selecao_invalida=1")


def _contexto_garcom(
    usuario: UsuarioOperacional,
    erro_lancamento: str | None = None,
) -> dict[str, object]:
    return {
        "usuario": usuario,
        "titulo": "Experiência do Garçom",
        "descricao": "Consulte a Comanda ou registre seu primeiro consumo.",
        "pode_lancar": True,
        "produtos": Produto.objects.order_by("nome"),
        "erro_lancamento": erro_lancamento,
        "chave_idempotencia": str(uuid4()),
    }


def _formatar_centavos_brl(valor: int) -> str:
    reais, centavos = divmod(valor, 100)
    reais_formatados = f"{reais:,}".replace(",", ".")
    return f"R$ {reais_formatados},{centavos:02d}"


def _formatar_horario_local(valor) -> str:
    return valor.astimezone(FUSO_HORARIO_APRESENTACAO).strftime(
        "%d/%m/%Y %H:%M"
    )


def pagina_inicial(request: HttpRequest) -> HttpResponse:
    identificador = request.session.get(CHAVE_USUARIO_OPERACIONAL)
    usuario_selecionado = _buscar_usuario(identificador)
    if identificador is not None and usuario_selecionado is None:
        return _redirecionar_selecao_invalida(request)
    if usuario_selecionado is not None:
        if usuario_selecionado.papel == UsuarioOperacional.Papel.GARCOM:
            return redirect("experiencia_garcom")
        return redirect("experiencia_caixa")

    usuarios = UsuarioOperacional.objects.order_by("nome")
    return render(
        request,
        "interface_web/pagina_inicial.html",
        {
            "usuarios": usuarios,
            "selecao_invalida": request.GET.get("selecao_invalida") == "1",
        },
    )


@require_POST
def selecionar_usuario(request: HttpRequest) -> HttpResponse:
    usuario = _buscar_usuario(request.POST.get("usuario_id"))
    if usuario is None:
        return _redirecionar_selecao_invalida(request)

    request.session[CHAVE_USUARIO_OPERACIONAL] = usuario.pk
    if usuario.papel == UsuarioOperacional.Papel.GARCOM:
        return redirect("experiencia_garcom")
    return redirect("experiencia_caixa")


@require_POST
def trocar_usuario(request: HttpRequest) -> HttpResponse:
    request.session.pop(CHAVE_USUARIO_OPERACIONAL, None)
    return redirect("pagina_inicial")


@require_GET
def consultar_comanda(request: HttpRequest) -> HttpResponse:
    try:
        resultado = consultar_estado_comanda(
            request.session.get(CHAVE_USUARIO_OPERACIONAL),
            request.GET.get("identificador", ""),
        )
    except UsuarioOperacionalInvalido:
        return _redirecionar_selecao_invalida(request)
    except PapelNaoPermitido:
        return HttpResponseForbidden("Usuário operacional sem permissão.")

    mensagens = {
        EstadoComanda.DISPONIVEL: (
            "Comanda disponível — nenhum atendimento aberto"
        ),
        EstadoComanda.EM_ATENDIMENTO: "Em atendimento",
        EstadoComanda.NAO_ENCONTRADA: "Comanda não encontrada",
    }
    usuario_atual = _buscar_usuario(
        request.session.get(CHAVE_USUARIO_OPERACIONAL)
    )
    pode_lancar_adicional = (
        resultado.estado == EstadoComanda.EM_ATENDIMENTO
        and usuario_atual is not None
        and usuario_atual.papel == UsuarioOperacional.Papel.GARCOM
    )
    acoes_cancelamento = []
    historico_cancelamentos = []
    total_formatado = None
    if pode_lancar_adicional:
        atendimento = Atendimento.objects.filter(
            comanda__identificador=resultado.identificador,
            estado=Atendimento.Estado.ABERTO,
        ).first()
        if atendimento is not None:
            lancamentos_validos = list(
                atendimento.lancamentos.validos()
                .select_related("produto", "autor")
                .order_by("horario", "pk")
            )
            acoes_cancelamento = [
                {"lancamento": lancamento, "chave": str(uuid4())}
                for lancamento in lancamentos_validos
            ]
            lancamentos_cancelados = (
                atendimento.lancamentos.filter(cancelamento__isnull=False)
                .select_related("produto", "autor", "cancelamento__autor")
                .order_by("horario", "pk")
            )
            historico_cancelamentos = [
                {
                    "produto": lancamento.produto.nome,
                    "quantidade": lancamento.quantidade,
                    "preco_unitario": _formatar_centavos_brl(
                        lancamento.preco_unitario_centavos
                    ),
                    "autor_lancamento": lancamento.autor.nome,
                    "horario_lancamento": _formatar_horario_local(
                        lancamento.horario
                    ),
                    "autor_cancelamento": lancamento.cancelamento.autor.nome,
                    "horario_cancelamento": _formatar_horario_local(
                        lancamento.cancelamento.horario
                    ),
                    "motivo": lancamento.cancelamento.get_motivo_display(),
                    "descricao": lancamento.cancelamento.descricao,
                }
                for lancamento in lancamentos_cancelados
            ]
            total_formatado = _formatar_centavos_brl(
                calcular_total_atendimento(
                    (
                        lancamento.quantidade,
                        lancamento.preco_unitario_centavos,
                    )
                    for lancamento in lancamentos_validos
                )
            )
    return render(
        request,
        "interface_web/consulta_comanda.html",
        {
            "identificador": resultado.identificador,
            "mensagem": mensagens[resultado.estado],
            "pode_lancar_adicional": pode_lancar_adicional,
            "produtos": Produto.objects.order_by("nome"),
            "chave_idempotencia": str(uuid4()),
            "acoes_cancelamento": acoes_cancelamento,
            "historico_cancelamentos": historico_cancelamentos,
            "motivos_cancelamento": CancelamentoLancamento.Motivo.choices,
            "total_formatado": total_formatado,
        },
    )


@require_POST
def registrar_primeiro_lancamento(request: HttpRequest) -> HttpResponse:
    try:
        resultado = executar_primeiro_lancamento(
            request.session.get(CHAVE_USUARIO_OPERACIONAL),
            request.POST.get("identificador_comanda", ""),
            request.POST.get("produto_id"),
            request.POST.get("quantidade"),
            request.POST.get("chave_idempotencia"),
        )
    except UsuarioOperacionalInvalido:
        return _redirecionar_selecao_invalida(request)
    except PapelNaoPermitido:
        return HttpResponseForbidden("Usuário operacional sem permissão.")
    except ConflitoIdempotencia:
        usuario = _buscar_usuario(
            request.session.get(CHAVE_USUARIO_OPERACIONAL)
        )
        return render(
            request,
            "interface_web/experiencia_usuario.html",
            _contexto_garcom(
                usuario,
                "Esta tentativa já foi usada com dados diferentes",
            ),
            status=409,
        )
    except PersistenciaTemporariamenteIndisponivel:
        usuario = _buscar_usuario(
            request.session.get(CHAVE_USUARIO_OPERACIONAL)
        )
        return render(
            request,
            "interface_web/experiencia_usuario.html",
            _contexto_garcom(
                usuario,
                "Banco ocupado temporariamente. Tente novamente",
            ),
            status=503,
        )
    except (
        ComandaNaoEncontrada,
        ProdutoNaoEncontrado,
        QuantidadeInvalida,
        ChaveIdempotenciaInvalida,
    ) as erro:
        mensagens = {
            ComandaNaoEncontrada: "Comanda não encontrada",
            ProdutoNaoEncontrado: "Produto não encontrado",
            QuantidadeInvalida: "Informe uma quantidade inteira positiva",
            ChaveIdempotenciaInvalida: (
                "Não foi possível identificar esta tentativa"
            ),
        }
        usuario = _buscar_usuario(
            request.session.get(CHAVE_USUARIO_OPERACIONAL)
        )
        return render(
            request,
            "interface_web/experiencia_usuario.html",
            _contexto_garcom(usuario, mensagens[type(erro)]),
            status=400,
        )

    total_centavos = (
        resultado.quantidade * resultado.preco_unitario_centavos
    )
    return render(
        request,
        "interface_web/lancamento_registrado.html",
        {
            "resultado": resultado,
            "total_formatado": _formatar_centavos_brl(total_centavos),
        },
    )


@require_POST
def registrar_lancamento_adicional(request: HttpRequest) -> HttpResponse:
    try:
        resultado = executar_lancamento_adicional(
            request.session.get(CHAVE_USUARIO_OPERACIONAL),
            request.POST.get("identificador_comanda", ""),
            request.POST.get("produto_id"),
            request.POST.get("quantidade"),
            request.POST.get("chave_idempotencia"),
        )
    except UsuarioOperacionalInvalido:
        return _redirecionar_selecao_invalida(request)
    except PapelNaoPermitido:
        return HttpResponseForbidden("Usuário operacional sem permissão.")
    except ConflitoIdempotencia:
        usuario = _buscar_usuario(
            request.session.get(CHAVE_USUARIO_OPERACIONAL)
        )
        return render(
            request,
            "interface_web/experiencia_usuario.html",
            _contexto_garcom(
                usuario,
                "Esta tentativa já foi usada com dados diferentes",
            ),
            status=409,
        )
    except (
        ComandaNaoEncontrada,
        ProdutoNaoEncontrado,
        QuantidadeInvalida,
        AtendimentoAbertoNaoEncontrado,
        ChaveIdempotenciaInvalida,
    ) as erro:
        mensagens = {
            ComandaNaoEncontrada: "Comanda não encontrada",
            ProdutoNaoEncontrado: "Produto não encontrado",
            QuantidadeInvalida: "Informe uma quantidade inteira positiva",
            AtendimentoAbertoNaoEncontrado: (
                "Nenhum atendimento aberto para esta Comanda"
            ),
            ChaveIdempotenciaInvalida: (
                "Não foi possível identificar esta tentativa"
            ),
        }
        usuario = _buscar_usuario(
            request.session.get(CHAVE_USUARIO_OPERACIONAL)
        )
        return render(
            request,
            "interface_web/experiencia_usuario.html",
            _contexto_garcom(usuario, mensagens[type(erro)]),
            status=400,
        )

    return render(
        request,
        "interface_web/lancamento_registrado.html",
        {
            "resultado": resultado,
            "total_formatado": _formatar_centavos_brl(
                resultado.total_centavos
            ),
        },
    )


@require_POST
def cancelar_lancamento(request: HttpRequest) -> HttpResponse:
    try:
        resultado = executar_cancelamento_lancamento(
            request.session.get(CHAVE_USUARIO_OPERACIONAL),
            request.POST.get("lancamento_id"),
            request.POST.get("motivo"),
            request.POST.get("descricao"),
            request.POST.get("chave_idempotencia"),
        )
    except UsuarioOperacionalInvalido:
        return _redirecionar_selecao_invalida(request)
    except PapelNaoPermitido:
        return HttpResponseForbidden("Usuário operacional sem permissão.")
    except PersistenciaTemporariamenteIndisponivel:
        usuario = _buscar_usuario(
            request.session.get(CHAVE_USUARIO_OPERACIONAL)
        )
        return render(
            request,
            "interface_web/experiencia_usuario.html",
            _contexto_garcom(
                usuario,
                "Banco ocupado temporariamente. Tente novamente",
            ),
            status=503,
        )
    except (ConflitoIdempotencia, LancamentoJaCancelado) as erro:
        mensagem = (
            "Esta tentativa já foi usada com dados diferentes"
            if isinstance(erro, ConflitoIdempotencia)
            else "Lançamento já cancelado"
        )
        usuario = _buscar_usuario(
            request.session.get(CHAVE_USUARIO_OPERACIONAL)
        )
        return render(
            request,
            "interface_web/experiencia_usuario.html",
            _contexto_garcom(usuario, mensagem),
            status=409,
        )
    except LancamentoNaoEncontrado:
        usuario = _buscar_usuario(
            request.session.get(CHAVE_USUARIO_OPERACIONAL)
        )
        return render(
            request,
            "interface_web/experiencia_usuario.html",
            _contexto_garcom(usuario, "Lançamento não encontrado"),
            status=404,
        )
    except (
        AtendimentoEncerrado,
        MotivoCancelamentoInvalido,
        DescricaoCancelamentoInvalida,
        ChaveIdempotenciaInvalida,
    ) as erro:
        mensagens = {
            AtendimentoEncerrado: "Atendimento encerrado",
            MotivoCancelamentoInvalido: "Selecione um motivo válido",
            DescricaoCancelamentoInvalida: (
                "Informe uma descrição quando o motivo for Outro"
            ),
            ChaveIdempotenciaInvalida: (
                "Não foi possível identificar esta tentativa"
            ),
        }
        usuario = _buscar_usuario(
            request.session.get(CHAVE_USUARIO_OPERACIONAL)
        )
        return render(
            request,
            "interface_web/experiencia_usuario.html",
            _contexto_garcom(usuario, mensagens[type(erro)]),
            status=400,
        )

    return render(
        request,
        "interface_web/lancamento_cancelado.html",
        {
            "resultado": resultado,
            "total_formatado": _formatar_centavos_brl(
                resultado.total_centavos
            ),
        },
    )


def experiencia_garcom(request: HttpRequest) -> HttpResponse:
    usuario = _buscar_usuario(request.session.get(CHAVE_USUARIO_OPERACIONAL))
    if usuario is None:
        return _redirecionar_selecao_invalida(request)
    if usuario.papel != UsuarioOperacional.Papel.GARCOM:
        return redirect("experiencia_caixa")

    return render(
        request,
        "interface_web/experiencia_usuario.html",
        _contexto_garcom(usuario),
    )


def experiencia_caixa(request: HttpRequest) -> HttpResponse:
    usuario = _buscar_usuario(request.session.get(CHAVE_USUARIO_OPERACIONAL))
    if usuario is None:
        return _redirecionar_selecao_invalida(request)
    if usuario.papel != UsuarioOperacional.Papel.CAIXA:
        return redirect("experiencia_garcom")

    return render(
        request,
        "interface_web/experiencia_usuario.html",
        {
            "usuario": usuario,
            "titulo": "Experiência do Caixa",
            "descricao": "A consulta de comandas será adicionada nos próximos tickets.",
        },
    )
