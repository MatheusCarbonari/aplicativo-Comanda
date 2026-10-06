from pathlib import Path
from typing import Any

from django.core.exceptions import ImproperlyConfigured
from django.db.backends.base.base import BaseDatabaseWrapper


JOURNAL_MODE_ESPERADO = "wal"
SYNCHRONOUS_ESPERADO = 2


def observar_pragmas(conexao: BaseDatabaseWrapper) -> dict[str, Any]:
    with conexao.cursor() as cursor:
        cursor.execute("PRAGMA journal_mode")
        journal_mode = str(cursor.fetchone()[0]).lower()
        cursor.execute("PRAGMA synchronous")
        synchronous = int(cursor.fetchone()[0])

    return {
        "journal_mode": journal_mode,
        "synchronous": synchronous,
    }


def validar_pragmas(
    *,
    journal_mode: str,
    synchronous: int,
    caminho_banco: str | Path,
) -> None:
    if (
        journal_mode.lower() == JOURNAL_MODE_ESPERADO
        and synchronous == SYNCHRONOUS_ESPERADO
    ):
        return

    raise ImproperlyConfigured(
        "A conexão SQLite não oferece a durabilidade exigida: "
        f"journal_mode={journal_mode}, synchronous={synchronous}, "
        f"banco={caminho_banco}. Esperado: journal_mode=WAL e "
        "synchronous=FULL (2)."
    )


def verificar_conexao_sqlite(
    sender: type[BaseDatabaseWrapper],
    connection: BaseDatabaseWrapper,
    **kwargs: Any,
) -> None:
    if connection.vendor != "sqlite":
        return

    pragmas = observar_pragmas(connection)
    validar_pragmas(
        journal_mode=pragmas["journal_mode"],
        synchronous=pragmas["synchronous"],
        caminho_banco=connection.settings_dict["NAME"],
    )
