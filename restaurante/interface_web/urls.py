"""Rotas públicas da interface web."""

from django.urls import path

from .views import (
    consultar_comanda,
    experiencia_caixa,
    experiencia_garcom,
    pagina_inicial,
    registrar_primeiro_lancamento,
    selecionar_usuario,
    trocar_usuario,
)


urlpatterns = [
    path("", pagina_inicial, name="pagina_inicial"),
    path("usuarios/selecionar/", selecionar_usuario, name="selecionar_usuario"),
    path("usuarios/trocar/", trocar_usuario, name="trocar_usuario"),
    path("comandas/consultar/", consultar_comanda, name="consultar_comanda"),
    path(
        "lancamentos/primeiro/",
        registrar_primeiro_lancamento,
        name="registrar_primeiro_lancamento",
    ),
    path("garcom/", experiencia_garcom, name="experiencia_garcom"),
    path("caixa/", experiencia_caixa, name="experiencia_caixa"),
]
