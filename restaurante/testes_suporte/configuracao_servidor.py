"""Configuração isolada para verificar o processo HTTP real."""

import os
from pathlib import Path

from restaurante.infraestrutura.configuracao import *  # noqa: F403


CAMINHO_BANCO_TESTE_SERVIDOR = Path(os.environ["RESTAURANTE_TESTE_BANCO"])
CAMINHO_LOG_TESTE_SERVIDOR = Path(os.environ["RESTAURANTE_TESTE_LOG"])

DATABASES["default"]["NAME"] = CAMINHO_BANCO_TESTE_SERVIDOR  # noqa: F405
DATABASES["default"]["TEST"] = {  # noqa: F405
    "NAME": CAMINHO_BANCO_TESTE_SERVIDOR.with_name("test.sqlite3"),
}
LOGGING["handlers"]["arquivo_estruturado"]["filename"] = (  # noqa: F405
    CAMINHO_LOG_TESTE_SERVIDOR
)
