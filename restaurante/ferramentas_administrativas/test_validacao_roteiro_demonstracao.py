import json
import shutil
from io import StringIO
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
from uuid import uuid4

from django.conf import settings
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import SimpleTestCase

from restaurante.testes_suporte.chrome_responsivo import (
    FalhaChrome,
    validar_paginas_responsivas,
)


class ValidarRoteiroDemonstracaoCommandTests(SimpleTestCase):
    def setUp(self):
        self.diretorio = (
            settings.DIRETORIO_TESTES / f"roteiro-demonstracao-{uuid4().hex}"
        )
        self.diretorio.mkdir()
        self.addCleanup(shutil.rmtree, self.diretorio)

    def test_fluxo_integrado_usa_http_publico_em_sqlite_isolado(self):
        relatorio = self.diretorio / "relatorio.json"
        saida = StringIO()

        call_command(
            "validar_roteiro_demonstracao",
            modo_teste=True,
            arquivo_relatorio=relatorio,
            stdout=saida,
        )

        resultado = json.loads(relatorio.read_text(encoding="utf-8"))
        self.assertEqual(resultado["sqlite"]["journal_mode"], "wal")
        self.assertEqual(resultado["sqlite"]["synchronous"], "FULL")
        self.assertEqual(resultado["sqlite"]["integrity_check"], "ok")
        self.assertEqual(resultado["fluxo_web"]["resultado"], "aprovado")
        self.assertEqual(
            resultado["fluxo_web"]["etapas"],
            [
                "Garçom selecionado",
                "Comanda disponível consultada",
                "Primeiro Lançamento registrado",
                "Lançamentos adicionais registrados",
                "Outro Garçom selecionado",
                "Lançamento cancelado",
                "Caixa consultou consolidação",
                "Mudança posterior exigiu nova confirmação",
                "Atendimento fechado",
                "Resumo final consultado",
                "Comanda reutilizada sem misturar históricos",
            ],
        )
        self.assertEqual(resultado["idempotencia"]["resultado"], "aprovado")
        self.assertEqual(
            resultado["reutilizacao_comanda"]["resultado"], "aprovado"
        )
        self.assertEqual(
            resultado["responsividade"]["resultado"],
            "não executada no modo de teste",
        )
        self.assertEqual(
            resultado["comunicacao"]["resultado"],
            "não executada no modo de teste",
        )
        self.assertEqual(
            resultado["operacoes_administrativas"]["resultado"],
            "não executadas no modo de teste",
        )
        self.assertIn(str(relatorio), saida.getvalue())
        self.assertEqual(
            list(self.diretorio.glob("*.sqlite3")),
            [],
            "o banco isolado deve ser removido ao final",
        )

    def test_documenta_execucao_e_validacao_manual_do_leitor(self):
        readme = (Path(settings.BASE_DIR) / "README.md").read_text(
            encoding="utf-8"
        )

        self.assertIn("manage.py validar_roteiro_demonstracao", readme)
        self.assertIn("390×844", readme)
        self.assertIn("1366×768", readme)
        self.assertIn("Validação manual com leitor físico", readme)
        self.assertIn("modelo do leitor", readme)
        self.assertIn("não declara que ela foi executada", readme)

    def test_etapa_obrigatoria_nao_comprovada_reprova_o_comando(self):
        relatorio = self.diretorio / "falha.json"

        def executar(comando, **kwargs):
            if any("processo_roteiro_demonstracao" in item for item in comando):
                relatorio.write_text(
                    json.dumps({"falhas": []}), encoding="utf-8"
                )
                return SimpleNamespace(returncode=0, stdout="fluxo ok", stderr="")
            return SimpleNamespace(
                returncode=1,
                stdout="",
                stderr="suíte de comunicação falhou",
            )

        with patch(
            "restaurante.ferramentas_administrativas.management.commands."
            "validar_roteiro_demonstracao.subprocess.run",
            side_effect=executar,
        ) as executar_processo:
            with self.assertRaisesRegex(
                CommandError, "etapa obrigatória comunicação falhou"
            ):
                call_command(
                    "validar_roteiro_demonstracao",
                    arquivo_relatorio=relatorio,
                )

        self.assertEqual(executar_processo.call_count, 2)
        resultado = json.loads(relatorio.read_text(encoding="utf-8"))
        self.assertIn("comunicação falhou", resultado["falhas"][0])

    def test_chrome_encerrado_antes_das_medicoes_reprova_validacao(self):
        processo = SimpleNamespace(returncode=-1073741819)
        processo.poll = lambda: processo.returncode
        pagina = self.diretorio / "pagina.html"
        pagina.write_text("<!doctype html><title>Teste</title>", encoding="utf-8")

        with (
            patch(
                "restaurante.testes_suporte.chrome_responsivo.subprocess.Popen",
                return_value=processo,
            ),
            patch(
                "restaurante.testes_suporte.chrome_responsivo._aguardar_devtools",
                return_value={
                    "Browser": "Chrome/Teste",
                    "webSocketDebuggerUrl": "ws://127.0.0.1/devtools/browser/teste",
                },
            ),
            patch(
                "restaurante.testes_suporte.chrome_responsivo._encerrar_arvore"
            ),
        ):
            with self.assertRaisesRegex(
                FalhaChrome, "encerrou inesperadamente antes de concluir"
            ):
                validar_paginas_responsivas(
                    navegador=Path("chrome.exe"),
                    paginas={"pagina": pagina},
                    diretorio_perfil=self.diretorio / "perfil",
                )

    def test_codigo_anormal_no_encerramento_do_chrome_reprova_validacao(self):
        processo = SimpleNamespace(returncode=None)
        processo.poll = lambda: None
        processo.wait = lambda timeout: -1073741819
        pagina = self.diretorio / "pagina.html"
        pagina.write_text("<!doctype html><title>Teste</title>", encoding="utf-8")
        canal = SimpleNamespace(chamar=lambda metodo: {}, close=lambda: None)

        with (
            patch(
                "restaurante.testes_suporte.chrome_responsivo.subprocess.Popen",
                return_value=processo,
            ),
            patch(
                "restaurante.testes_suporte.chrome_responsivo._aguardar_devtools",
                return_value={
                    "Browser": "Chrome/Teste",
                    "webSocketDebuggerUrl": "ws://127.0.0.1/devtools/browser/teste",
                },
            ),
            patch(
                "restaurante.testes_suporte.chrome_responsivo._medir_pagina",
                return_value={},
            ),
            patch(
                "restaurante.testes_suporte.chrome_responsivo._CanalDevTools",
                return_value=canal,
            ),
            patch(
                "restaurante.testes_suporte.chrome_responsivo._encerrar_arvore"
            ),
        ):
            with self.assertRaisesRegex(
                FalhaChrome, "código inesperado depois das medições"
            ):
                validar_paginas_responsivas(
                    navegador=Path("chrome.exe"),
                    paginas={"pagina": pagina},
                    diretorio_perfil=self.diretorio / "perfil",
                )
