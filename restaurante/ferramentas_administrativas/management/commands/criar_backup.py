import os
import sqlite3
from contextlib import closing
from datetime import UTC, datetime
from pathlib import Path
from tempfile import NamedTemporaryFile
from uuid import uuid4

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import connection

from restaurante.infraestrutura.logging_estruturado import (
    registrar_evento,
    registrar_excecao,
)


class Command(BaseCommand):
    help = "Cria e valida um snapshot seguro do banco SQLite em uso."

    def add_arguments(self, parser):
        parser.add_argument(
            "--finalidade",
            choices=("rotina", "pre-migracao"),
            default="rotina",
            help="Define a identificação técnica do backup publicado.",
        )

    def handle(self, *args, **options):
        if connection.vendor != "sqlite":
            raise CommandError("O comando criar_backup requer um banco SQLite.")

        backup_id = uuid4().hex
        registrar_evento(
            "backup_sqlite_iniciado",
            backup_id=backup_id,
        )
        diretorio = Path(settings.DIRETORIO_BACKUPS)
        try:
            diretorio.mkdir(parents=True, exist_ok=True)
        except OSError as erro:
            registrar_excecao(
                "backup_sqlite_falhou",
                erro,
                backup_id=backup_id,
            )
            raise CommandError(
                "Não foi possível preparar o diretório de backups."
            ) from erro

        identificador = datetime.now(UTC).strftime("%Y%m%dT%H%M%S%fZ")
        prefixo = "restaurante"
        if options["finalidade"] == "pre-migracao":
            prefixo = "restaurante-pre-migracao"
        temporario: Path | None = None
        try:
            with NamedTemporaryFile(
                dir=diretorio,
                prefix=f".{prefixo}-{identificador}-",
                suffix=".incompleto",
                delete=False,
            ) as arquivo_temporario:
                temporario = Path(arquivo_temporario.name)

            connection.ensure_connection()
            with closing(sqlite3.connect(temporario)) as destino:
                connection.connection.backup(destino)

            with closing(sqlite3.connect(temporario)) as copia:
                resultado = copia.execute("PRAGMA integrity_check").fetchone()
            if resultado != ("ok",):
                raise CommandError(
                    "A cópia do banco falhou na verificação de integridade."
                )

            caminho_backup = self._publicar_sem_sobrescrever(
                temporario,
                diretorio,
                identificador,
                prefixo,
            )
            temporario = None
        except CommandError as erro:
            registrar_excecao(
                "backup_sqlite_falhou",
                erro,
                backup_id=backup_id,
            )
            raise
        except (OSError, sqlite3.Error) as erro:
            registrar_excecao(
                "backup_sqlite_falhou",
                erro,
                backup_id=backup_id,
            )
            raise CommandError(
                "Não foi possível criar um backup SQLite válido."
            ) from erro
        finally:
            if temporario is not None:
                try:
                    temporario.unlink(missing_ok=True)
                except OSError:
                    pass

        registrar_evento(
            "backup_sqlite_concluido",
            backup_id=backup_id,
            arquivo_backup=caminho_backup.name,
        )
        self.stdout.write(
            self.style.SUCCESS(f"Backup criado com sucesso: {caminho_backup}")
        )

    @staticmethod
    def _publicar_sem_sobrescrever(
        temporario: Path,
        diretorio: Path,
        identificador: str,
        prefixo: str,
    ) -> Path:
        sufixo = 0
        while True:
            complemento = "" if sufixo == 0 else f"-{sufixo}"
            destino = diretorio / (
                f"{prefixo}-{identificador}{complemento}.sqlite3"
            )
            try:
                os.link(temporario, destino)
            except FileExistsError:
                sufixo += 1
                continue
            try:
                temporario.unlink()
            except OSError:
                pass
            return destino
