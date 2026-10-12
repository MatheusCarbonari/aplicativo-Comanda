"""Rotas HTTP da aplicação."""

from django.urls import include, path

from .saude import verificar_saude


urlpatterns = [
    path("saude/", verificar_saude, name="saude_backend"),
    path("", include("restaurante.interface_web.urls")),
]
