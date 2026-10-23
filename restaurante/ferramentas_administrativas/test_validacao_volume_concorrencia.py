import json
import shutil
import sqlite3
import subprocess
from io import StringIO
from pathlib import Path
from uuid import uuid4
from unittest.mock import patch

from django.conf import settings
from django.core.management import call_command
from django.core.management.base import CommandError
from django.db import OperationalError
from django.test import SimpleTestCase

from restaurante.ferramentas_administrativas.validacao_volume import (
    ContadorContencao,
    InvarianteViolada,
    verificar_invariantes,
)
from restaurante.aplicacao.contencao_persistencia import (
    executar_com_retry_de_contencao,
    observar_contencoes,
)


class ValidarVolumeConcorrenciaCommandTests(SimpleTestCase):
    def setUp(self):
        self.diretorio = (
            settings.DIRETORIO_TESTES / f"volume-concorrencia-{uuid4().hex}"
        )
        self.diretorio.mkdir()
        self.addCleanup(shutil.rmtree, self.diretorio)

    def test_execucao_reduzida_produz_relatorio_publico_em_banco_isolado(self):
        relatorio = self.diretorio / "relatorio.json"
        saida = StringIO()

        call_command(
            "validar_volume_concorrencia",
            lancamentos=20,
            dispositivos=4,
            modo_teste=True,
            arquivo_relatorio=relatorio,
            stdout=saida,
        )

        resultado = json.loads(relatorio.read_text(encoding="utf-8"))
        self.assertGreaterEqual(resultado["cenario"]["lancamentos_persistidos"], 20)
        self.assertEqual(resultado["cenario"]["dispositivos_simulados"], 4)
        self.assertEqual(resultado["cenario"]["dispositivos_observados"], 4)
        self.assertEqual(resultado["sqlite"]["journal_mode"], "wal")
        self.assertEqual(resultado["sqlite"]["synchronous"], "FULL")
        self.assertEqual(resultado["invariantes"]["resultado"], "ok")
        for operacao in ("registro_lancamento", "consulta", "fechamento"):
            medicao = resultado["operacoes"][operacao]
            self.assertGreaterEqual(medicao["quantidade"], 1)
            self.assertEqual(
                medicao["quantidade"],
                sum(
                    medicao[resultado]
                    for resultado in (
                        "concluida",
                        "erro_dominio",
                        "contencao_recuperada",
                        "contencao_persistente",
                    )
                ),
            )
            self.assertEqual(
                set(medicao["tempos_ms"]),
                {"minimo", "mediana", "p95", "maximo"},
            )
            self.assertIn(
                medicao["p95_em_relacao_a_meta_pratica"],
                {"dentro_da_meta_pratica", "acima_da_meta_pratica"},
            )
        self.assertGreaterEqual(
            resultado["operacoes"]["fechamento"]["erro_dominio"],
            1,
        )
        self.assertEqual(
            set(resultado["contencao"]),
            {"sqlite_busy", "sqlite_locked", "retries"},
        )
        self.assertTrue(resultado["idempotencia"]["sem_duplicacao"])
        self.assertEqual(resultado["meta_pratica_segundos"], 1.0)
        self.assertIn(str(relatorio), saida.getvalue())
        self.assertIn("p95", saida.getvalue())
        self.assertIn("Invariantes: ok", saida.getvalue())
        self.assertEqual(
            list(self.diretorio.glob("*.sqlite3")),
            [],
            "o banco exclusivo deve ser removido ao fim da execucao",
        )

    def test_recusa_mais_de_dez_dispositivos(self):
        with self.assertRaisesMessage(
            CommandError,
            "entre 1 e 10",
        ):
            call_command(
                "validar_volume_concorrencia",
                lancamentos=10,
                dispositivos=11,
                modo_teste=True,
                stdout=StringIO(),
            )

    def test_cenario_reduzido_usa_dez_dispositivos_sem_exceder_limite(self):
        relatorio = self.diretorio / "dez-dispositivos.json"

        call_command(
            "validar_volume_concorrencia",
            lancamentos=30,
            dispositivos=10,
            modo_teste=True,
            arquivo_relatorio=relatorio,
            stdout=StringIO(),
        )

        resultado = json.loads(relatorio.read_text(encoding="utf-8"))
        self.assertEqual(resultado["cenario"]["dispositivos_simulados"], 10)
        self.assertEqual(resultado["cenario"]["dispositivos_observados"], 10)

    def test_timeout_remove_banco_temporario_e_retorna_erro_claro(self):
        diretorios_antes = set(settings.DIRETORIO_TESTES.glob("volume-cenario-*"))

        with (
            patch(
                "restaurante.ferramentas_administrativas.management.commands."
                "validar_volume_concorrencia.subprocess.run",
                side_effect=subprocess.TimeoutExpired("validacao", 300),
            ),
            self.assertRaisesMessage(CommandError, "excedeu o limite"),
        ):
            call_command(
                "validar_volume_concorrencia",
                lancamentos=10,
                dispositivos=4,
                modo_teste=True,
                stdout=StringIO(),
            )

        self.assertEqual(
            set(settings.DIRETORIO_TESTES.glob("volume-cenario-*")),
            diretorios_antes,
        )


