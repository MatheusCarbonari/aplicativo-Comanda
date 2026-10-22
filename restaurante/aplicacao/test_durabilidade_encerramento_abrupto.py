import json
import queue
import shutil
import subprocess
import sys
import threading
from dataclasses import dataclass
from pathlib import Path
from uuid import uuid4

from django.conf import settings
from django.test import SimpleTestCase


@dataclass
class ProcessoAuxiliar:
    processo: subprocess.Popen
    mensagens: queue.Queue
    leitor_saida: threading.Thread
    caminho_stderr: Path
    saida_fechada: bool = False


class DurabilidadeEncerramentoAbruptoTests(SimpleTestCase):
    TEMPO_LIMITE_SINAL = 10

    def setUp(self):
        self.diretorio = (
            settings.DIRETORIO_TESTES / f"durabilidade-{uuid4().hex}"
        )
        self.diretorio.mkdir()
        self.addCleanup(shutil.rmtree, self.diretorio)
        self.banco = self.diretorio / "restaurante.sqlite3"
        self.log = self.diretorio / "durabilidade.jsonl"

    def test_timeout_recolhe_filho_que_nao_emite_sinal(self):
        processo = self._iniciar_auxiliar("travar")

        with self.assertRaisesRegex(
            AssertionError,
            "timeout aguardando sinal antes_commit",
        ):
            self._aguardar_sinal(
                processo,
                "antes_commit",
                timeout=0.2,
            )

        self.assertIsNotNone(processo.processo.poll())
        self.assertTrue(processo.saida_fechada)

    def test_interrupcao_antes_do_commit_nao_preserva_primeiro_lancamento(self):
        preparo = self._executar_auxiliar("preparar")

        processo = self._iniciar_operacao(
            "primeiro_lancamento",
            "antes_commit",
            "chave-primeiro-antes-commit",
            usuario_id=preparo["garcom_id"],
            produto_id=preparo["produto_id"],
            comanda="001",
        )
        sinal = self._aguardar_sinal(processo, "antes_commit")
        self.assertEqual(sinal["journal_mode"], "wal")
        self.assertEqual(sinal["synchronous"], 2)
        self._encerrar_abruptamente(processo)

        estado = self._executar_auxiliar("inspecionar", comanda="001")
        self.assertEqual(estado["atendimentos"], [])
        self.assertEqual(estado["lancamentos"], [])
        self.assertEqual(estado["cancelamentos"], [])
        self.assertEqual(estado["idempotencias"], [])
        self.assertTrue(estado["comanda_disponivel"])
        self.assertEqual(estado["journal_mode"], "wal")
        self.assertEqual(estado["synchronous"], 2)

    def test_commit_sobrevive_e_replay_recupera_resultado_sem_duplicacao(self):
        preparo = self._executar_auxiliar("preparar")
        argumentos = {
            "usuario_id": preparo["garcom_id"],
            "produto_id": preparo["produto_id"],
            "comanda": "001",
        }
        chave = "chave-resposta-perdida"

        processo = self._iniciar_operacao(
            "primeiro_lancamento",
            "depois_commit",
            chave,
            **argumentos,
        )
        sinal = self._aguardar_sinal(processo, "depois_commit")
        self.assertEqual(sinal["journal_mode"], "wal")
        self.assertEqual(sinal["synchronous"], 2)
        self._encerrar_abruptamente(processo)

        estado_confirmado = self._executar_auxiliar(
            "inspecionar",
            comanda="001",
        )
        self.assertEqual(len(estado_confirmado["atendimentos"]), 1)
        self.assertEqual(
            estado_confirmado["atendimentos"][0]["estado"],
            "ABERTO",
        )
        self.assertEqual(len(estado_confirmado["lancamentos"]), 1)
        self.assertEqual(len(estado_confirmado["idempotencias"]), 1)
        self.assertFalse(estado_confirmado["comanda_disponivel"])
        resultado_persistido = estado_confirmado["idempotencias"][0][
            "resultado"
        ]

        replay = self._iniciar_operacao(
            "primeiro_lancamento",
            "depois_commit",
            chave,
            **argumentos,
        )
        self._aguardar_sinal(replay, "depois_commit")
        resposta_replay = self._entregar_resposta(replay)
        self.assertEqual(resposta_replay["resultado"], resultado_persistido)

        estado_apos_replay = self._executar_auxiliar(
            "inspecionar",
            comanda="001",
        )
        self.assertEqual(estado_apos_replay, estado_confirmado)

    def test_interrupcao_antes_do_commit_reverte_operacoes_em_atendimento(self):
        preparo = self._executar_auxiliar("preparar")
        primeiro = self._executar_com_resposta(
            "primeiro_lancamento",
            "chave-base-confirmada",
            usuario_id=preparo["garcom_id"],
            produto_id=preparo["produto_id"],
            comanda="001",
        )
        estado_base = self._executar_auxiliar("inspecionar", comanda="001")

        cenarios = (
            (
                "lancamento_adicional",
                "chave-adicional-antes-commit",
                {
                    "usuario_id": preparo["garcom_id"],
                    "produto_id": preparo["produto_id"],
                    "comanda": "001",
                },
            ),
            (
                "cancelamento",
                "chave-cancelamento-antes-commit",
                {
                    "usuario_id": preparo["garcom_id"],
                    "lancamento_id": primeiro["lancamento_id"],
                    "motivo": "DUPLICADO",
                    "descricao": "",
                },
            ),
            (
                "fechamento",
                "chave-fechamento-antes-commit",
                {
                    "usuario_id": preparo["caixa_id"],
                    "atendimento_id": primeiro["atendimento_id"],
                    "revisao": estado_base["revisao"],
                },
            ),
        )

        for operacao, chave, argumentos in cenarios:
            with self.subTest(operacao=operacao):
                processo = self._iniciar_operacao(
                    operacao,
                    "antes_commit",
                    chave,
                    **argumentos,
                )
                self._aguardar_sinal(processo, "antes_commit")
                self._encerrar_abruptamente(processo)
                self.assertEqual(
                    self._executar_auxiliar("inspecionar", comanda="001"),
                    estado_base,
                )

        self.assertEqual(len(estado_base["atendimentos"]), 1)
        self.assertEqual(estado_base["atendimentos"][0]["estado"], "ABERTO")
        self.assertEqual(len(estado_base["lancamentos"]), 1)
        self.assertEqual(estado_base["cancelamentos"], [])
        self.assertEqual(len(estado_base["idempotencias"]), 1)

    def test_operacoes_confirmadas_sobrevivem_ate_o_fechamento(self):
        preparo = self._executar_auxiliar("preparar")
        primeiro = self._executar_com_resposta(
            "primeiro_lancamento",
            "chave-primeiro-fluxo-completo",
            usuario_id=preparo["garcom_id"],
            produto_id=preparo["produto_id"],
            comanda="001",
        )
        estado_inicial = self._executar_auxiliar("inspecionar", comanda="001")

        adicional = self._executar_e_interromper_depois_commit(
            "lancamento_adicional",
            "chave-adicional-confirmada",
            usuario_id=preparo["garcom_id"],
            produto_id=preparo["produto_id"],
            comanda="001",
        )
        estado_com_adicional = self._executar_auxiliar(
            "inspecionar",
            comanda="001",
        )
        self.assertEqual(len(estado_com_adicional["lancamentos"]), 2)
        self.assertEqual(len(estado_com_adicional["idempotencias"]), 2)
        self.assertNotEqual(
            estado_com_adicional["revisao"],
            estado_inicial["revisao"],
        )

        self._executar_e_interromper_depois_commit(
            "cancelamento",
            "chave-cancelamento-confirmado",
            usuario_id=preparo["garcom_id"],
            lancamento_id=adicional["lancamento_id"],
            motivo="DUPLICADO",
            descricao="",
        )
        estado_cancelado = self._executar_auxiliar(
            "inspecionar",
            comanda="001",
        )
        self.assertEqual(len(estado_cancelado["cancelamentos"]), 1)
        self.assertEqual(estado_cancelado["lancamentos_validos"], 1)
        self.assertEqual(len(estado_cancelado["idempotencias"]), 3)
        self.assertNotEqual(
            estado_cancelado["revisao"],
            estado_com_adicional["revisao"],
        )

        self._executar_e_interromper_depois_commit(
            "fechamento",
            "chave-fechamento-confirmado",
            usuario_id=preparo["caixa_id"],
            atendimento_id=primeiro["atendimento_id"],
            revisao=estado_cancelado["revisao"],
        )
        estado_fechado = self._executar_auxiliar(
            "inspecionar",
            comanda="001",
        )
        self.assertEqual(len(estado_fechado["atendimentos"]), 1)
        self.assertEqual(
            estado_fechado["atendimentos"][0]["estado"],
            "ENCERRADO",
        )
        self.assertIsNotNone(
            estado_fechado["atendimentos"][0]["fechado_por_id"]
        )
        self.assertIsNotNone(estado_fechado["atendimentos"][0]["fechado_em"])
        self.assertEqual(estado_fechado["atendimentos_abertos"], 0)
        self.assertTrue(estado_fechado["comanda_disponivel"])
        self.assertEqual(len(estado_fechado["idempotencias"]), 4)
        self.assertNotEqual(
            estado_fechado["revisao"],
            estado_cancelado["revisao"],
        )
        self.assertEqual(estado_fechado["journal_mode"], "wal")
        self.assertEqual(estado_fechado["synchronous"], 2)

    def test_verificacao_pode_ser_repetida_em_bancos_persistentes_isolados(self):
        for repeticao in range(2):
            with self.subTest(repeticao=repeticao):
                self.banco = self.diretorio / f"repeticao-{repeticao}.sqlite3"
                self.log = self.diretorio / f"repeticao-{repeticao}.jsonl"
                preparo = self._executar_auxiliar("preparar")
                self.assertTrue(self.banco.is_file())
                processo = self._iniciar_operacao(
                    "primeiro_lancamento",
                    "antes_commit",
                    f"chave-repeticao-{repeticao}",
                    usuario_id=preparo["garcom_id"],
                    produto_id=preparo["produto_id"],
                    comanda="001",
                )
                self._aguardar_sinal(processo, "antes_commit")
                self._encerrar_abruptamente(processo)
                estado = self._executar_auxiliar(
                    "inspecionar",
                    comanda="001",
                )
                self.assertEqual(estado["atendimentos"], [])
                self.assertEqual(estado["idempotencias"], [])
                self.assertEqual(estado["journal_mode"], "wal")
                self.assertEqual(estado["synchronous"], 2)

    def test_documentacao_explica_execucao_e_limites_da_simulacao(self):
        leia_me = (settings.BASE_DIR / "README.md").read_text(encoding="utf-8")
        texto_normalizado = " ".join(leia_me.split())

        self.assertIn("test_durabilidade_encerramento_abrupto", texto_normalizado)
        self.assertIn("antes_commit", texto_normalizado)
        self.assertIn("depois_commit", texto_normalizado)
        self.assertIn("WAL", texto_normalizado)
        self.assertIn("synchronous=FULL", texto_normalizado)
        self.assertIn(
            "não equivale a uma queda física de energia",
            texto_normalizado,
        )
        self.assertIn("cache volátil", texto_normalizado)
        self.assertIn("falha física de armazenamento", texto_normalizado)

    def _comando_auxiliar(self, acao, **argumentos):
        comando = [
            sys.executable,
            "-m",
            "restaurante.testes_suporte.processo_durabilidade",
            "--banco",
            str(self.banco),
            "--log",
            str(self.log),
            acao,
        ]
        for nome, valor in argumentos.items():
            comando.extend((f"--{nome.replace('_', '-')}", str(valor)))
        return comando

    def _executar_auxiliar(self, acao, **argumentos):
        concluido = subprocess.run(
            self._comando_auxiliar(acao, **argumentos),
            cwd=settings.BASE_DIR,
            check=True,
            capture_output=True,
            text=True,
            timeout=30,
        )
        return json.loads(concluido.stdout)

    def _iniciar_operacao(self, operacao, ponto, chave, **argumentos):
        return self._iniciar_auxiliar(
            "operar",
            operacao=operacao,
            ponto=ponto,
            chave=chave,
            **argumentos,
        )

    def _iniciar_auxiliar(self, acao, **argumentos):
        caminho_stderr = self.diretorio / f"stderr-{uuid4().hex}.log"
        with caminho_stderr.open("w", encoding="utf-8") as arquivo_stderr:
            processo = subprocess.Popen(
                self._comando_auxiliar(acao, **argumentos),
                cwd=settings.BASE_DIR,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=arquivo_stderr,
                text=True,
            )
        mensagens = queue.Queue()

        def drenar_saida():
            assert processo.stdout is not None
            try:
                for linha in processo.stdout:
                    mensagens.put(linha)
            finally:
                mensagens.put(None)

        leitor_saida = threading.Thread(target=drenar_saida, daemon=True)
        leitor_saida.start()
        auxiliar = ProcessoAuxiliar(
            processo=processo,
            mensagens=mensagens,
            leitor_saida=leitor_saida,
            caminho_stderr=caminho_stderr,
        )
        self.addCleanup(self._finalizar_se_ativo, auxiliar)
        return auxiliar

    def _aguardar_sinal(
        self,
        auxiliar,
        sinal_esperado,
        *,
        timeout=None,
    ):
        limite = self.TEMPO_LIMITE_SINAL if timeout is None else timeout
        mensagem = self._receber_json(
            auxiliar,
            timeout=limite,
            contexto=f"sinal {sinal_esperado}",
        )
        if not isinstance(mensagem, dict):
            self._finalizar_processo(auxiliar)
            self.fail(
                "Protocolo inválido: esperado objeto JSON, recebido "
                f"{mensagem!r}. stderr: {self._ler_stderr(auxiliar)}"
            )
        if mensagem.get("sinal") != sinal_esperado:
            self._finalizar_processo(auxiliar)
            self.fail(
                "Protocolo inválido: esperado sinal "
                f"{sinal_esperado}, recebido {mensagem!r}. "
                f"stderr: {self._ler_stderr(auxiliar)}"
            )
        if (
            mensagem.get("journal_mode") != "wal"
            or mensagem.get("synchronous") != 2
        ):
            self._finalizar_processo(auxiliar)
            self.fail(
                "Processo mutador sem WAL/FULL: "
                f"{mensagem!r}. stderr: {self._ler_stderr(auxiliar)}"
            )
        return mensagem

    def _receber_json(self, auxiliar, *, timeout, contexto):
        try:
            linha = auxiliar.mensagens.get(timeout=timeout)
        except queue.Empty:
            self._finalizar_processo(auxiliar)
            self.fail(
                f"timeout aguardando {contexto}; processo filho recolhido. "
                f"stderr: {self._ler_stderr(auxiliar)}"
            )
        if linha is None:
            self._finalizar_processo(auxiliar)
            self.fail(
                f"Processo auxiliar terminou sem {contexto}. "
                f"stderr: {self._ler_stderr(auxiliar)}"
            )
        try:
            return json.loads(linha)
        except json.JSONDecodeError:
            self._finalizar_processo(auxiliar)
            self.fail(
                f"Protocolo JSON inválido ao aguardar {contexto}: {linha!r}. "
                f"stderr: {self._ler_stderr(auxiliar)}"
            )

    def _executar_com_resposta(self, operacao, chave, **argumentos):
        processo = self._iniciar_operacao(
            operacao, "depois_commit", chave, **argumentos
        )
        self._aguardar_sinal(processo, "depois_commit")
        return self._entregar_resposta(processo)["resultado"]

    def _executar_e_interromper_depois_commit(
        self,
        operacao,
        chave,
        **argumentos,
    ):
        processo = self._iniciar_operacao(
            operacao,
            "depois_commit",
            chave,
            **argumentos,
        )
        self._aguardar_sinal(processo, "depois_commit")
        self._encerrar_abruptamente(processo)
        estado = self._executar_auxiliar("inspecionar", comanda="001")
        resultado = next(
            registro["resultado"]
            for registro in estado["idempotencias"]
            if registro["chave"] == chave
        )
        return resultado

    def _encerrar_abruptamente(self, auxiliar):
        auxiliar.processo.kill()
        auxiliar.processo.wait(timeout=10)
        self.assertNotEqual(auxiliar.processo.returncode, 0)
        self._fechar_recursos(auxiliar)

    def _entregar_resposta(self, auxiliar):
        assert auxiliar.processo.stdin is not None
        auxiliar.processo.stdin.write("entregar\n")
        auxiliar.processo.stdin.flush()
        auxiliar.processo.stdin.close()
        resposta = self._receber_json(
            auxiliar,
            timeout=self.TEMPO_LIMITE_SINAL,
            contexto="resposta da operação",
        )
        try:
            auxiliar.processo.wait(timeout=self.TEMPO_LIMITE_SINAL)
        except subprocess.TimeoutExpired:
            self._finalizar_processo(auxiliar)
            self.fail(
                "timeout aguardando término após resposta; "
                "processo filho recolhido."
            )
        self.assertEqual(auxiliar.processo.returncode, 0)
        self._fechar_recursos(auxiliar)
        return resposta

    def _finalizar_processo(self, auxiliar):
        if auxiliar.processo.poll() is None:
            auxiliar.processo.kill()
        auxiliar.processo.wait(timeout=10)
        self._fechar_recursos(auxiliar)

    def _finalizar_se_ativo(self, auxiliar):
        self._finalizar_processo(auxiliar)

    @staticmethod
    def _fechar_recursos(auxiliar):
        stdin = auxiliar.processo.stdin
        stdout = auxiliar.processo.stdout
        if stdin is not None and not stdin.closed:
            stdin.close()
        if stdout is not None and not stdout.closed:
            stdout.close()
        auxiliar.leitor_saida.join(timeout=1)
        auxiliar.saida_fechada = stdout is None or stdout.closed

    @staticmethod
    def _ler_stderr(auxiliar):
        try:
            return auxiliar.caminho_stderr.read_text(
                encoding="utf-8",
                errors="replace",
            ).strip()
        except OSError as erro:
            return f"indisponível ({type(erro).__name__})"
