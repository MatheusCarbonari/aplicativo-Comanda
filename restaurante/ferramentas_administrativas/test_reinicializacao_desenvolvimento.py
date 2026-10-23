import logging
import sqlite3
import shutil
from contextlib import closing
from datetime import timedelta
from io import StringIO
from unittest.mock import patch
from uuid import uuid4

from django.conf import settings
from django.contrib.sessions.models import Session
from django.core.management import call_command, CommandError
from django.db import connection, transaction
from django.test import TransactionTestCase, override_settings
from django.urls import Resolver404, resolve
from django.utils import timezone

from restaurante.persistencia.models import (
    Atendimento,
    CancelamentoLancamento,
    ComandaFisica,
    Lancamento,
    Produto,
    RegistroIdempotencia,
    UsuarioOperacional,
)


class ColetorDeLogs(logging.Handler):
    def __init__(self):
        super().__init__()
        self.registros = []

    def emit(self, record):
        self.registros.append(record)


class HandlerFalho(logging.Handler):
    def emit(self, record):
        raise OSError("falha sentinela do logging")


class ReinicializarDadosDesenvolvimentoTests(TransactionTestCase):
    def setUp(self):
        self.diretorio_backup = (
            settings.DIRETORIO_TESTES / f"reset-desenvolvimento-{uuid4().hex}"
        )
        self.diretorio_backup.mkdir()
        self.addCleanup(shutil.rmtree, self.diretorio_backup)

    def _coletar_logs(self):
        coletor = ColetorDeLogs()
        logger = logging.getLogger("restaurante")
        logger.addHandler(coletor)
        self.addCleanup(logger.removeHandler, coletor)
        return coletor

    def test_ambiente_sem_debug_recusa_antes_de_prompt_backup_ou_alteracao(self):
        comanda = ComandaFisica.objects.create(identificador="DEV-PRESERVADA")
        coletor = self._coletar_logs()

        with (
            override_settings(
                DEBUG=False,
                DIRETORIO_BACKUPS=self.diretorio_backup,
            ),
            patch("builtins.input") as entrada,
            self.assertRaisesMessage(
                CommandError,
                "exclusivo do ambiente de desenvolvimento",
            ),
        ):
            call_command(
                "reinicializar_dados_desenvolvimento",
                stdout=StringIO(),
                stderr=StringIO(),
            )

        entrada.assert_not_called()
        self.assertTrue(ComandaFisica.objects.filter(pk=comanda.pk).exists())
        self.assertEqual(list(self.diretorio_backup.iterdir()), [])
        self.assertEqual(
            coletor.registros[-1].contexto_tecnico["etapa"],
            "ambiente",
        )

    def test_confirmacao_incorreta_preserva_banco_e_nao_cria_backup(self):
        comanda = ComandaFisica.objects.create(identificador="SEM-CONFIRMACAO")
        saida = StringIO()
        coletor = self._coletar_logs()

        def responder_confirmacao(prompt):
            aviso = saida.getvalue()
            self.assertIn("Atendimentos", aviso)
            self.assertIn("Lançamentos", aviso)
            self.assertIn("Cancelamentos", aviso)
            self.assertIn("registros de idempotência", aviso)
            self.assertIn("sessões", aviso)
            self.assertIn("Comandas", aviso)
            self.assertIn("Produtos", aviso)
            self.assertIn("Usuários operacionais", aviso)
            self.assertIn("Digite REINICIALIZAR", prompt)
            return "reinicializar"

        with (
            override_settings(
                DEBUG=True,
                DIRETORIO_BACKUPS=self.diretorio_backup,
            ),
            patch("builtins.input", side_effect=responder_confirmacao),
            self.assertRaisesMessage(
                CommandError,
                "Confirmação recusada",
            ),
        ):
            call_command(
                "reinicializar_dados_desenvolvimento",
                stdout=saida,
                stderr=StringIO(),
            )

        self.assertTrue(ComandaFisica.objects.filter(pk=comanda.pk).exists())
        self.assertEqual(list(self.diretorio_backup.iterdir()), [])
        self.assertEqual(
            coletor.registros[-1].contexto_tecnico["etapa"],
            "confirmacao",
        )

    def test_falha_no_backup_aborta_antes_de_remover_dados(self):
        comanda = ComandaFisica.objects.create(identificador="BACKUP-FALHOU")
        coletor = self._coletar_logs()
        destino_indisponivel = self.diretorio_backup / "nao-e-diretorio"
        destino_indisponivel.write_text("sentinela", encoding="utf-8")

        with (
            override_settings(
                DEBUG=True,
                DIRETORIO_BACKUPS=destino_indisponivel,
            ),
            patch("builtins.input", return_value="REINICIALIZAR"),
            self.assertRaisesMessage(
                CommandError,
                "Falha no backup obrigatório",
            ),
        ):
            call_command(
                "reinicializar_dados_desenvolvimento",
                stdout=StringIO(),
                stderr=StringIO(),
            )

        self.assertTrue(ComandaFisica.objects.filter(pk=comanda.pk).exists())
        self.assertEqual(
            destino_indisponivel.read_text(encoding="utf-8"),
            "sentinela",
        )
        self.assertEqual(
            coletor.registros[-1].contexto_tecnico["etapa"],
            "backup",
        )
        self.assertNotIn(
            "reinicializacao_limpeza_iniciada",
            [registro.evento for registro in coletor.registros],
        )

    def test_sucesso_preserva_backup_e_recria_exatamente_a_massa_inicial(self):
        call_command("carregar_dados_iniciais", stdout=StringIO())
        comanda = ComandaFisica.objects.get(identificador="001")
        produto = Produto.objects.get(nome="Café")
        usuario = UsuarioOperacional.objects.get(nome="Garçom 1")
        atendimento = Atendimento.objects.create(comanda=comanda)
        lancamento = Lancamento.objects.create(
            atendimento=atendimento,
            produto=produto,
            quantidade=2,
            preco_unitario_centavos=600,
            autor=usuario,
        )
        CancelamentoLancamento.objects.create(
            lancamento=lancamento,
            motivo=CancelamentoLancamento.Motivo.DUPLICADO,
            autor=usuario,
        )
        RegistroIdempotencia.objects.create(
            chave="IDEMPOTENCIA-ANTIGA",
            operacao="OPERACAO-ANTIGA",
            hash_conteudo="a" * 64,
            resultado={"id": 1},
        )
        Session.objects.create(
            session_key="sessao-antiga",
            session_data="dados-antigos",
            expire_date=timezone.now() + timedelta(days=1),
        )
        ComandaFisica.objects.create(identificador="999")
        Produto.objects.create(nome="Produto extra", preco_centavos=1234)
        UsuarioOperacional.objects.create(
            nome="Usuário extra",
            papel=UsuarioOperacional.Papel.CAIXA,
        )

        saida = StringIO()
        with (
            override_settings(
                DEBUG=True,
                DIRETORIO_BACKUPS=self.diretorio_backup,
            ),
            patch("builtins.input", return_value="REINICIALIZAR"),
        ):
            call_command(
                "reinicializar_dados_desenvolvimento",
                stdout=saida,
                stderr=StringIO(),
            )

        backups = list(self.diretorio_backup.glob("restaurante-*.sqlite3"))
        self.assertEqual(len(backups), 1)
        with closing(sqlite3.connect(backups[0])) as copia:
            self.assertEqual(
                copia.execute("PRAGMA integrity_check").fetchone(),
                ("ok",),
            )
            self.assertEqual(
                copia.execute(
                    "SELECT identificador FROM persistencia_comandafisica "
                    "WHERE identificador = '999'"
                ).fetchone(),
                ("999",),
            )
            self.assertEqual(
                copia.execute(
                    "SELECT COUNT(*) FROM persistencia_atendimento"
                ).fetchone(),
                (1,),
            )

        self.assertEqual(
            list(
                ComandaFisica.objects.order_by("identificador").values_list(
                    "identificador",
                    flat=True,
                )
            ),
            [f"{numero:03d}" for numero in range(1, 21)],
        )
        self.assertEqual(Produto.objects.count(), 10)
        self.assertEqual(UsuarioOperacional.objects.count(), 3)
        self.assertFalse(Produto.objects.filter(nome="Produto extra").exists())
        self.assertFalse(
            UsuarioOperacional.objects.filter(nome="Usuário extra").exists()
        )
        self.assertEqual(Atendimento.objects.count(), 0)
        self.assertEqual(Lancamento.objects.count(), 0)
        self.assertEqual(CancelamentoLancamento.objects.count(), 0)
        self.assertEqual(RegistroIdempotencia.objects.count(), 0)
        self.assertEqual(Session.objects.count(), 0)
        self.assertIn("Carga inicial concluída", saida.getvalue())
        self.assertIn("Reinicialização concluída", saida.getvalue())

    def test_falha_real_durante_recriacao_reverte_toda_a_limpeza(self):
        call_command("carregar_dados_iniciais", stdout=StringIO())
        comanda = ComandaFisica.objects.get(identificador="001")
        produto = Produto.objects.get(nome="Café")
        usuario = UsuarioOperacional.objects.get(nome="Garçom 1")
        atendimento = Atendimento.objects.create(comanda=comanda)
        Lancamento.objects.create(
            atendimento=atendimento,
            produto=produto,
            quantidade=1,
            preco_unitario_centavos=600,
            autor=usuario,
        )
        RegistroIdempotencia.objects.create(
            chave="ROLLBACK-IDEMPOTENCIA",
            operacao="ROLLBACK",
            hash_conteudo="b" * 64,
            resultado={"estado": "anterior"},
        )
        Session.objects.create(
            session_key="sessao-rollback",
            session_data="estado-anterior",
            expire_date=timezone.now() + timedelta(days=1),
        )
        ComandaFisica.objects.create(identificador="998")
        estado_anterior = self._capturar_estado()
        saida = StringIO()
        coletor = self._coletar_logs()

        with connection.cursor() as cursor:
            cursor.execute(
                """
                CREATE TRIGGER impedir_decima_comanda
                BEFORE INSERT ON persistencia_comandafisica
                WHEN NEW.identificador = '010'
                BEGIN
                    SELECT RAISE(ABORT, 'falha sentinela na recriacao');
                END
                """
            )
        try:
            with (
                override_settings(
                    DEBUG=True,
                    DIRETORIO_BACKUPS=self.diretorio_backup,
                ),
                patch("builtins.input", return_value="REINICIALIZAR"),
                self.assertRaisesMessage(
                    CommandError,
                    "todas as alterações foram revertidas",
                ),
            ):
                call_command(
                    "reinicializar_dados_desenvolvimento",
                    stdout=saida,
                    stderr=StringIO(),
                )
        finally:
            with connection.cursor() as cursor:
                cursor.execute("DROP TRIGGER impedir_decima_comanda")

        self.assertEqual(self._capturar_estado(), estado_anterior)
        backups = list(self.diretorio_backup.glob("restaurante-*.sqlite3"))
        self.assertEqual(len(backups), 1)
        with closing(sqlite3.connect(backups[0])) as copia:
            self.assertEqual(
                copia.execute("PRAGMA integrity_check").fetchone(),
                ("ok",),
            )
        self.assertNotIn("Reinicialização concluída", saida.getvalue())
        self.assertEqual(
            coletor.registros[-1].contexto_tecnico["etapa"],
            "recriacao",
        )
        eventos = [registro.evento for registro in coletor.registros]
        self.assertNotIn("reinicializacao_massa_inicial_recriada", eventos)
        self.assertNotIn("reinicializacao_desenvolvimento_concluida", eventos)

    def test_execucao_repetida_mantem_massa_inicial_sem_duplicidades(self):
        with (
            override_settings(
                DEBUG=True,
                DIRETORIO_BACKUPS=self.diretorio_backup,
            ),
            patch(
                "builtins.input",
                side_effect=("REINICIALIZAR", "REINICIALIZAR"),
            ),
        ):
            call_command(
                "reinicializar_dados_desenvolvimento",
                stdout=StringIO(),
                stderr=StringIO(),
            )
            call_command(
                "reinicializar_dados_desenvolvimento",
                stdout=StringIO(),
                stderr=StringIO(),
            )

        self.assertEqual(ComandaFisica.objects.count(), 20)
        self.assertEqual(Produto.objects.count(), 10)
        self.assertEqual(UsuarioOperacional.objects.count(), 3)
        self.assertEqual(
            ComandaFisica.objects.values("identificador").distinct().count(),
            20,
        )
        self.assertEqual(Produto.objects.values("nome").distinct().count(), 10)
        self.assertEqual(
            UsuarioOperacional.objects.values("nome").distinct().count(),
            3,
        )
        self.assertEqual(
            len(list(self.diretorio_backup.glob("restaurante-*.sqlite3"))),
            2,
        )

    def test_logging_registra_ordem_e_sucesso_somente_apos_commit(self):
        Produto.objects.create(
            nome="PRODUTO-SIGILOSO-SENTINELA",
            preco_centavos=9876,
        )
        coletor = self._coletar_logs()

        with (
            override_settings(
                DEBUG=True,
                DIRETORIO_BACKUPS=self.diretorio_backup,
            ),
            patch("builtins.input", return_value="REINICIALIZAR"),
            transaction.atomic(),
        ):
            call_command(
                "reinicializar_dados_desenvolvimento",
                stdout=StringIO(),
                stderr=StringIO(),
            )
            eventos_antes_commit = [
                registro.evento for registro in coletor.registros
            ]
            self.assertNotIn(
                "reinicializacao_massa_inicial_recriada",
                eventos_antes_commit,
            )
            self.assertNotIn(
                "reinicializacao_desenvolvimento_concluida",
                eventos_antes_commit,
            )

        eventos = [registro.evento for registro in coletor.registros]
        self.assertEqual(
            eventos,
            [
                "reinicializacao_desenvolvimento_solicitada",
                "reinicializacao_desenvolvimento_confirmada",
                "reinicializacao_backup_iniciado",
                "backup_sqlite_iniciado",
                "backup_sqlite_concluido",
                "reinicializacao_backup_confirmado",
                "reinicializacao_limpeza_iniciada",
                "reinicializacao_massa_inicial_recriada",
                "reinicializacao_desenvolvimento_concluida",
            ],
        )
        valores_contexto = [
            valor
            for registro in coletor.registros
            for valor in registro.contexto_tecnico.values()
        ]
        self.assertNotIn("PRODUTO-SIGILOSO-SENTINELA", valores_contexto)
        self.assertNotIn(9876, valores_contexto)

    def test_falha_do_logging_nao_altera_reinicializacao_bem_sucedida(self):
        logger = logging.getLogger("restaurante")

        with (
            override_settings(
                DEBUG=True,
                DIRETORIO_BACKUPS=self.diretorio_backup,
            ),
            patch("builtins.input", return_value="REINICIALIZAR"),
            patch.object(logger, "handlers", [HandlerFalho()]),
            patch.object(logger, "propagate", False),
        ):
            call_command(
                "reinicializar_dados_desenvolvimento",
                stdout=StringIO(),
                stderr=StringIO(),
            )

        self.assertEqual(ComandaFisica.objects.count(), 20)
        self.assertEqual(Produto.objects.count(), 10)
        self.assertEqual(UsuarioOperacional.objects.count(), 3)
        self.assertEqual(
            len(list(self.diretorio_backup.glob("restaurante-*.sqlite3"))),
            1,
        )

    def test_falha_do_logging_nao_mascara_falha_do_backup(self):
        comanda = ComandaFisica.objects.create(identificador="LOG-FALHO")
        destino_indisponivel = self.diretorio_backup / "destino-indisponivel"
        destino_indisponivel.write_text("sentinela", encoding="utf-8")
        logger = logging.getLogger("restaurante")

        with (
            override_settings(
                DEBUG=True,
                DIRETORIO_BACKUPS=destino_indisponivel,
            ),
            patch("builtins.input", return_value="REINICIALIZAR"),
            patch.object(logger, "handlers", [HandlerFalho()]),
            patch.object(logger, "propagate", False),
            self.assertRaisesMessage(
                CommandError,
                "Falha no backup obrigatório",
            ) as erro_reportado,
        ):
            call_command(
                "reinicializar_dados_desenvolvimento",
                stdout=StringIO(),
                stderr=StringIO(),
            )

        self.assertIsInstance(erro_reportado.exception.__cause__, CommandError)
        self.assertTrue(ComandaFisica.objects.filter(pk=comanda.pk).exists())
        self.assertEqual(
            destino_indisponivel.read_text(encoding="utf-8"),
            "sentinela",
        )

    def test_nao_existe_exposicao_web_nem_execucao_automatica(self):
        comanda = ComandaFisica.objects.create(identificador="NAO-AUTOMATICO")

        with patch("builtins.input") as entrada:
            call_command("check", stdout=StringIO(), stderr=StringIO())

        entrada.assert_not_called()
        self.assertTrue(ComandaFisica.objects.filter(pk=comanda.pk).exists())
        self.assertEqual(list(self.diretorio_backup.iterdir()), [])
        with self.assertRaises(Resolver404):
            resolve("/reinicializar-dados-desenvolvimento/")

        resposta = self.client.get("/")
        self.assertEqual(resposta.status_code, 200)
        self.assertNotContains(resposta, "reinicializar_dados_desenvolvimento")
        self.assertNotContains(resposta, "Reinicializar dados")
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
        self.assertNotIn(
            "reinicializar_dados_desenvolvimento",
            conteudo_templates,
        )
        self.assertNotIn("reinicializar dados", conteudo_templates)

    def test_documentacao_descreve_protecao_e_dados_recriados(self):
        leia_me = (settings.BASE_DIR / "README.md").read_text(encoding="utf-8")

        self.assertIn("reinicializar_dados_desenvolvimento", leia_me)
        self.assertIn("DEBUG=True", leia_me)
        self.assertIn("REINICIALIZAR", leia_me)
        self.assertIn("backup", leia_me)
        self.assertIn("Atendimentos", leia_me)
        self.assertIn("sessões", leia_me)
        self.assertIn("mesma transação", leia_me)
        self.assertIn("rollback", leia_me)

    @staticmethod
    def _capturar_estado():
        modelos = (
            CancelamentoLancamento,
            Lancamento,
            Atendimento,
            RegistroIdempotencia,
            Produto,
            UsuarioOperacional,
            ComandaFisica,
            Session,
        )
        return {
            modelo._meta.label_lower: list(
                modelo.objects.order_by("pk").values()
            )
            for modelo in modelos
        }
