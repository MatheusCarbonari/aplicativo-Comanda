from collections.abc import Callable
from typing import TypeVar

from django.db import OperationalError

from restaurante.persistencia.conflitos_sqlite import e_contencao_transitoria


Resultado = TypeVar("Resultado")
MAXIMO_TENTATIVAS_CONTENCAO = 2


class PersistenciaTemporariamenteIndisponivel(Exception):
    pass


def executar_com_retry_de_contencao(
    executar: Callable[[], Resultado],
) -> Resultado:
    for tentativa in range(MAXIMO_TENTATIVAS_CONTENCAO):
        try:
            return executar()
        except OperationalError as erro:
            if not e_contencao_transitoria(erro):
                raise
            if tentativa + 1 == MAXIMO_TENTATIVAS_CONTENCAO:
                raise PersistenciaTemporariamenteIndisponivel from erro
    raise AssertionError("Limite de tentativas inalcançável")
