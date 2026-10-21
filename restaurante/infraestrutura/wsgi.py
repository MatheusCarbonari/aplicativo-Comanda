"""Ponto de entrada WSGI."""

import os

from django.core.wsgi import get_wsgi_application


os.environ.setdefault(
    "DJANGO_SETTINGS_MODULE",
    "restaurante.infraestrutura.configuracao",
)
os.environ["RESTAURANTE_PROCESSO_OPERACIONAL"] = "1"

application = get_wsgi_application()