class ContabilizacaoContencaoTests(SimpleTestCase):
    def test_retry_recuperado_contabiliza_sqlite_busy(self):
        contador = ContadorContencao()
        tentativas = 0

        def operacao_instavel():
            nonlocal tentativas
            tentativas += 1
            if tentativas == 1:
                try:
                    raise sqlite3.OperationalError("database is locked")
                except sqlite3.OperationalError as causa:
                    raise OperationalError("database is locked") from causa
            return "confirmada"

        with observar_contencoes(contador.registrar):
            resultado = executar_com_retry_de_contencao(operacao_instavel)

        self.assertEqual(resultado, "confirmada")
        self.assertEqual(
            contador.resumo(),
            {"sqlite_busy": 1, "sqlite_locked": 0, "retries": 1},
        )

    def test_sqlite_locked_e_contabilizado_separadamente(self):
        contador = ContadorContencao()

        contador.registrar(OperationalError("database table is locked"))

        self.assertEqual(
            contador.resumo(),
            {"sqlite_busy": 0, "sqlite_locked": 1, "retries": 1},
        )


class VerificadorInvariantesTests(SimpleTestCase):
    def setUp(self):
        self.diretorio = (
            settings.DIRETORIO_TESTES / f"invariantes-volume-{uuid4().hex}"
        )
        self.diretorio.mkdir()
        self.addCleanup(shutil.rmtree, self.diretorio)
        self.conexao = sqlite3.connect(self.diretorio / "cenario.sqlite3")
        self.addCleanup(self.conexao.close)
        self.conexao.executescript(
            """
            CREATE TABLE persistencia_atendimento (
                id INTEGER PRIMARY KEY,
                comanda_id INTEGER NOT NULL,
                estado TEXT NOT NULL,
                fechado_em TEXT
            );
            CREATE TABLE persistencia_lancamento (
                id INTEGER PRIMARY KEY,
                atendimento_id INTEGER NOT NULL,
                quantidade INTEGER NOT NULL,
                preco_unitario_centavos INTEGER NOT NULL,
                horario TEXT NOT NULL
            );
            CREATE TABLE persistencia_cancelamentolancamento (
                id INTEGER PRIMARY KEY,
                lancamento_id INTEGER NOT NULL
            );
            CREATE TABLE persistencia_registroidempotencia (
                id INTEGER PRIMARY KEY,
                chave TEXT NOT NULL
            );
            """
        )

    def test_total_incorreto_faz_verificador_falhar_explicitamente(self):
        self.conexao.execute(
            "INSERT INTO persistencia_atendimento VALUES (1, 1, 'ABERTO', NULL)"
        )
        self.conexao.execute(
            "INSERT INTO persistencia_lancamento VALUES "
            "(1, 1, 2, 150, '2026-10-23T10:00:00+00:00')"
        )

        with self.assertRaisesMessage(InvarianteViolada, "Total incorreto"):
            verificar_invariantes(
                self.conexao,
                totais_esperados={1: 299},
                lancamentos_confirmados={1},
            )

    def test_atendimento_aberto_duplicado_faz_verificador_falhar(self):
        self.conexao.executemany(
            "INSERT INTO persistencia_atendimento VALUES (?, 1, 'ABERTO', NULL)",
            [(1,), (2,)],
        )

        with self.assertRaisesMessage(
            InvarianteViolada,
            "Atendimento aberto duplicado",
        ):
            verificar_invariantes(
                self.conexao,
                totais_esperados={1: 0, 2: 0},
                lancamentos_confirmados=set(),
            )

    def test_lancamento_cancelado_nao_entra_no_total(self):
        self.conexao.execute(
            "INSERT INTO persistencia_atendimento VALUES (1, 1, 'ABERTO', NULL)"
        )
        self.conexao.execute(
            "INSERT INTO persistencia_lancamento VALUES "
            "(1, 1, 2, 150, '2026-10-23T10:00:00+00:00')"
        )
        self.conexao.execute(
            "INSERT INTO persistencia_cancelamentolancamento VALUES (1, 1)"
        )

        resultado = verificar_invariantes(
            self.conexao,
            totais_esperados={1: 0},
            lancamentos_confirmados={1},
        )

        self.assertEqual(resultado["resultado"], "ok")
