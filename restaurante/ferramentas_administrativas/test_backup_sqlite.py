import logging
import sqlite3
import shutil
from contextlib import closing
from datetime import UTC, datetime
from io import StringIO
from uuid import uuid4
from unittest.mock import MagicMock, patch

from django.conf import settings
from django.core.management import call_command, CommandError
from django.db import connection
from django.test import TransactionTestCase, override_settings

from restaurante.persistencia.models import ComandaFisica


class ColetorDeLogs(logging.Handler):
    def __init__(self):
        super().__init__()
        self.registros = []

    def emit(self, record):
        self.registros.append(record)


class HandlerFalho(logging.Handler):
    def emit(self, record):
        raise OSError("falha sentinela do logging")


class CriarBackupTests(TransactionTestCase):
    def setUp(self):
        self.diretorio_backup = (
            settings.DIRETORIO_TESTES / f"backup-{uuid4().hex}"
        )
        self.diretorio_backup.mkdir()
        self.addCleanup(shutil.rmtree, self.diretorio_backup)

    def coletar_logs(self):
        coletor = ColetorDeLogs()
        logger = logging.getLogger("restaurante")
        logger.addHandler(coletor)
        self.addCleanup(logger.removeHandler, coletor)
        return coletor

    def test_configuracao_define_diretorio_persistente_separado(self):
        self.assertEqual(
            settings.DIRETORIO_BACKUPS,
            settings.BASE_DIR / ".local" / "backups",
        )
        self.assertNotEqual(
            settings.DIRETORIO_BACKUPS,
            settings.DIRETORIO_DADOS,
        )

    def test_cria_snapshot_integro_com_dados_enquanto_banco_esta_aberto(self):
        ComandaFisica.objects.create(identificador="BACKUP-ESPERADO")
        connection.ensure_connection()
        conexao_operacional = connection.connection
        with connection.cursor() as cursor:
            cursor.execute("PRAGMA journal_mode")
            self.assertEqual(cursor.fetchone(), ("wal",))

        saida = StringIO()
        with override_settings(DIRETORIO_BACKUPS=self.diretorio_backup):
            call_command("criar_backup", stdout=saida)

            backups = list(self.diretorio_backup.glob("*.sqlite3"))
            self.assertEqual(len(backups), 1)
            self.assertEqual(
                set(self.diretorio_backup.iterdir()),
                set(backups),
            )
            self.assertRegex(
                backups[0].name,
                r"^restaurante-\d{8}T\d{12}Z\.sqlite3$",
            )
            with closing(sqlite3.connect(backups[0])) as copia:
                integridade = copia.execute("PRAGMA integrity_check").fetchone()
                identificadores = copia.execute(
                    'SELECT identificador FROM "persistencia_comandafisica"'
                ).fetchall()

            self.assertEqual(integridade, ("ok",))
            self.assertIn(("BACKUP-ESPERADO",), identificadores)
            self.assertIs(connection.connection, conexao_operacional)
            self.assertTrue(
                ComandaFisica.objects.filter(
                    identificador="BACKUP-ESPERADO"
                ).exists()
            )
            self.assertIn(str(backups[0]), saida.getvalue())

    def test_registra_inicio_e_sucesso_somente_com_backup_valido_publicado(self):
        coletor = self.coletar_logs()

        with override_settings(DIRETORIO_BACKUPS=self.diretorio_backup):
            call_command("criar_backup", stdout=StringIO())

        eventos = [registro.evento for registro in coletor.registros]
        self.assertEqual(
            eventos,
            ["backup_sqlite_iniciado", "backup_sqlite_concluido"],
        )
        registro_inicio, registro_sucesso = coletor.registros
        backup = next(self.diretorio_backup.glob("*.sqlite3"))
        with closing(sqlite3.connect(backup)) as copia:
            self.assertEqual(
                copia.execute("PRAGMA integrity_check").fetchone(),
                ("ok",),
            )
        self.assertEqual(
            registro_inicio.contexto_tecnico["backup_id"],
            registro_sucesso.contexto_tecnico["backup_id"],
        )
        self.assertEqual(
            set(registro_inicio.contexto_tecnico),
            {"backup_id"},
        )
        self.assertEqual(
            set(registro_sucesso.contexto_tecnico),
            {"backup_id", "arquivo_backup"},
        )
        self.assertEqual(
            registro_sucesso.contexto_tecnico["arquivo_backup"],
            backup.name,
        )

    def test_falha_do_logging_nao_altera_backup_bem_sucedido(self):
        logger = logging.getLogger("restaurante")
        saida = StringIO()

        with (
            override_settings(DIRETORIO_BACKUPS=self.diretorio_backup),
            patch.object(logger, "handlers", [HandlerFalho()]),
            patch.object(logger, "propagate", False),
        ):
            call_command("criar_backup", stdout=saida)

        backups = list(self.diretorio_backup.glob("*.sqlite3"))
        self.assertEqual(len(backups), 1)
        self.assertEqual(
            list(self.diretorio_backup.glob("*.incompleto")),
            [],
        )
        with closing(sqlite3.connect(backups[0])) as copia:
            self.assertEqual(
                copia.execute("PRAGMA integrity_check").fetchone(),
                ("ok",),
            )
        self.assertIn("Backup criado com sucesso", saida.getvalue())

    def test_falha_do_logging_nao_mascara_falha_do_backup(self):
        ComandaFisica.objects.create(identificador="ORIGEM-COM-LOG-FALHO")
        destino_fechado = sqlite3.connect(":memory:")
        destino_fechado.close()
        logger = logging.getLogger("restaurante")

        with (
            override_settings(DIRETORIO_BACKUPS=self.diretorio_backup),
            patch.object(logger, "handlers", [HandlerFalho()]),
            patch.object(logger, "propagate", False),
            patch(
                "restaurante.ferramentas_administrativas.management.commands."
                "criar_backup.sqlite3.connect",
                return_value=destino_fechado,
            ),
            self.assertRaises(CommandError) as erro_reportado,
        ):
            call_command("criar_backup", stdout=StringIO())

        self.assertEqual(
            str(erro_reportado.exception),
            "Não foi possível criar um backup SQLite válido.",
        )
        self.assertIsInstance(
            erro_reportado.exception.__cause__,
            sqlite3.ProgrammingError,
        )
        self.assertEqual(list(self.diretorio_backup.iterdir()), [])
        self.assertTrue(
            ComandaFisica.objects.filter(
                identificador="ORIGEM-COM-LOG-FALHO"
            ).exists()
        )

    def test_falha_durante_backup_preserva_origem_remove_parcial_e_nao_loga_sucesso(self):
        ComandaFisica.objects.create(identificador="ORIGEM-INTOCADA")
        coletor = self.coletar_logs()
        destino_fechado = sqlite3.connect(":memory:")
        destino_fechado.close()

        with (
            override_settings(DIRETORIO_BACKUPS=self.diretorio_backup),
            patch(
                "restaurante.ferramentas_administrativas.management.commands."
                "criar_backup.sqlite3.connect",
                return_value=destino_fechado,
            ),
            self.assertRaisesMessage(
                CommandError,
                "Não foi possível criar um backup SQLite válido.",
            ),
        ):
            call_command("criar_backup", stdout=StringIO())

        self.assertTrue(
            ComandaFisica.objects.filter(identificador="ORIGEM-INTOCADA").exists()
        )
        with connection.cursor() as cursor:
            cursor.execute("PRAGMA integrity_check")
            self.assertEqual(cursor.fetchone(), ("ok",))
        self.assertEqual(list(self.diretorio_backup.iterdir()), [])
        eventos = [registro.evento for registro in coletor.registros]
        self.assertEqual(
            eventos,
            ["backup_sqlite_iniciado", "backup_sqlite_falhou"],
        )
        self.assertEqual(
            coletor.registros[-1].contexto_tecnico["error_type"],
            "ProgrammingError",
        )
        self.assertEqual(
            set(coletor.registros[-1].contexto_tecnico),
            {"backup_id", "error_type"},
        )

    def test_falha_na_limpeza_nao_mascara_erro_do_backup(self):
        ComandaFisica.objects.create(identificador="ORIGEM-APOS-CLEANUP")
        destino_fechado = sqlite3.connect(":memory:")
        destino_fechado.close()

        with (
            override_settings(DIRETORIO_BACKUPS=self.diretorio_backup),
            patch(
                "restaurante.ferramentas_administrativas.management.commands."
                "criar_backup.sqlite3.connect",
                return_value=destino_fechado,
            ),
            patch(
                "restaurante.ferramentas_administrativas.management.commands."
                "criar_backup.Path.unlink",
                side_effect=PermissionError("falha secundária de cleanup"),
            ),
            self.assertRaises(CommandError) as erro_reportado,
        ):
            call_command("criar_backup", stdout=StringIO())

        self.assertEqual(
            str(erro_reportado.exception),
            "Não foi possível criar um backup SQLite válido.",
        )
        self.assertIsInstance(
            erro_reportado.exception.__cause__,
            sqlite3.ProgrammingError,
        )
        self.assertTrue(
            ComandaFisica.objects.filter(
                identificador="ORIGEM-APOS-CLEANUP"
            ).exists()
        )
        self.assertEqual(list(self.diretorio_backup.glob("*.sqlite3")), [])
        self.assertEqual(
            len(list(self.diretorio_backup.glob("*.incompleto"))),
            1,
        )

    def test_integridade_invalida_nao_publica_nem_registra_sucesso(self):
        coletor = self.coletar_logs()
        conectar_real = sqlite3.connect
        chamadas = 0

        def conectar_com_integridade_invalida(caminho):
            nonlocal chamadas
            chamadas += 1
            if chamadas == 1:
                return conectar_real(caminho)
            conexao = MagicMock()
            conexao.execute.return_value.fetchone.return_value = (
                "integridade inválida",
            )
            return conexao

        with (
            override_settings(DIRETORIO_BACKUPS=self.diretorio_backup),
            patch(
                "restaurante.ferramentas_administrativas.management.commands."
                "criar_backup.sqlite3.connect",
                side_effect=conectar_com_integridade_invalida,
            ),
            self.assertRaisesMessage(
                CommandError,
                "A cópia do banco falhou na verificação de integridade.",
            ),
        ):
            call_command("criar_backup", stdout=StringIO())

        self.assertEqual(list(self.diretorio_backup.iterdir()), [])
        self.assertEqual(
            [registro.evento for registro in coletor.registros],
            ["backup_sqlite_iniciado", "backup_sqlite_falhou"],
        )

    def test_colisao_temporal_cria_nome_distinto_sem_sobrescrever(self):
        instante = datetime(2026, 10, 21, 17, 30, 45, 123456, tzinfo=UTC)
        ComandaFisica.objects.create(identificador="PRIMEIRO-SNAPSHOT")

        with (
            override_settings(DIRETORIO_BACKUPS=self.diretorio_backup),
            patch(
                "restaurante.ferramentas_administrativas.management.commands."
                "criar_backup.datetime"
            ) as relogio,
        ):
            relogio.now.return_value = instante
            call_command("criar_backup", stdout=StringIO())
            primeiro = self.diretorio_backup / (
                "restaurante-20261021T173045123456Z.sqlite3"
            )
            conteudo_original = primeiro.read_bytes()

            ComandaFisica.objects.create(identificador="SEGUNDO-SNAPSHOT")
            call_command("criar_backup", stdout=StringIO())

        segundo = self.diretorio_backup / (
            "restaurante-20261021T173045123456Z-1.sqlite3"
        )
        self.assertTrue(primeiro.exists())
        self.assertTrue(segundo.exists())
        self.assertEqual(primeiro.read_bytes(), conteudo_original)
        with closing(sqlite3.connect(primeiro)) as copia_inicial:
            primeiro_tem_segundo = copia_inicial.execute(
                'SELECT 1 FROM "persistencia_comandafisica" '
                "WHERE identificador = ?",
                ("SEGUNDO-SNAPSHOT",),
            ).fetchone()
        with closing(sqlite3.connect(segundo)) as copia_posterior:
            segundo_tem_segundo = copia_posterior.execute(
                'SELECT 1 FROM "persistencia_comandafisica" '
                "WHERE identificador = ?",
                ("SEGUNDO-SNAPSHOT",),
            ).fetchone()
        self.assertIsNone(primeiro_tem_segundo)
        self.assertEqual(segundo_tem_segundo, (1,))

    def test_cria_diretorio_persistente_quando_necessario(self):
        destino = self.diretorio_backup / "backups" / "restaurante"

        with override_settings(DIRETORIO_BACKUPS=destino):
            call_command("criar_backup", stdout=StringIO())

        self.assertTrue(destino.is_dir())
        self.assertEqual(len(list(destino.glob("*.sqlite3"))), 1)

    def test_destino_indisponivel_preserva_origem_e_registra_falha(self):
        ComandaFisica.objects.create(identificador="ORIGEM-PRESERVADA")
        destino_indisponivel = self.diretorio_backup / "nao-e-diretorio"
        destino_indisponivel.write_text("sentinela", encoding="utf-8")
        coletor = self.coletar_logs()

        with (
            override_settings(DIRETORIO_BACKUPS=destino_indisponivel),
            self.assertRaisesMessage(
                CommandError,
                "Não foi possível preparar o diretório de backups.",
            ),
        ):
            call_command("criar_backup", stdout=StringIO())

        self.assertEqual(
            destino_indisponivel.read_text(encoding="utf-8"),
            "sentinela",
        )
        self.assertTrue(
            ComandaFisica.objects.filter(
                identificador="ORIGEM-PRESERVADA"
            ).exists()
        )
        self.assertEqual(
            [registro.evento for registro in coletor.registros],
            ["backup_sqlite_iniciado", "backup_sqlite_falhou"],
        )

    def test_falha_ao_reabrir_copia_remove_parcial_e_registra_falha(self):
        conectar_real = sqlite3.connect
        chamadas = 0
        coletor = self.coletar_logs()

        def conectar_com_falha_na_reabertura(caminho):
            nonlocal chamadas
            chamadas += 1
            if chamadas == 1:
                return conectar_real(caminho)
            raise sqlite3.OperationalError("falha sentinela de abertura")

        with (
            override_settings(DIRETORIO_BACKUPS=self.diretorio_backup),
            patch(
                "restaurante.ferramentas_administrativas.management.commands."
                "criar_backup.sqlite3.connect",
                side_effect=conectar_com_falha_na_reabertura,
            ),
            self.assertRaisesMessage(
                CommandError,
                "Não foi possível criar um backup SQLite válido.",
            ),
        ):
            call_command("criar_backup", stdout=StringIO())

        self.assertEqual(list(self.diretorio_backup.iterdir()), [])
        self.assertEqual(
            [registro.evento for registro in coletor.registros],
            ["backup_sqlite_iniciado", "backup_sqlite_falhou"],
        )
