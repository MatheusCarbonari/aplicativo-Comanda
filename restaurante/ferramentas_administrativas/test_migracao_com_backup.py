import logging
import shutil
import sqlite3
from contextlib import closing
from io import StringIO
from unittest.mock import patch
from uuid import uuid4

from django.conf import settings
from django.core.management import call_command, CommandError
from django.db import connection
from django.test import TransactionTestCase, override_settings


class ColetorDeLogs(logging.Handler):
    def __init__(self):
        super().__init__()
        self.registros = []

    def emit(self, record):
        self.registros.append(record)


class HandlerFalho(logging.Handler):
    def emit(self, record):
        raise OSError("falha sentinela do logging")


class MigrarComBackupTests(TransactionTestCase):
    def setUp(self):
        self.diretorio_backup = (
            settings.DIRETORIO_TESTES / f"pre-migracao-{uuid4().hex}"
        )
        self.diretorio_backup.mkdir()
        self.addCleanup(shutil.rmtree, self.diretorio_backup)

    def coletar_logs(self):
        coletor = ColetorDeLogs()
        logger = logging.getLogger("restaurante")
        logger.addHandler(coletor)
        self.addCleanup(logger.removeHandler, coletor)
        return coletor

    def test_backup_validado_e_publicado_antes_da_migration(self):
        coletor = self.coletar_logs()
        call_command(
            "migrate",
            "persistencia",
            "0007",
            interactive=False,
            verbosity=0,
        )
        self.addCleanup(
            call_command,
            "migrate",
            "persistencia",
            "0008",
            interactive=False,
            verbosity=0,
        )

        saida = StringIO()
        with override_settings(DIRETORIO_BACKUPS=self.diretorio_backup):
            call_command(
                "migrar_com_backup",
                "persistencia",
                "0008",
                stdout=saida,
                stderr=StringIO(),
                interactive=False,
                verbosity=0,
            )

        backups = list(
            self.diretorio_backup.glob(
                "restaurante-pre-migracao-*.sqlite3"
            )
        )
        self.assertEqual(len(backups), 1)
        with closing(sqlite3.connect(backups[0])) as copia:
            self.assertEqual(
                copia.execute("PRAGMA integrity_check").fetchone(),
                ("ok",),
            )
            colunas_no_backup = {
                linha[1]
                for linha in copia.execute(
                    "PRAGMA table_info(persistencia_atendimento)"
                ).fetchall()
            }
        with connection.cursor() as cursor:
            cursor.execute("PRAGMA table_info(persistencia_atendimento)")
            colunas_apos_migration = {linha[1] for linha in cursor.fetchall()}
        self.assertNotIn("aberto_em", colunas_no_backup)
        self.assertIn("aberto_em", colunas_apos_migration)
        self.assertIn(
            "Backup pré-migração confirmado e migrations concluídas.",
            saida.getvalue(),
        )
        eventos = [registro.evento for registro in coletor.registros]
        self.assertEqual(
            eventos,
            [
                "migracao_com_backup_iniciada",
                "backup_pre_migracao_iniciado",
                "backup_sqlite_iniciado",
                "backup_sqlite_concluido",
                "backup_pre_migracao_confirmado",
                "migracao_iniciada",
                "migracao_concluida",
            ],
        )
        self.assertLess(
            eventos.index("backup_sqlite_concluido"),
            eventos.index("backup_pre_migracao_confirmado"),
        )
        self.assertLess(
            eventos.index("backup_pre_migracao_confirmado"),
            eventos.index("migracao_iniciada"),
        )
        self.assertLess(
            eventos.index("migracao_iniciada"),
            eventos.index("migracao_concluida"),
        )

    def test_falha_no_backup_impede_inicio_da_migration(self):
        with override_settings(DIRETORIO_BACKUPS=self.diretorio_backup):
            call_command(
                "criar_backup",
                finalidade="pre-migracao",
                stdout=StringIO(),
            )
        backup_anterior = next(
            self.diretorio_backup.glob(
                "restaurante-pre-migracao-*.sqlite3"
            )
        )
        coletor = self.coletar_logs()
        tabelas_antes = set(connection.introspection.table_names())
        destino_fechado = sqlite3.connect(":memory:")
        destino_fechado.close()
        conectar_real = sqlite3.connect

        def falhar_apenas_no_destino(caminho, *args, **kwargs):
            if str(caminho).endswith(".incompleto"):
                return destino_fechado
            return conectar_real(caminho, *args, **kwargs)

        with (
            override_settings(DIRETORIO_BACKUPS=self.diretorio_backup),
            patch(
                "restaurante.ferramentas_administrativas.management.commands."
                "criar_backup.sqlite3.connect",
                side_effect=falhar_apenas_no_destino,
            ),
            patch(
                "django.core.management.commands.migrate.Command.handle",
                side_effect=AssertionError("migrate não deveria iniciar"),
            ) as executar_migrate,
            self.assertRaisesMessage(
                CommandError,
                "Falha no backup pré-migração; nenhuma migration foi iniciada.",
            ),
        ):
            call_command(
                "migrar_com_backup",
                stdout=StringIO(),
                stderr=StringIO(),
                interactive=False,
                verbosity=0,
            )

        executar_migrate.assert_not_called()
        self.assertEqual(
            set(connection.introspection.table_names()),
            tabelas_antes,
        )
        self.assertEqual(
            list(self.diretorio_backup.glob("*.sqlite3")),
            [backup_anterior],
        )
        with closing(sqlite3.connect(backup_anterior)) as copia:
            self.assertEqual(
                copia.execute("PRAGMA integrity_check").fetchone(),
                ("ok",),
            )
        eventos = [registro.evento for registro in coletor.registros]
        self.assertEqual(
            eventos,
            [
                "migracao_com_backup_iniciada",
                "backup_pre_migracao_iniciado",
                "backup_sqlite_iniciado",
                "backup_sqlite_falhou",
                "backup_pre_migracao_falhou",
            ],
        )

    def test_falha_na_migration_preserva_backup_validado(self):
        coletor = self.coletar_logs()

        with (
            override_settings(DIRETORIO_BACKUPS=self.diretorio_backup),
            self.assertRaisesMessage(
                CommandError,
                "O backup pré-migração foi confirmado, mas a migration falhou.",
            ) as erro_reportado,
        ):
            call_command(
                "migrar_com_backup",
                "aplicacao_inexistente",
                stdout=StringIO(),
                stderr=StringIO(),
                interactive=False,
                verbosity=0,
            )

        self.assertIsInstance(erro_reportado.exception.__cause__, CommandError)
        backups = list(
            self.diretorio_backup.glob(
                "restaurante-pre-migracao-*.sqlite3"
            )
        )
        self.assertEqual(len(backups), 1)
        with closing(sqlite3.connect(backups[0])) as copia:
            self.assertEqual(
                copia.execute("PRAGMA integrity_check").fetchone(),
                ("ok",),
            )
        eventos = [registro.evento for registro in coletor.registros]
        self.assertEqual(
            eventos,
            [
                "migracao_com_backup_iniciada",
                "backup_pre_migracao_iniciado",
                "backup_sqlite_iniciado",
                "backup_sqlite_concluido",
                "backup_pre_migracao_confirmado",
                "migracao_iniciada",
                "migracao_falhou",
            ],
        )
        self.assertLess(
            eventos.index("backup_pre_migracao_confirmado"),
            eventos.index("migracao_iniciada"),
        )
        self.assertLess(
            eventos.index("migracao_iniciada"),
            eventos.index("migracao_falhou"),
        )
        self.assertNotIn("migracao_concluida", eventos)

    def test_retencao_diaria_ignora_backup_pre_migracao_e_incompleto(self):
        with override_settings(DIRETORIO_BACKUPS=self.diretorio_backup):
            call_command(
                "migrar_com_backup",
                stdout=StringIO(),
                stderr=StringIO(),
                interactive=False,
                verbosity=0,
            )
            backup_pre_migracao = next(
                self.diretorio_backup.glob(
                    "restaurante-pre-migracao-*.sqlite3"
                )
            )
            incompleto = self.diretorio_backup / (
                ".restaurante-pre-migracao-"
                "20261022T030000000000Z-teste.incompleto"
            )
            incompleto.write_text("incompleto", encoding="utf-8")
            for dia in range(1, 9):
                caminho = self.diretorio_backup / (
                    f"restaurante-202601{dia:02d}T030000000000Z.sqlite3"
                )
                caminho.write_bytes(f"diario-{dia}".encode("ascii"))

            call_command("executar_backup_diario", stdout=StringIO())

        self.assertTrue(backup_pre_migracao.exists())
        self.assertTrue(incompleto.exists())
        self.assertEqual(
            len(
                list(
                    self.diretorio_backup.glob(
                        "restaurante-????????T????????????Z*.sqlite3"
                    )
                )
            ),
            7,
        )

    def test_falha_do_logging_nao_altera_sucesso_do_procedimento(self):
        logger = logging.getLogger("restaurante")

        with (
            override_settings(DIRETORIO_BACKUPS=self.diretorio_backup),
            patch.object(logger, "handlers", [HandlerFalho()]),
            patch.object(logger, "propagate", False),
        ):
            call_command(
                "migrar_com_backup",
                stdout=StringIO(),
                stderr=StringIO(),
                interactive=False,
                verbosity=0,
            )

        backup = next(
            self.diretorio_backup.glob(
                "restaurante-pre-migracao-*.sqlite3"
            )
        )
        with closing(sqlite3.connect(backup)) as copia:
            self.assertEqual(
                copia.execute("PRAGMA integrity_check").fetchone(),
                ("ok",),
            )

    def test_falha_do_logging_nao_mascara_falha_da_migration(self):
        logger = logging.getLogger("restaurante")

        with (
            override_settings(DIRETORIO_BACKUPS=self.diretorio_backup),
            patch.object(logger, "handlers", [HandlerFalho()]),
            patch.object(logger, "propagate", False),
            self.assertRaisesMessage(
                CommandError,
                "O backup pré-migração foi confirmado, mas a migration falhou.",
            ) as erro_reportado,
        ):
            call_command(
                "migrar_com_backup",
                "aplicacao_inexistente",
                stdout=StringIO(),
                stderr=StringIO(),
                interactive=False,
                verbosity=0,
            )

        self.assertIsInstance(erro_reportado.exception.__cause__, CommandError)
        self.assertEqual(
            len(
                list(
                    self.diretorio_backup.glob(
                        "restaurante-pre-migracao-*.sqlite3"
                    )
                )
            ),
            1,
        )
