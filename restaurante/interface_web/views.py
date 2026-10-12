"""Páginas renderizadas pela interface web."""

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
from restaurante.persistencia.models import UsuarioOperacional


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
    return render(
        request,
        "interface_web/consulta_comanda.html",
        {
            "identificador": resultado.identificador,
            "mensagem": mensagens[resultado.estado],
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
        {
            "usuario": usuario,
            "titulo": "Experiência do Garçom",
            "descricao": (
                "As operações de atendimento serão adicionadas nos próximos tickets."
            ),
        },
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
