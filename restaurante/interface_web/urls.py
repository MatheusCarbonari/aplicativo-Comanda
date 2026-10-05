"""Rotas públicas da interface web."""

from django.urls import path

from .views import pagina_inicial


urlpatterns = [
    path("", pagina_inicial, name="pagina_inicial"),
]
