from django.core.checks import Error, Tags, register
from django.core.exceptions import ImproperlyConfigured
from django.db import DatabaseError, connections

from .sqlite_duravel import observar_pragmas, validar_pragmas


@register(Tags.database)
def verificar_sqlite_duravel(app_configs, **kwargs):
    conexao = connections["default"]
    if conexao.vendor != "sqlite":
        return []

    try:
        conexao.ensure_connection()
        pragmas = observar_pragmas(conexao)
        validar_pragmas(
            journal_mode=pragmas["journal_mode"],
            synchronous=pragmas["synchronous"],
            caminho_banco=conexao.settings_dict["NAME"],
        )
    except (DatabaseError, ImproperlyConfigured, OSError) as erro:
        return [
            Error(
                f"Não foi possível garantir a durabilidade do SQLite: {erro}",
                id="restaurante.E001",
            )
        ]

    return []
