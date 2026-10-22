import os
import shutil
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
    help = "Restaura explicitamente um backup SQLite com a aplicação parada."

    def add_arguments(self, parser):
        parser.add_argument(
            "--arquivo",
            required=True,
            help="Caminho do backup SQLite escolhido explicitamente.",
        )
        parser.add_argument(
            "--confirmar-aplicacao-parada",
            action="store_true",
            help="Confirma que a aplicação foi retirada de serviço.",
        )

    def handle(self, *args, **options):
        if not options["confirmar_aplicacao_parada"]:
            raise CommandError(
                "Confirme que a aplicação está parada com "
                "--confirmar-aplicacao-parada."
            )
        if connection.vendor != "sqlite":
            raise CommandError("O comando restaurar_backup requer um banco SQLite.")

        arquivo_backup = Path(options["arquivo"]).resolve()
        banco_operacional = Path(connection.settings_dict["NAME"]).resolve()
        if arquivo_backup.suffix == ".incompleto":
            raise CommandError(
                "O backup escolhido é inválido: arquivos .incompleto não "
                "podem ser restaurados."
            )
        if arquivo_backup == banco_operacional:
            raise CommandError(
                "Escolha um backup diferente do banco operacional atual."
            )
        restauracao_id = uuid4().hex
        registrar_evento(
            "restauracao_backup_iniciada",
            restauracao_id=restauracao_id,
            arquivo_backup=arquivo_backup.name,
        )
        try:
            self._validar_integridade(arquivo_backup)
        except (OSError, sqlite3.Error, CommandError) as erro:
            registrar_excecao(
                "restauracao_backup_falhou",
                erro,
                restauracao_id=restauracao_id,
                etapa="validacao_backup",
                arquivo_backup=arquivo_backup.name,
            )
            if isinstance(erro, CommandError):
                raise CommandError(str(erro)) from erro
            raise CommandError(
                "O backup escolhido é inválido ou está corrompido."
            ) from erro

        registrar_evento(
            "backup_restauracao_validado",
            restauracao_id=restauracao_id,
            arquivo_backup=arquivo_backup.name,
        )

        temporario_restauracao: Path | None = None
        try:
            banco_operacional.parent.mkdir(parents=True, exist_ok=True)
            with NamedTemporaryFile(
                dir=banco_operacional.parent,
                prefix=".restauracao-",
                suffix=".incompleto",
                delete=False,
            ) as arquivo_temporario:
                temporario_restauracao = Path(arquivo_temporario.name)
            shutil.copyfile(arquivo_backup, temporario_restauracao)
            self._validar_integridade(temporario_restauracao)
        except (OSError, sqlite3.Error, CommandError) as erro:
            self._limpar_temporario(temporario_restauracao)
            self._registrar_falha(
                erro,
                restauracao_id,
                "preparacao_substituicao",
                arquivo_backup.name,
            )
            raise CommandError(
                "Falha ao preparar o backup escolhido para restauração."
            ) from erro

        try:
            connection.close()
            arquivos_wal = [
                Path(f"{banco_operacional}-wal"),
                Path(f"{banco_operacional}-shm"),
            ]
            if any(caminho.exists() for caminho in arquivos_wal):
                raise CommandError(
                    "A condição de acesso ao banco é insegura: existem "
                    "arquivos WAL/SHM ativos."
                )
        except (OSError, sqlite3.Error, CommandError) as erro:
            self._limpar_temporario(temporario_restauracao)
            self._registrar_falha(
                erro,
                restauracao_id,
                "condicao_segura",
                arquivo_backup.name,
            )
            raise CommandError(
                "A aplicação ainda está ativa ou o banco está em "
                "condição insegura para restauração."
            ) from erro

        try:
            preservado = self._preservar_banco_operacional(banco_operacional)
        except (OSError, sqlite3.Error, CommandError) as erro:
            self._limpar_temporario(temporario_restauracao)
            self._registrar_falha(
                erro,
                restauracao_id,
                "preservacao_banco_operacional",
                arquivo_backup.name,
            )
            raise CommandError(
                "Falha ao preservar o banco operacional atual; a restauração "
                "não foi iniciada."
            ) from erro

        registrar_evento(
            "banco_operacional_preservado",
            restauracao_id=restauracao_id,
            arquivo_backup=arquivo_backup.name,
            banco_anterior=preservado.name,
        )

        try:
            os.replace(temporario_restauracao, banco_operacional)
            temporario_restauracao = None
        except OSError as erro:
            self._registrar_falha(
                erro,
                restauracao_id,
                "substituicao",
                arquivo_backup.name,
                banco_anterior=preservado.name,
            )
            raise CommandError(
                "Falha durante a substituição do banco operacional. O banco "
                "anterior permanece disponível."
            ) from erro
        finally:
            if temporario_restauracao is not None:
                try:
                    temporario_restauracao.unlink(missing_ok=True)
                except OSError:
                    pass

        registrar_evento(
            "backup_restauracao_publicado",
            restauracao_id=restauracao_id,
            arquivo_backup=arquivo_backup.name,
            banco_anterior=preservado.name,
        )

        try:
            self._validar_integridade(banco_operacional)
        except (OSError, sqlite3.Error, CommandError) as erro:
            banco_anterior_restaurado = False
            try:
                os.replace(preservado, banco_operacional)
                banco_anterior_restaurado = True
            except OSError:
                pass
            self._registrar_falha(
                erro,
                restauracao_id,
                "integridade_pos_restauracao",
                arquivo_backup.name,
                banco_anterior=preservado.name,
                banco_anterior_restaurado=banco_anterior_restaurado,
            )
            if banco_anterior_restaurado:
                raise CommandError(
                    "Falha na integridade pós-restauração; o banco anterior "
                    "foi restaurado com segurança."
                ) from erro
            raise CommandError(
                "Falha na integridade pós-restauração. O banco anterior "
                f"permanece recuperável em {preservado}."
            ) from erro

        registrar_evento(
            "integridade_pos_restauracao_confirmada",
            restauracao_id=restauracao_id,
            arquivo_backup=arquivo_backup.name,
            banco_anterior=preservado.name,
        )
        registrar_evento(
            "restauracao_backup_concluida",
            restauracao_id=restauracao_id,
            arquivo_backup=arquivo_backup.name,
            banco_anterior=preservado.name,
        )
        self.stdout.write(
            self.style.SUCCESS(
                "Restauração concluída e integridade confirmada. "
                "Reinicie a aplicação antes de liberar novas operações."
            )
        )

    @staticmethod
    def _validar_integridade(caminho: Path) -> None:
        if not caminho.is_file():
            raise CommandError("O arquivo de backup escolhido não existe.")
        uri_somente_leitura = f"{caminho.as_uri()}?mode=ro"
        with closing(sqlite3.connect(uri_somente_leitura, uri=True)) as banco:
            resultado = banco.execute("PRAGMA integrity_check").fetchone()
        if resultado != ("ok",):
            raise CommandError(
                "O backup escolhido falhou na verificação de integridade."
            )

    def _preservar_banco_operacional(self, banco_operacional: Path) -> Path:
        if not banco_operacional.is_file():
            raise CommandError("O banco operacional atual não existe.")
        diretorio_backup = Path(settings.DIRETORIO_BACKUPS)
        diretorio_backup.mkdir(parents=True, exist_ok=True)
        identificador = datetime.now(UTC).strftime("%Y%m%dT%H%M%S%fZ")
        temporario: Path | None = None
        try:
            with NamedTemporaryFile(
                dir=diretorio_backup,
                prefix=".restaurante-antes-restauracao-",
                suffix=".incompleto",
                delete=False,
            ) as arquivo_temporario:
                temporario = Path(arquivo_temporario.name)
            shutil.copyfile(banco_operacional, temporario)
            self._validar_integridade(temporario)
            sufixo = 0
            while True:
                complemento = "" if sufixo == 0 else f"-{sufixo}"
                preservado = diretorio_backup / (
                    "restaurante-antes-restauracao-"
                    f"{identificador}{complemento}.sqlite3"
                )
                try:
                    os.link(temporario, preservado)
                except FileExistsError:
                    sufixo += 1
                    continue
                temporario.unlink()
                temporario = None
                return preservado
        finally:
            if temporario is not None:
                try:
                    temporario.unlink(missing_ok=True)
                except OSError:
                    pass

    @staticmethod
    def _registrar_falha(
        erro,
        restauracao_id,
        etapa,
        arquivo_backup,
        **contexto,
    ):
        registrar_excecao(
            "restauracao_backup_falhou",
            erro,
            restauracao_id=restauracao_id,
            etapa=etapa,
            arquivo_backup=arquivo_backup,
            **contexto,
        )

    @staticmethod
    def _limpar_temporario(caminho):
        if caminho is None:
            return
        try:
            caminho.unlink(missing_ok=True)
        except OSError:
            pass
