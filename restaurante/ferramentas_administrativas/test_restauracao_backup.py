import logging
import os
import shutil
import sqlite3
from contextlib import closing, contextmanager
from io import StringIO
from pathlib import Path
from unittest.mock import patch
from uuid import uuid4

from django.conf import settings
from django.core.management import call_command, CommandError
from django.db import connection
from django.test import SimpleTestCase, override_settings
from django.urls import Resolver404, resolve


class ColetorDeLogs(logging.Handler):
    def __init__(self):
        super().__init__()
        self.registros = []

    def emit(self, record):
        self.registros.append(record)


class HandlerFalho(logging.Handler):
    def emit(self, record):
        raise OSError("falha sentinela do logging")


class RestaurarBackupTests(SimpleTestCase):
    databases = {"default"}

    def setUp(self):
        self.diretorio = (
            settings.DIRETORIO_TESTES / f"restauracao-{uuid4().hex}"
        )
        self.diretorio.mkdir()
        self.addCleanup(shutil.rmtree, self.diretorio)
        self.banco_operacional = self.diretorio / "restaurante.sqlite3"
        self.backup = self.diretorio / "backup-escolhido.sqlite3"
        self._criar_banco(self.banco_operacional, "estado operacional")
        self._criar_banco(self.backup, "estado do backup")

    @staticmethod
    def _criar_banco(caminho, valor):
        with closing(sqlite3.connect(caminho)) as banco:
            banco.execute("CREATE TABLE estado (valor TEXT NOT NULL)")
            banco.execute("INSERT INTO estado (valor) VALUES (?)", (valor,))
            banco.commit()

    @contextmanager
    def _usar_banco_operacional(self):
        nome_original = connection.settings_dict["NAME"]
        connection.close()
        connection.settings_dict["NAME"] = self.banco_operacional
        try:
            yield
        finally:
            connection.close()
            connection.settings_dict["NAME"] = nome_original

    @staticmethod
    def _ler_estado(caminho):
        with closing(sqlite3.connect(caminho)) as banco:
            integridade = banco.execute("PRAGMA integrity_check").fetchone()
            estado = banco.execute("SELECT valor FROM estado").fetchone()
        return integridade, estado

    def _coletar_logs(self):
        coletor = ColetorDeLogs()
        logger = logging.getLogger("restaurante")
        logger.addHandler(coletor)
        self.addCleanup(logger.removeHandler, coletor)
        return coletor

    def test_sem_confirmacao_recusa_antes_de_modificar_qualquer_arquivo(self):
        conteudo_operacional = self.banco_operacional.read_bytes()
        conteudo_backup = self.backup.read_bytes()

        with (
            self._usar_banco_operacional(),
            override_settings(DIRETORIO_BACKUPS=self.diretorio),
            self.assertRaisesMessage(
                CommandError,
                "Confirme que a aplicação está parada",
            ),
        ):
            call_command(
                "restaurar_backup",
                arquivo=self.backup,
                stdout=StringIO(),
                stderr=StringIO(),
            )

        self.assertEqual(self.banco_operacional.read_bytes(), conteudo_operacional)
        self.assertEqual(self.backup.read_bytes(), conteudo_backup)
        self.assertEqual(
            set(self.diretorio.iterdir()),
            {self.banco_operacional, self.backup},
        )

    def test_backup_corrompido_falha_antes_de_preservar_banco_operacional(self):
        self.backup.write_bytes(b"NAO-E-SQLITE-SENTINELA")
        conteudo_operacional = self.banco_operacional.read_bytes()

        with (
            self._usar_banco_operacional(),
            override_settings(DIRETORIO_BACKUPS=self.diretorio),
            self.assertRaisesMessage(
                CommandError,
                "O backup escolhido é inválido",
            ),
        ):
            call_command(
                "restaurar_backup",
                arquivo=self.backup,
                confirmar_aplicacao_parada=True,
                stdout=StringIO(),
                stderr=StringIO(),
            )

        self.assertEqual(self.banco_operacional.read_bytes(), conteudo_operacional)
        self.assertEqual(
            set(self.diretorio.iterdir()),
            {self.banco_operacional, self.backup},
        )

    def test_backup_inexistente_e_rejeitado_sem_tocar_no_banco(self):
        backup_inexistente = self.diretorio / "backup-inexistente.sqlite3"
        conteudo_operacional = self.banco_operacional.read_bytes()

        with (
            self._usar_banco_operacional(),
            override_settings(DIRETORIO_BACKUPS=self.diretorio),
            self.assertRaisesMessage(
                CommandError,
                "O arquivo de backup escolhido não existe",
            ),
        ):
            call_command(
                "restaurar_backup",
                arquivo=backup_inexistente,
                confirmar_aplicacao_parada=True,
                stdout=StringIO(),
                stderr=StringIO(),
            )

        self.assertEqual(self.banco_operacional.read_bytes(), conteudo_operacional)
        self.assertFalse(backup_inexistente.exists())
        self.assertEqual(
            list(self.diretorio.glob("restaurante-antes-restauracao-*.sqlite3")),
            [],
        )
        self.assertEqual(list(self.diretorio.glob("*.incompleto")), [])

    def test_restaura_backup_preserva_anterior_e_confirma_integridade_na_ordem(self):
        coletor = self._coletar_logs()
        saida = StringIO()

        with (
            self._usar_banco_operacional(),
            override_settings(DIRETORIO_BACKUPS=self.diretorio),
        ):
            call_command(
                "restaurar_backup",
                arquivo=self.backup,
                confirmar_aplicacao_parada=True,
                stdout=saida,
                stderr=StringIO(),
            )
            self.assertIsNone(connection.connection)

        preservados = list(
            self.diretorio.glob("restaurante-antes-restauracao-*.sqlite3")
        )
        self.assertEqual(len(preservados), 1)
        self.assertEqual(
            self._ler_estado(self.banco_operacional),
            (("ok",), ("estado do backup",)),
        )
        self.assertEqual(
            self._ler_estado(preservados[0]),
            (("ok",), ("estado operacional",)),
        )
        self.assertEqual(
            self._ler_estado(self.backup),
            (("ok",), ("estado do backup",)),
        )
        self.assertEqual(list(self.diretorio.glob("*.incompleto")), [])
        self.assertIn("Restauração concluída", saida.getvalue())
        self.assertIn("Reinicie a aplicação", saida.getvalue())

        eventos = [registro.evento for registro in coletor.registros]
        self.assertEqual(
            eventos,
            [
                "restauracao_backup_iniciada",
                "backup_restauracao_validado",
                "banco_operacional_preservado",
                "backup_restauracao_publicado",
                "integridade_pos_restauracao_confirmada",
                "restauracao_backup_concluida",
            ],
        )
        identificadores = {
            registro.contexto_tecnico["restauracao_id"]
            for registro in coletor.registros
        }
        self.assertEqual(len(identificadores), 1)
        representacao_logs = repr(
            [
                (registro.evento, registro.contexto_tecnico)
                for registro in coletor.registros
            ]
        )
        self.assertNotIn("estado operacional", representacao_logs)
        self.assertNotIn("estado do backup", representacao_logs)

    def test_condicao_wal_insegura_recusa_sem_preservar_ou_substituir(self):
        arquivo_wal = Path(f"{self.banco_operacional}-wal")
        arquivo_wal.write_bytes(b"WAL-ATIVO-SENTINELA")
        conteudo_operacional = self.banco_operacional.read_bytes()

        with (
            self._usar_banco_operacional(),
            override_settings(DIRETORIO_BACKUPS=self.diretorio),
            self.assertRaisesMessage(
                CommandError,
                "condição insegura",
            ),
        ):
            call_command(
                "restaurar_backup",
                arquivo=self.backup,
                confirmar_aplicacao_parada=True,
                stdout=StringIO(),
                stderr=StringIO(),
            )

        self.assertEqual(self.banco_operacional.read_bytes(), conteudo_operacional)
        self.assertEqual(arquivo_wal.read_bytes(), b"WAL-ATIVO-SENTINELA")
        self.assertEqual(
            list(self.diretorio.glob("restaurante-antes-restauracao-*.sqlite3")),
            [],
        )
        self.assertEqual(list(self.diretorio.glob("*.incompleto")), [])

    def test_condicao_shm_insegura_recusa_sem_alterar_banco_operacional(self):
        arquivo_shm = Path(f"{self.banco_operacional}-shm")
        arquivo_shm.write_bytes(b"SHM-ATIVO-SENTINELA")
        conteudo_operacional = self.banco_operacional.read_bytes()

        with (
            self._usar_banco_operacional(),
            override_settings(DIRETORIO_BACKUPS=self.diretorio),
            self.assertRaisesMessage(
                CommandError,
                "condição insegura",
            ),
        ):
            call_command(
                "restaurar_backup",
                arquivo=self.backup,
                confirmar_aplicacao_parada=True,
                stdout=StringIO(),
                stderr=StringIO(),
            )

        self.assertEqual(self.banco_operacional.read_bytes(), conteudo_operacional)
        self.assertEqual(arquivo_shm.read_bytes(), b"SHM-ATIVO-SENTINELA")
        self.assertEqual(
            list(self.diretorio.glob("restaurante-antes-restauracao-*.sqlite3")),
            [],
        )
        self.assertEqual(list(self.diretorio.glob("*.incompleto")), [])

    def test_falha_na_publicacao_mantem_banco_anterior_recuperavel(self):
        coletor = self._coletar_logs()
        conteudo_operacional = self.banco_operacional.read_bytes()

        with (
            self._usar_banco_operacional(),
            override_settings(DIRETORIO_BACKUPS=self.diretorio),
            patch(
                "restaurante.ferramentas_administrativas.management.commands."
                "restaurar_backup.os.replace",
                side_effect=PermissionError("falha sentinela na publicação"),
            ),
            self.assertRaisesMessage(
                CommandError,
                "Falha durante a substituição",
            ),
        ):
            call_command(
                "restaurar_backup",
                arquivo=self.backup,
                confirmar_aplicacao_parada=True,
                stdout=StringIO(),
                stderr=StringIO(),
            )

        preservados = list(
            self.diretorio.glob("restaurante-antes-restauracao-*.sqlite3")
        )
        self.assertEqual(len(preservados), 1)
        self.assertEqual(self.banco_operacional.read_bytes(), conteudo_operacional)
        self.assertEqual(
            self._ler_estado(preservados[0]),
            (("ok",), ("estado operacional",)),
        )
        self.assertEqual(list(self.diretorio.glob("*.incompleto")), [])
        eventos = [registro.evento for registro in coletor.registros]
        self.assertEqual(eventos[-1], "restauracao_backup_falhou")
        self.assertEqual(
            coletor.registros[-1].contexto_tecnico["etapa"],
            "substituicao",
        )
        self.assertNotIn("restauracao_backup_concluida", eventos)

    def test_falha_ao_preservar_nao_inicia_substituicao(self):
        coletor = self._coletar_logs()
        destino_indisponivel = self.diretorio / "destino-indisponivel"
        destino_indisponivel.write_text("sentinela", encoding="utf-8")
        conteudo_operacional = self.banco_operacional.read_bytes()

        with (
            self._usar_banco_operacional(),
            override_settings(DIRETORIO_BACKUPS=destino_indisponivel),
            self.assertRaisesMessage(
                CommandError,
                "Falha ao preservar o banco operacional atual",
            ),
        ):
            call_command(
                "restaurar_backup",
                arquivo=self.backup,
                confirmar_aplicacao_parada=True,
                stdout=StringIO(),
                stderr=StringIO(),
            )

        self.assertEqual(self.banco_operacional.read_bytes(), conteudo_operacional)
        self.assertEqual(
            destino_indisponivel.read_text(encoding="utf-8"),
            "sentinela",
        )
        self.assertEqual(list(self.diretorio.glob("*.incompleto")), [])
        self.assertEqual(
            coletor.registros[-1].contexto_tecnico["etapa"],
            "preservacao_banco_operacional",
        )

    def test_integridade_posterior_falha_e_banco_anterior_volta_a_operacao(self):
        coletor = self._coletar_logs()
        substituir_real = os.replace
        publicacoes = 0

        def substituir_e_corromper(origem, destino):
            nonlocal publicacoes
            substituir_real(origem, destino)
            if Path(destino) == self.banco_operacional and publicacoes == 0:
                publicacoes += 1
                self.banco_operacional.write_bytes(b"CORROMPIDO-APOS-PUBLICACAO")

        with (
            self._usar_banco_operacional(),
            override_settings(DIRETORIO_BACKUPS=self.diretorio),
            patch(
                "restaurante.ferramentas_administrativas.management.commands."
                "restaurar_backup.os.replace",
                side_effect=substituir_e_corromper,
            ),
            self.assertRaisesMessage(
                CommandError,
                "banco anterior foi restaurado com segurança",
            ),
        ):
            call_command(
                "restaurar_backup",
                arquivo=self.backup,
                confirmar_aplicacao_parada=True,
                stdout=StringIO(),
                stderr=StringIO(),
            )

        self.assertEqual(
            self._ler_estado(self.banco_operacional),
            (("ok",), ("estado operacional",)),
        )
        self.assertEqual(
            list(self.diretorio.glob("restaurante-antes-restauracao-*.sqlite3")),
            [],
        )
        eventos = [registro.evento for registro in coletor.registros]
        self.assertEqual(eventos[-1], "restauracao_backup_falhou")
        self.assertEqual(
            coletor.registros[-1].contexto_tecnico["etapa"],
            "integridade_pos_restauracao",
        )
        self.assertTrue(
            coletor.registros[-1].contexto_tecnico["banco_anterior_restaurado"]
        )
        self.assertNotIn("restauracao_backup_concluida", eventos)

    def test_falha_na_recuperacao_preserva_causa_e_copia_recuperavel(self):
        coletor = self._coletar_logs()
        substituir_real = os.replace
        substituicoes = 0
        saida = StringIO()

        def publicar_corrompido_e_falhar_recuperacao(origem, destino):
            nonlocal substituicoes
            substituicoes += 1
            if substituicoes == 1:
                substituir_real(origem, destino)
                self.banco_operacional.write_bytes(
                    b"CORROMPIDO-APOS-PUBLICACAO"
                )
                return
            raise PermissionError("falha secundaria sentinela na recuperacao")

        with (
            self._usar_banco_operacional(),
            override_settings(DIRETORIO_BACKUPS=self.diretorio),
            patch(
                "restaurante.ferramentas_administrativas.management.commands."
                "restaurar_backup.os.replace",
                side_effect=publicar_corrompido_e_falhar_recuperacao,
            ),
            self.assertRaises(CommandError) as erro_reportado,
        ):
            call_command(
                "restaurar_backup",
                arquivo=self.backup,
                confirmar_aplicacao_parada=True,
                stdout=saida,
                stderr=StringIO(),
            )

        preservados = list(
            self.diretorio.glob("restaurante-antes-restauracao-*.sqlite3")
        )
        self.assertEqual(len(preservados), 1)
        self.assertIsInstance(
            erro_reportado.exception.__cause__,
            sqlite3.DatabaseError,
        )
        self.assertNotIsInstance(
            erro_reportado.exception.__cause__,
            PermissionError,
        )
        self.assertIn(
            f"permanece recuperável em {preservados[0]}",
            str(erro_reportado.exception),
        )
        self.assertEqual(
            self._ler_estado(preservados[0]),
            (("ok",), ("estado operacional",)),
        )
        self.assertEqual(
            self.banco_operacional.read_bytes(),
            b"CORROMPIDO-APOS-PUBLICACAO",
        )
        eventos = [registro.evento for registro in coletor.registros]
        self.assertEqual(eventos[-1], "restauracao_backup_falhou")
        self.assertEqual(
            coletor.registros[-1].contexto_tecnico["etapa"],
            "integridade_pos_restauracao",
        )
        self.assertFalse(
            coletor.registros[-1].contexto_tecnico["banco_anterior_restaurado"]
        )
        self.assertNotIn("restauracao_backup_concluida", eventos)
        self.assertNotIn("Restauração concluída", saida.getvalue())

    def test_arquivo_incompleto_nao_e_aceito_como_backup(self):
        incompleto = self.diretorio / "restaurante-20261022.incompleto"
        self.backup.replace(incompleto)
        conteudo_operacional = self.banco_operacional.read_bytes()

        with (
            self._usar_banco_operacional(),
            override_settings(DIRETORIO_BACKUPS=self.diretorio),
            self.assertRaisesMessage(CommandError, "backup escolhido é inválido"),
        ):
            call_command(
                "restaurar_backup",
                arquivo=incompleto,
                confirmar_aplicacao_parada=True,
                stdout=StringIO(),
                stderr=StringIO(),
            )

        self.assertEqual(self.banco_operacional.read_bytes(), conteudo_operacional)
        self.assertTrue(incompleto.exists())

    def test_falha_do_logging_nao_altera_restauracao_bem_sucedida(self):
        logger = logging.getLogger("restaurante")

        with (
            self._usar_banco_operacional(),
            override_settings(DIRETORIO_BACKUPS=self.diretorio),
            patch.object(logger, "handlers", [HandlerFalho()]),
            patch.object(logger, "propagate", False),
        ):
            call_command(
                "restaurar_backup",
                arquivo=self.backup,
                confirmar_aplicacao_parada=True,
                stdout=StringIO(),
                stderr=StringIO(),
            )

        self.assertEqual(
            self._ler_estado(self.banco_operacional),
            (("ok",), ("estado do backup",)),
        )
        self.assertEqual(
            len(
                list(
                    self.diretorio.glob(
                        "restaurante-antes-restauracao-*.sqlite3"
                    )
                )
            ),
            1,
        )

    def test_falha_do_logging_nao_mascara_backup_invalido(self):
        self.backup.write_bytes(b"BACKUP-CORROMPIDO-COM-LOG-FALHO")
        conteudo_operacional = self.banco_operacional.read_bytes()
        logger = logging.getLogger("restaurante")

        with (
            self._usar_banco_operacional(),
            override_settings(DIRETORIO_BACKUPS=self.diretorio),
            patch.object(logger, "handlers", [HandlerFalho()]),
            patch.object(logger, "propagate", False),
            self.assertRaisesMessage(
                CommandError,
                "O backup escolhido é inválido",
            ),
        ):
            call_command(
                "restaurar_backup",
                arquivo=self.backup,
                confirmar_aplicacao_parada=True,
                stdout=StringIO(),
                stderr=StringIO(),
            )

        self.assertEqual(self.banco_operacional.read_bytes(), conteudo_operacional)

    def test_interface_web_nao_expoe_restauracao(self):
        with self.assertRaises(Resolver404):
            resolve("/restaurar-backup/")

        resposta = self.client.get("/")
        self.assertEqual(resposta.status_code, 200)
        self.assertNotContains(resposta, "restaurar_backup")
        self.assertNotContains(resposta, "Restaurar backup")
        diretorio_templates = (
            settings.BASE_DIR
            / "restaurante"
            / "interface_web"
            / "templates"
        )
        conteudo_templates = "\n".join(
            caminho.read_text(encoding="utf-8")
            for caminho in diretorio_templates.rglob("*.html")
        ).lower()
        self.assertNotIn("restaurar_backup", conteudo_templates)
        self.assertNotIn("restaurar backup", conteudo_templates)

    def test_documentacao_exige_parada_e_reinicio_da_aplicacao(self):
        leia_me = (settings.BASE_DIR / "README.md").read_text(encoding="utf-8")

        self.assertIn(
            "restaurar_backup --arquivo <caminho-do-backup> "
            "--confirmar-aplicacao-parada",
            leia_me,
        )
        self.assertIn("pare completamente a aplicação", leia_me)
        self.assertIn("reinicie a aplicação", leia_me)
