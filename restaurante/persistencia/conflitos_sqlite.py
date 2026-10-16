import sqlite3

from django.db import IntegrityError, OperationalError

from restaurante.persistencia.models import Atendimento


def e_conflito_de_abertura(erro: IntegrityError) -> bool:
    causa = erro.__cause__
    coluna_comanda = Atendimento._meta.get_field("comanda").column
    mensagem_esperada = (
        "UNIQUE constraint failed: "
        f"{Atendimento._meta.db_table}.{coluna_comanda}"
    )
    return (
        isinstance(causa, sqlite3.IntegrityError)
        and getattr(causa, "sqlite_errorcode", None)
        == sqlite3.SQLITE_CONSTRAINT_UNIQUE
        and str(causa) == mensagem_esperada
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
