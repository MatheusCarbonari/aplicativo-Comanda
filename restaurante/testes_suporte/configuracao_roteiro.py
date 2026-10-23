"""Configuração isolada do roteiro integrado de demonstração."""

import os
from pathlib import Path

from restaurante.infraestrutura.configuracao import *  # noqa: F403


CAMINHO_BANCO_ROTEIRO = Path(os.environ["RESTAURANTE_ROTEIRO_BANCO"])
CAMINHO_LOG_ROTEIRO = Path(os.environ["RESTAURANTE_ROTEIRO_LOG"])

DATABASES["default"]["NAME"] = CAMINHO_BANCO_ROTEIRO  # noqa: F405
DATABASES["default"]["TEST"] = {  # noqa: F405
    "NAME": CAMINHO_BANCO_ROTEIRO.with_name("test.sqlite3"),
}
LOGGING["handlers"]["arquivo_estruturado"][  # noqa: F405
    "filename"
] = CAMINHO_LOG_ROTEIRO
