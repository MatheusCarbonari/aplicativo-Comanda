import re
import sqlite3
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from django.conf import settings
from django.core.management import call_command
from django.core.management.base import BaseCommand, CommandError

from restaurante.infraestrutura.logging_estruturado import (
    registrar_evento,
    registrar_excecao,
)


PADRAO_BACKUP_VALIDO = re.compile(
    r"restaurante-(?P<timestamp>\d{8}T\d{12}Z)"
    r"(?:-(?P<sufixo>\d+))?\.sqlite3"
)
QUANTIDADE_BACKUPS_MANTIDOS = 7


class Command(BaseCommand):
    help = "Executa o backup SQLite seguro e aplica a retenção diária."

    def handle(self, *args, **options):
        execucao_id = uuid4().hex
        diretorio = Path(settings.DIRETORIO_BACKUPS)
        try:
            diretorio.mkdir(parents=True, exist_ok=True)
            conexao_bloqueio = sqlite3.connect(
                diretorio / ".backup-diario.lock.sqlite3",
                timeout=0,
            )
        except (OSError, sqlite3.Error) as erro:
            registrar_excecao(
                "backup_diario_falhou",
                erro,
                execucao_id=execucao_id,
                etapa="bloqueio",
            )
            raise CommandError(
                "Não foi possível iniciar o backup diário."
            ) from erro
        try:
            try:
                conexao_bloqueio.execute("BEGIN IMMEDIATE")
            except sqlite3.OperationalError as erro:
                if "locked" in str(erro).lower():
                    registrar_evento(
                        "backup_diario_ignorado_concorrencia",
                        execucao_id=execucao_id,
                    )
                    raise CommandError(
                        "Uma execução do backup diário já está em andamento."
                    ) from erro
                registrar_excecao(
                    "backup_diario_falhou",
                    erro,
                    execucao_id=execucao_id,
                    etapa="bloqueio",
                )
                raise CommandError(
                    "Não foi possível iniciar o backup diário."
                ) from erro

            registrar_evento(
                "backup_diario_iniciado",
                execucao_id=execucao_id,
            )
            try:
                call_command(
                    "criar_backup",
                    stdout=self.stdout,
                    stderr=self.stderr,
                )
            except Exception as erro:
                registrar_excecao(
                    "backup_diario_falhou",
                    erro,
                    execucao_id=execucao_id,
                    etapa="backup",
                )
                if isinstance(erro, CommandError):
                    raise
                raise CommandError(
                    "O backup diário falhou durante a criação da cópia."
                ) from erro

            try:
                mantidos, removidos = self._aplicar_retencao(
                    diretorio,
                    execucao_id,
                )
            except OSError as erro:
                registrar_excecao(
                    "backup_diario_falhou",
                    erro,
                    execucao_id=execucao_id,
                    etapa="retencao",
                )
                raise CommandError(
                    "O backup foi criado, mas a retenção diária falhou."
                ) from erro

            registrar_evento(
                "backup_diario_retencao_aplicada",
                execucao_id=execucao_id,
                backups_mantidos=mantidos,
                arquivos_removidos=removidos,
            )
            registrar_evento(
                "backup_diario_concluido",
                execucao_id=execucao_id,
            )
        finally:
            if conexao_bloqueio.in_transaction:
                conexao_bloqueio.rollback()
            conexao_bloqueio.close()

    @staticmethod
    def _aplicar_retencao(
        diretorio: Path,
        execucao_id: str,
    ) -> tuple[int, int]:
        backups_validos = []
        for caminho in diretorio.iterdir():
            correspondencia = PADRAO_BACKUP_VALIDO.fullmatch(caminho.name)
            if not caminho.is_file() or correspondencia is None:
                continue
            try:
                timestamp = datetime.strptime(
                    correspondencia.group("timestamp"),
                    "%Y%m%dT%H%M%S%fZ",
                ).replace(tzinfo=UTC)
            except ValueError:
                continue
            backups_validos.append(
                (
                    timestamp,
                    int(correspondencia.group("sufixo") or 0),
                    caminho.name,
                    caminho,
                )
            )

        backups_validos.sort()
        removidos = 0
        for *_, excedente in backups_validos[:-QUANTIDADE_BACKUPS_MANTIDOS]:
            excedente.unlink()
            removidos += 1
            registrar_evento(
                "backup_diario_excedente_removido",
                execucao_id=execucao_id,
                arquivo_backup=excedente.name,
            )
        return min(len(backups_validos), QUANTIDADE_BACKUPS_MANTIDOS), removidos
