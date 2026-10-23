"""Configuracao isolada do processo de validacao de volume."""

import os
from pathlib import Path

from restaurante.infraestrutura.configuracao import *  # noqa: F403


CAMINHO_BANCO_VOLUME = Path(os.environ["RESTAURANTE_VOLUME_BANCO"])
CAMINHO_LOG_VOLUME = Path(os.environ["RESTAURANTE_VOLUME_LOG"])

DATABASES["default"]["NAME"] = CAMINHO_BANCO_VOLUME  # noqa: F405
DATABASES["default"]["TEST"] = {"NAME": CAMINHO_BANCO_VOLUME.with_name("test.sqlite3")}
LOGGING["handlers"]["arquivo_estruturado"][  # noqa: F405
    "filename"
] = CAMINHO_LOG_VOLUME

