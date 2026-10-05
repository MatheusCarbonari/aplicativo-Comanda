"""Páginas renderizadas pela interface web."""

from django.http import HttpRequest, HttpResponse
from django.shortcuts import render


def pagina_inicial(request: HttpRequest) -> HttpResponse:
    return render(request, "interface_web/pagina_inicial.html")
