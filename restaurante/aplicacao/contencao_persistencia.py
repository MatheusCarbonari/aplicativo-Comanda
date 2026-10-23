from collections.abc import Callable
from contextlib import contextmanager
from contextvars import ContextVar
from typing import TypeVar

from django.db import OperationalError

from restaurante.persistencia.conflitos_sqlite import e_contencao_transitoria


Resultado = TypeVar("Resultado")
MAXIMO_TENTATIVAS_CONTENCAO = 2
_observador_contencao: ContextVar[Callable[[OperationalError], None] | None] = (
    ContextVar("observador_contencao", default=None)
)


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
            observador = _observador_contencao.get()
            if observador is not None:
                observador(erro)
            if tentativa + 1 == MAXIMO_TENTATIVAS_CONTENCAO:
                raise PersistenciaTemporariamenteIndisponivel from erro
    raise AssertionError("Limite de tentativas inalcançável")


@contextmanager
def observar_contencoes(observador: Callable[[OperationalError], None]):
    token = _observador_contencao.set(observador)
    try:
        yield
    finally:
        _observador_contencao.reset(token)
