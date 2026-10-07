"""Rotas públicas da interface web."""

from django.urls import path

from .views import (
    experiencia_caixa,
    experiencia_garcom,
    pagina_inicial,
    selecionar_usuario,
    trocar_usuario,
)


urlpatterns = [
    path("", pagina_inicial, name="pagina_inicial"),
    path("usuarios/selecionar/", selecionar_usuario, name="selecionar_usuario"),
    path("usuarios/trocar/", trocar_usuario, name="trocar_usuario"),
    path("garcom/", experiencia_garcom, name="experiencia_garcom"),
    path("caixa/", experiencia_caixa, name="experiencia_caixa"),
]
