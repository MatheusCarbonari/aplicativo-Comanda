import sqlite3

from django.db import IntegrityError, OperationalError

from restaurante.persistencia.models import (
    Atendimento,
    CancelamentoLancamento,
)


def e_conflito_de_abertura(erro: IntegrityError) -> bool:
    coluna_comanda = Atendimento._meta.get_field("comanda").column
    return _e_conflito_unicidade(
        erro,
        Atendimento._meta.db_table,
        coluna_comanda,
    )


def e_contencao_transitoria(erro: OperationalError) -> bool:
    causa = erro.__cause__
    codigo = getattr(causa, "sqlite_errorcode", None)
    if isinstance(codigo, int) and (codigo & 0xFF) in (
        sqlite3.SQLITE_BUSY,
        sqlite3.SQLITE_LOCKED,
    ):
        return True
    mensagem = str(erro).lower()
    return (
        "database is locked" in mensagem
        or "database table is locked" in mensagem
    )


def e_conflito_de_cancelamento(erro: IntegrityError) -> bool:
    coluna_lancamento = CancelamentoLancamento._meta.get_field(
        "lancamento"
    ).column
    return _e_conflito_unicidade(
        erro,
        CancelamentoLancamento._meta.db_table,
        coluna_lancamento,
    )


def _e_conflito_unicidade(
    erro: IntegrityError,
    tabela: str,
    coluna: str,
) -> bool:
    causa = erro.__cause__
    mensagem_esperada = f"UNIQUE constraint failed: {tabela}.{coluna}"
    return (
        isinstance(causa, sqlite3.IntegrityError)
        and getattr(causa, "sqlite_errorcode", None)
        == sqlite3.SQLITE_CONSTRAINT_UNIQUE
        and str(causa) == mensagem_esperada
    )
