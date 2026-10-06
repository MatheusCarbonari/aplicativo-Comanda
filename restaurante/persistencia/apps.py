from django.apps import AppConfig
from django.db.backends.signals import connection_created


class PersistenciaConfig(AppConfig):
    name = "restaurante.persistencia"
    verbose_name = "Persistência"

    def ready(self) -> None:
        from . import verificacoes  # noqa: F401
        from .sqlite_duravel import verificar_conexao_sqlite

        connection_created.connect(
            verificar_conexao_sqlite,
            dispatch_uid="restaurante.persistencia.sqlite_duravel",
        )
