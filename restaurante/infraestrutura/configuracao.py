"""Configuração inicial da aplicação Django."""

import os
import sys
from pathlib import Path

from django.core.exceptions import ImproperlyConfigured


BASE_DIR = Path(__file__).resolve().parents[2]
DIRETORIO_DADOS = BASE_DIR / ".local" / "dados"
DIRETORIO_TESTES = BASE_DIR / ".local" / "testes"
DIRETORIO_LOGS = BASE_DIR / ".local" / "logs"
DIRETORIO_BACKUPS = BASE_DIR / ".local" / "backups"
CAMINHO_BANCO = DIRETORIO_DADOS / "restaurante.sqlite3"
CAMINHO_BANCO_TESTES = DIRETORIO_TESTES / "restaurante-testes.sqlite3"
CAMINHO_LOG_APLICACAO = DIRETORIO_LOGS / "restaurante.jsonl"
CAMINHO_LOG_TESTES = (
    DIRETORIO_TESTES / f"restaurante-testes-{os.getpid()}.jsonl"
)
EM_EXECUCAO_TESTES = len(sys.argv) > 1 and sys.argv[1] == "test"

try:
    DIRETORIO_DADOS.mkdir(parents=True, exist_ok=True)
    DIRETORIO_TESTES.mkdir(parents=True, exist_ok=True)
    DIRETORIO_LOGS.mkdir(parents=True, exist_ok=True)
except OSError as erro:
    raise ImproperlyConfigured(
        f"Não foi possível preparar os diretórios persistentes: {erro}"
    ) from erro

SECRET_KEY = os.environ.get(
    "DJANGO_SECRET_KEY",
    "chave-exclusiva-para-desenvolvimento-local",
)
DEBUG = os.environ.get("DJANGO_DEBUG", "1") == "1"
ALLOWED_HOSTS = ["localhost", "127.0.0.1", "[::1]", "testserver"]

INSTALLED_APPS = [
    "restaurante.infraestrutura.apps.InfraestruturaConfig",
    "django.contrib.sessions",
    "django.contrib.staticfiles",
    "restaurante.persistencia.apps.PersistenciaConfig",
    "restaurante.ferramentas_administrativas.apps.FerramentasAdministrativasConfig",
    "restaurante.interface_web",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "restaurante.infraestrutura.middleware.RegistrarFalhasMiddleware",
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
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "json": {
            "()": "restaurante.infraestrutura.logging_estruturado.FormatadorJSON",
        },
    },
    "handlers": {
        "arquivo_estruturado": {
            "class": "logging.handlers.RotatingFileHandler",
            "filename": (
                CAMINHO_LOG_TESTES
                if EM_EXECUCAO_TESTES
                else CAMINHO_LOG_APLICACAO
            ),
            "encoding": "utf-8",
            "delay": True,
            "formatter": "json",
            "level": "INFO",
            "maxBytes": 5 * 1024 * 1024,
            "backupCount": 5,
        },
    },
    "loggers": {
        "restaurante": {
            "handlers": ["arquivo_estruturado"],
            "level": "INFO",
            "propagate": False,
        },
    },
}
