"""Configuração inicial da aplicação Django."""

import os
from pathlib import Path

from django.core.exceptions import ImproperlyConfigured


BASE_DIR = Path(__file__).resolve().parents[2]
DIRETORIO_DADOS = BASE_DIR / ".local" / "dados"
DIRETORIO_TESTES = BASE_DIR / ".local" / "testes"
CAMINHO_BANCO = DIRETORIO_DADOS / "restaurante.sqlite3"
CAMINHO_BANCO_TESTES = DIRETORIO_TESTES / "restaurante-testes.sqlite3"

try:
    DIRETORIO_DADOS.mkdir(parents=True, exist_ok=True)
    DIRETORIO_TESTES.mkdir(parents=True, exist_ok=True)
except OSError as erro:
    raise ImproperlyConfigured(
        f"Não foi possível preparar o diretório persistente do SQLite: {erro}"
    ) from erro

SECRET_KEY = os.environ.get(
    "DJANGO_SECRET_KEY",
    "chave-exclusiva-para-desenvolvimento-local",
)
DEBUG = os.environ.get("DJANGO_DEBUG", "1") == "1"
ALLOWED_HOSTS = ["localhost", "127.0.0.1", "[::1]", "testserver"]

INSTALLED_APPS = [
    "django.contrib.staticfiles",
    "restaurante.persistencia.apps.PersistenciaConfig",
    "restaurante.interface_web",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.middleware.common.CommonMiddleware",
]

ROOT_URLCONF = "restaurante.infraestrutura.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {"context_processors": []},
    }
]

WSGI_APPLICATION = "restaurante.infraestrutura.wsgi.application"
ASGI_APPLICATION = "restaurante.infraestrutura.asgi.application"

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": CAMINHO_BANCO,
        "OPTIONS": {
            "init_command": "PRAGMA journal_mode=WAL; PRAGMA synchronous=FULL",
        },
        "TEST": {
            "NAME": CAMINHO_BANCO_TESTES,
        },
    }
}

LANGUAGE_CODE = "pt-br"
TIME_ZONE = "America/Sao_Paulo"
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"
