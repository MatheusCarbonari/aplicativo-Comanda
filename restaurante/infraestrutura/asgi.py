"""Ponto de entrada ASGI."""

import os

from django.core.asgi import get_asgi_application


os.environ.setdefault(
    "DJANGO_SETTINGS_MODULE",
    "restaurante.infraestrutura.configuracao",
)

application = get_asgi_application()
