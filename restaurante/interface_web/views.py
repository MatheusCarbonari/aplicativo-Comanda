"""Páginas renderizadas pela interface web."""

from uuid import uuid4

from django.http import HttpRequest, HttpResponse, HttpResponseForbidden
from django.shortcuts import redirect, render
from django.urls import reverse
from django.views.decorators.http import require_GET, require_POST

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
    ComandaEmAtendimento,
    ComandaNaoEncontrada,
    ProdutoNaoEncontrado,
    registrar_primeiro_lancamento as executar_primeiro_lancamento,
)
from restaurante.aplicacao.registrar_lancamento_adicional import (
    AtendimentoAbertoNaoEncontrado,
    registrar_lancamento_adicional as executar_lancamento_adicional,
)
from restaurante.dominio.lancamentos import QuantidadeInvalida
from restaurante.persistencia.models import Produto, UsuarioOperacional


CHAVE_USUARIO_OPERACIONAL = "usuario_operacional_id"


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
    return render(
        request,
        "interface_web/consulta_comanda.html",
        {
            "identificador": resultado.identificador,
            "mensagem": mensagens[resultado.estado],
            "pode_lancar_adicional": (
                resultado.estado == EstadoComanda.EM_ATENDIMENTO
                and usuario_atual is not None
                and usuario_atual.papel
                == UsuarioOperacional.Papel.GARCOM
            ),
            "produtos": Produto.objects.order_by("nome"),
            "chave_idempotencia": str(uuid4()),
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
    except (
        ComandaNaoEncontrada,
        ProdutoNaoEncontrado,
        QuantidadeInvalida,
        ComandaEmAtendimento,
        ChaveIdempotenciaInvalida,
    ) as erro:
        mensagens = {
            ComandaNaoEncontrada: "Comanda não encontrada",
            ProdutoNaoEncontrado: "Produto não encontrado",
            QuantidadeInvalida: "Informe uma quantidade inteira positiva",
            ComandaEmAtendimento: "Comanda já está em atendimento",
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
