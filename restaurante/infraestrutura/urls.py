"""Rotas HTTP da aplicação."""

from django.urls import include, path


urlpatterns = [
    path("", include("restaurante.interface_web.urls")),
]
