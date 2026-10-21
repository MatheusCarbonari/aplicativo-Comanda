import json
import logging
import os
import subprocess
import sys
from contextlib import contextmanager
from datetime import datetime
from importlib import import_module
from io import StringIO
from logging.handlers import RotatingFileHandler
from unittest.mock import call, patch

from django.conf import settings
from django.db import DatabaseError, transaction
from django.test import TestCase, TransactionTestCase

from restaurante.infraestrutura.logging_estruturado import registrar_evento
from restaurante.aplicacao.registrar_primeiro_lancamento import (
    registrar_primeiro_lancamento,
)
from restaurante.aplicacao.cancelar_lancamento import cancelar_lancamento
from restaurante.aplicacao.registrar_lancamento_adicional import (
    registrar_lancamento_adicional,
)
from restaurante.aplicacao.fechar_atendimento import fechar_atendimento
from restaurante.aplicacao.revisao_fechamento import (
    calcular_revisao_fechamento,
)
from restaurante.persistencia.models import (
    Atendimento,
    ComandaFisica,
    Lancamento,
    Produto,
    UsuarioOperacional,
)


class HandlerFalho(logging.Handler):
    def emit(self, record):
        raise OSError("disco de logs indisponível")


@contextmanager
def capturar_jsonl_aplicacao():
    logger = logging.getLogger("restaurante")
    fluxo = StringIO()
    handler = logging.StreamHandler(fluxo)
    handler.setFormatter(logger.handlers[0].formatter)
    handlers_originais = logger.handlers[:]
    propagacao_original = logger.propagate
    logger.handlers = [handler]
    logger.propagate = False
    try:
        yield fluxo
    finally:
        handler.close()
        logger.handlers = handlers_originais
        logger.propagate = propagacao_original


class LoggingEstruturadoTests(TestCase):
    def test_configuracao_grava_jsonl_em_diretorio_persistente_conhecido(self):
        self.assertEqual(
            settings.DIRETORIO_LOGS,
            settings.BASE_DIR / ".local" / "logs",
        )
        self.assertEqual(
            settings.CAMINHO_LOG_APLICACAO,
            settings.DIRETORIO_LOGS / "restaurante.jsonl",
        )
        configuracao_handler = settings.LOGGING["handlers"][
            "arquivo_estruturado"
        ]
        self.assertEqual(
            configuracao_handler["class"],
            "logging.handlers.RotatingFileHandler",
        )

        caminho = settings.DIRETORIO_TESTES / "logging-estruturado.jsonl"
        caminho.unlink(missing_ok=True)
        handler = RotatingFileHandler(caminho, encoding="utf-8")
        handler.setFormatter(
            logging.getLogger("restaurante").handlers[0].formatter
        )
        logger = logging.getLogger("restaurante.teste.formato")
        handlers_originais = logger.handlers[:]
        propagacao_original = logger.propagate
        nivel_original = logger.level
        logger.handlers = [handler]
        logger.propagate = False
        logger.setLevel(logging.INFO)
        try:
            registrar_evento(
                "diagnostico_teste",
                logger=logger,
                atendimento_id=42,
                level="NIVEL-FALSO",
                timestamp="HORARIO-FALSO",
            )
            handler.close()
            registro = json.loads(caminho.read_text(encoding="utf-8"))
        finally:
            handler.close()
            logger.handlers = handlers_originais
            logger.propagate = propagacao_original
            logger.setLevel(nivel_original)
            caminho.unlink(missing_ok=True)

        self.assertEqual(registro["level"], "INFO")
        self.assertEqual(registro["event"], "diagnostico_teste")
        self.assertEqual(registro["atendimento_id"], 42)
        self.assertIsNotNone(
            datetime.fromisoformat(registro["timestamp"]).tzinfo
        )

    def test_suite_escreve_em_arquivo_isolado_do_log_operacional(self):
        configuracao = settings.LOGGING["handlers"]["arquivo_estruturado"]
        self.assertEqual(
            configuracao["filename"],
            settings.CAMINHO_LOG_TESTES,
        )
        self.assertNotEqual(
            configuracao["filename"],
            settings.CAMINHO_LOG_APLICACAO,
        )
        conteudo_operacional_antes = (
            settings.CAMINHO_LOG_APLICACAO.read_bytes()
            if settings.CAMINHO_LOG_APLICACAO.exists()
            else None
        )

        registrar_evento("evento-exclusivo-da-suite-de-testes")
        for handler in logging.getLogger("restaurante").handlers:
            handler.flush()

        conteudo_operacional_depois = (
            settings.CAMINHO_LOG_APLICACAO.read_bytes()
            if settings.CAMINHO_LOG_APLICACAO.exists()
            else None
        )
        self.assertEqual(
            conteudo_operacional_depois,
            conteudo_operacional_antes,
        )

    def test_comando_check_nao_altera_arquivo_operacional(self):
        conteudo_antes = (
            settings.CAMINHO_LOG_APLICACAO.read_bytes()
            if settings.CAMINHO_LOG_APLICACAO.exists()
            else None
        )
        ambiente = os.environ.copy()
        ambiente.pop("RUN_MAIN", None)
        ambiente.pop("RESTAURANTE_PROCESSO_OPERACIONAL", None)

        subprocess.run(
            [sys.executable, "manage.py", "check"],
            cwd=settings.BASE_DIR,
            env=ambiente,
            check=True,
            capture_output=True,
            text=True,
        )

        conteudo_depois = (
            settings.CAMINHO_LOG_APLICACAO.read_bytes()
            if settings.CAMINHO_LOG_APLICACAO.exists()
            else None
        )
        self.assertEqual(conteudo_depois, conteudo_antes)

    def test_rotacao_configurada_e_executada_com_limite_controlado(self):
        configuracao = settings.LOGGING["handlers"]["arquivo_estruturado"]
        self.assertEqual(configuracao["maxBytes"], 5 * 1024 * 1024)
        self.assertEqual(configuracao["backupCount"], 5)

        caminho = settings.DIRETORIO_TESTES / "logging-rotacao.jsonl"
        caminhos = [caminho, caminho.with_name(f"{caminho.name}.1")]
        for arquivo in caminhos:
            arquivo.unlink(missing_ok=True)
        handler = RotatingFileHandler(
            caminho,
            maxBytes=120,
            backupCount=1,
            encoding="utf-8",
        )
        handler.setFormatter(
            logging.getLogger("restaurante").handlers[0].formatter
        )
        logger = logging.getLogger("restaurante.teste.rotacao")
        handlers_originais = logger.handlers[:]
        propagacao_original = logger.propagate
        nivel_original = logger.level
        logger.handlers = [handler]
        logger.propagate = False
        logger.setLevel(logging.INFO)
        try:
            for numero in range(2):
                registrar_evento(
                    "rotacao_controlada",
                    logger=logger,
                    operation_id=f"operacao-{numero}-" + "x" * 40,
                )
            handler.close()

            self.assertTrue(caminho.exists())
            self.assertTrue(caminho.with_name(f"{caminho.name}.1").exists())
            for arquivo in caminhos:
                for linha in arquivo.read_text(encoding="utf-8").splitlines():
                    json.loads(linha)
        finally:
            handler.close()
            logger.handlers = handlers_originais
            logger.propagate = propagacao_original
            logger.setLevel(nivel_original)
            for arquivo in caminhos:
                arquivo.unlink(missing_ok=True)

    def test_ciclo_django_registra_inicio_e_callback_publico_de_encerramento(
        self,
    ):
        from restaurante.infraestrutura.apps import InfraestruturaConfig
        from restaurante.infraestrutura.ciclo_vida import (
            registrar_encerramento_aplicacao,
        )

        primeira_config = InfraestruturaConfig(
            "restaurante.infraestrutura",
            import_module("restaurante.infraestrutura"),
        )
        segunda_config = InfraestruturaConfig(
            "restaurante.infraestrutura",
            import_module("restaurante.infraestrutura"),
        )
        with (
            patch(
                "restaurante.infraestrutura.ciclo_vida.registrar_evento"
            ) as registrar,
            patch("atexit.register") as registrar_callback,
            patch.object(sys, "argv", ["manage.py", "runserver"]),
            patch.dict(
                os.environ,
                {"RUN_MAIN": "true"},
                clear=True,
            ),
        ):
            primeira_config.ready()
            segunda_config.ready()

            registrar.assert_called_once_with("aplicacao_iniciada")
            registrar_callback.assert_called_once_with(
                registrar_encerramento_aplicacao
            )

            registrar_callback.call_args.args[0]()
            registrar_callback.call_args.args[0]()

        self.assertEqual(
            registrar.call_args_list,
            [
                call("aplicacao_iniciada"),
                call("aplicacao_encerrada"),
            ],
        )

    def test_comando_check_nao_registra_ciclo_operacional(self):
        from restaurante.infraestrutura.apps import InfraestruturaConfig

        config = InfraestruturaConfig(
            "restaurante.infraestrutura",
            import_module("restaurante.infraestrutura"),
        )
        with (
            patch(
                "restaurante.infraestrutura.ciclo_vida.registrar_evento"
            ) as registrar,
            patch("atexit.register") as registrar_callback,
            patch.object(sys, "argv", ["manage.py", "check"]),
            patch.dict(os.environ, {}, clear=True),
        ):
            config.ready()

        registrar.assert_not_called()
        registrar_callback.assert_not_called()

    def test_processo_auxiliar_do_autoreload_nao_registra_ciclo(self):
        from restaurante.infraestrutura.apps import InfraestruturaConfig

        config = InfraestruturaConfig(
            "restaurante.infraestrutura",
            import_module("restaurante.infraestrutura"),
        )
        with (
            patch(
                "restaurante.infraestrutura.ciclo_vida.registrar_evento"
            ) as registrar,
            patch("atexit.register") as registrar_callback,
            patch.object(sys, "argv", ["manage.py", "runserver"]),
            patch.dict(os.environ, {}, clear=True),
        ):
            config.ready()

        registrar.assert_not_called()
        registrar_callback.assert_not_called()

    def test_erro_inesperado_em_fluxo_http_e_registrado_sem_requisicao(self):
        segredo = "FORMULARIO-CSRF-COOKIE-SESSAO-SENTINELA"
        self.client.raise_request_exception = False

        with (
            capturar_jsonl_aplicacao() as fluxo,
            patch(
                "restaurante.interface_web.views.executar_primeiro_lancamento",
                side_effect=RuntimeError(segredo),
            ),
        ):
            resposta = self.client.post(
                "/lancamentos/primeiro/",
                {
                    "identificador_comanda": segredo,
                    "produto_id": segredo,
                    "quantidade": segredo,
                    "chave_idempotencia": segredo,
                    "csrfmiddlewaretoken": segredo,
                },
                HTTP_COOKIE=f"sessionid={segredo}",
                HTTP_X_CSRFTOKEN=segredo,
            )

        registros = [
            json.loads(linha)
            for linha in fluxo.getvalue().splitlines()
            if linha
        ]
        erro = next(
            registro
            for registro in registros
            if registro["event"] == "erro_inesperado_http"
        )
        self.assertEqual(resposta.status_code, 500)
        self.assertEqual(erro["level"], "ERROR")
        self.assertEqual(erro["error_type"], "RuntimeError")
        self.assertEqual(erro["method"], "POST")
        self.assertEqual(erro["path"], "/lancamentos/primeiro/")
        self.assertNotIn(segredo, fluxo.getvalue())

    def test_falha_de_banco_tratada_pelo_http_e_registrada_sem_detalhes(self):
        detalhe_sensivel = "sql-e-parametros-sentinela"

        with (
            capturar_jsonl_aplicacao() as fluxo,
            patch(
                "restaurante.infraestrutura.saude.connection.cursor",
                side_effect=DatabaseError(detalhe_sensivel),
            ),
        ):
            resposta = self.client.get("/saude/")

        registros = [
            json.loads(linha)
            for linha in fluxo.getvalue().splitlines()
            if linha
        ]
        falha = next(
            registro
            for registro in registros
            if registro["event"] == "falha_banco"
        )
        self.assertEqual(resposta.status_code, 503)
        self.assertEqual(falha["level"], "ERROR")
        self.assertEqual(falha["error_type"], "DatabaseError")
        self.assertEqual(falha["operation"], "verificar_saude")
        self.assertNotIn(detalhe_sensivel, fluxo.getvalue())
        self.assertNotContains(
            resposta,
            detalhe_sensivel,
            status_code=503,
        )

    def test_operacao_confirmada_registra_so_identificadores_tecnicos(self):
        nome_produto = "PRODUTO-CONSUMIDO-SENTINELA"
        quantidade = 987_654
        preco = 87_654_321
        chave_operacao = "operacao-tecnica-correlacionavel"
        garcom = UsuarioOperacional.objects.create(
            nome="Garçom de teste",
            papel=UsuarioOperacional.Papel.GARCOM,
        )
        ComandaFisica.objects.create(identificador="001")
        produto = Produto.objects.create(
            nome=nome_produto,
            preco_centavos=preco,
        )

        with capturar_jsonl_aplicacao() as fluxo:
            with self.captureOnCommitCallbacks(execute=True):
                resultado = registrar_primeiro_lancamento(
                    garcom.pk,
                    "001",
                    produto.pk,
                    quantidade,
                    chave_operacao,
                )

        registros = [
            json.loads(linha)
            for linha in fluxo.getvalue().splitlines()
            if linha
        ]
        operacao = next(
            registro
            for registro in registros
            if registro["event"] == "operacao_dominio_confirmada"
        )
        self.assertEqual(
            operacao["operation"],
            "REGISTRAR_PRIMEIRO_LANCAMENTO",
        )
        self.assertEqual(operacao["operation_id"], chave_operacao)
        self.assertEqual(operacao["atendimento_id"], resultado.atendimento_id)
        self.assertEqual(operacao["usuario_operacional_id"], garcom.pk)
        conteudo_log = fluxo.getvalue()
        self.assertNotIn(nome_produto, conteudo_log)
        self.assertNotIn(str(quantidade), conteudo_log)
        self.assertNotIn(str(preco), conteudo_log)
        self.assertNotIn(str(quantidade * preco), conteudo_log)

    def test_falha_do_handler_nao_altera_resultado_persistido_do_dominio(self):
        garcom = UsuarioOperacional.objects.create(
            nome="Garçom resiliente",
            papel=UsuarioOperacional.Papel.GARCOM,
        )
        ComandaFisica.objects.create(identificador="002")
        produto = Produto.objects.create(nome="Água", preco_centavos=500)
        logger = logging.getLogger("restaurante")
        handlers_originais = logger.handlers[:]
        propagacao_original = logger.propagate
        logger.handlers = [HandlerFalho()]
        logger.propagate = False
        try:
            with self.captureOnCommitCallbacks(execute=True):
                resultado = registrar_primeiro_lancamento(
                    garcom.pk,
                    "002",
                    produto.pk,
                    1,
                    "logging-nao-e-fonte-da-verdade",
                )
        finally:
            logger.handlers = handlers_originais
            logger.propagate = propagacao_original

        self.assertEqual(Atendimento.objects.count(), 1)
        self.assertEqual(Lancamento.objects.count(), 1)
        self.assertEqual(
            resultado.lancamento_id,
            Lancamento.objects.get().pk,
        )

    def test_cancelamento_confirmado_nao_registra_motivo_ou_descricao(self):
        garcom = UsuarioOperacional.objects.create(
            nome="Garçom cancelador",
            papel=UsuarioOperacional.Papel.GARCOM,
        )
        ComandaFisica.objects.create(identificador="003")
        produto = Produto.objects.create(nome="Suco", preco_centavos=900)
        lancamento = registrar_primeiro_lancamento(
            garcom.pk,
            "003",
            produto.pk,
            2,
            "preparar-cancelamento",
        )
        descricao = "DESCRICAO-CANCELAMENTO-SENTINELA"

        with capturar_jsonl_aplicacao() as fluxo:
            with self.captureOnCommitCallbacks(execute=True):
                resultado = cancelar_lancamento(
                    garcom.pk,
                    lancamento.lancamento_id,
                    "OUTRO",
                    descricao,
                    "cancelamento-correlacionavel",
                )

        registros = [
            json.loads(linha)
            for linha in fluxo.getvalue().splitlines()
            if linha
        ]
        operacao = next(
            registro
            for registro in registros
            if registro["event"] == "operacao_dominio_confirmada"
        )
        self.assertEqual(operacao["operation"], "CANCELAR_LANCAMENTO")
        self.assertEqual(
            operacao["cancelamento_id"],
            resultado.cancelamento_id,
        )
        self.assertEqual(operacao["atendimento_id"], resultado.atendimento_id)
        self.assertEqual(operacao["lancamento_id"], resultado.lancamento_id)
        self.assertNotIn("OUTRO", fluxo.getvalue())
        self.assertNotIn(descricao, fluxo.getvalue())

    def test_lancamento_adicional_confirmado_registra_somente_ids(self):
        garcom = UsuarioOperacional.objects.create(
            nome="Garçom adicional",
            papel=UsuarioOperacional.Papel.GARCOM,
        )
        ComandaFisica.objects.create(identificador="004")
        produto_inicial = Produto.objects.create(
            nome="Produto inicial",
            preco_centavos=100,
        )
        registrar_primeiro_lancamento(
            garcom.pk,
            "004",
            produto_inicial.pk,
            1,
            "preparar-adicional",
        )
        nome_produto = "PRODUTO-ADICIONAL-SENTINELA"
        produto_adicional = Produto.objects.create(
            nome=nome_produto,
            preco_centavos=76_543_210,
        )

        with capturar_jsonl_aplicacao() as fluxo:
            with self.captureOnCommitCallbacks(execute=True):
                resultado = registrar_lancamento_adicional(
                    garcom.pk,
                    "004",
                    produto_adicional.pk,
                    876_543,
                    "adicional-correlacionavel",
                )

        operacao = next(
            json.loads(linha)
            for linha in fluxo.getvalue().splitlines()
            if json.loads(linha)["event"] == "operacao_dominio_confirmada"
        )
        self.assertEqual(
            operacao["operation"],
            "REGISTRAR_LANCAMENTO_ADICIONAL",
        )
        self.assertEqual(operacao["atendimento_id"], resultado.atendimento_id)
        self.assertEqual(operacao["lancamento_id"], resultado.lancamento_id)
        self.assertNotIn(nome_produto, fluxo.getvalue())
        self.assertNotIn("876543", fluxo.getvalue())
        self.assertNotIn("76543210", fluxo.getvalue())

    def test_fechamento_confirmado_registra_ids_sem_resumo_de_consumo(self):
        garcom = UsuarioOperacional.objects.create(
            nome="GARCOM-NOME-SENTINELA",
            papel=UsuarioOperacional.Papel.GARCOM,
        )
        caixa = UsuarioOperacional.objects.create(
            nome="CAIXA-NOME-SENTINELA",
            papel=UsuarioOperacional.Papel.CAIXA,
        )
        ComandaFisica.objects.create(identificador="005")
        produto = Produto.objects.create(
            nome="PRODUTO-FECHAMENTO-SENTINELA",
            preco_centavos=65_432_109,
        )
        registrar_primeiro_lancamento(
            garcom.pk,
            "005",
            produto.pk,
            765_432,
            "preparar-fechamento",
        )
        atendimento = Atendimento.objects.get()
        revisao = calcular_revisao_fechamento(atendimento)

        with capturar_jsonl_aplicacao() as fluxo:
            with self.captureOnCommitCallbacks(execute=True):
                resultado = fechar_atendimento(
                    caixa.pk,
                    atendimento.pk,
                    revisao,
                    "fechamento-correlacionavel",
                )

        operacao = next(
            json.loads(linha)
            for linha in fluxo.getvalue().splitlines()
            if json.loads(linha)["event"] == "operacao_dominio_confirmada"
        )
        self.assertEqual(operacao["operation"], "FECHAR_ATENDIMENTO")
        self.assertEqual(operacao["atendimento_id"], resultado.atendimento_id)
        self.assertEqual(operacao["usuario_operacional_id"], caixa.pk)
        conteudo_log = fluxo.getvalue()
        self.assertNotIn("PRODUTO-FECHAMENTO-SENTINELA", conteudo_log)
        self.assertNotIn("765432", conteudo_log)
        self.assertNotIn("65432109", conteudo_log)
        self.assertNotIn("CAIXA-NOME-SENTINELA", conteudo_log)


class EventosPosCommitTests(TransactionTestCase):
    def setUp(self):
        self.garcom = UsuarioOperacional.objects.create(
            nome="Garçom transacional",
            papel=UsuarioOperacional.Papel.GARCOM,
        )
        ComandaFisica.objects.create(identificador="101")
        self.produto = Produto.objects.create(
            nome="Produto transacional",
            preco_centavos=700,
        )

    def test_rollback_externo_nao_emite_evento_de_sucesso(self):
        with capturar_jsonl_aplicacao() as fluxo:
            with self.assertRaisesRegex(RuntimeError, "rollback externo"):
                with transaction.atomic():
                    registrar_primeiro_lancamento(
                        self.garcom.pk,
                        "101",
                        self.produto.pk,
                        1,
                        "operacao-revertida",
                    )
                    raise RuntimeError("rollback externo")

        self.assertNotIn("operacao_dominio_confirmada", fluxo.getvalue())
        self.assertEqual(Atendimento.objects.count(), 0)
        self.assertEqual(Lancamento.objects.count(), 0)

    def test_commit_efetivo_emite_evento_de_sucesso(self):
        with capturar_jsonl_aplicacao() as fluxo:
            resultado = registrar_primeiro_lancamento(
                self.garcom.pk,
                "101",
                self.produto.pk,
                1,
                "operacao-confirmada",
            )

        registro = json.loads(fluxo.getvalue())
        self.assertEqual(registro["event"], "operacao_dominio_confirmada")
        self.assertEqual(registro["atendimento_id"], resultado.atendimento_id)
        self.assertEqual(Atendimento.objects.count(), 1)
        self.assertEqual(Lancamento.objects.count(), 1)

    def test_falha_do_logger_apos_commit_preserva_resultado(self):
        logger = logging.getLogger("restaurante")
        handlers_originais = logger.handlers[:]
        propagacao_original = logger.propagate
        logger.handlers = [HandlerFalho()]
        logger.propagate = False
        try:
            resultado = registrar_primeiro_lancamento(
                self.garcom.pk,
                "101",
                self.produto.pk,
                1,
                "logger-falha-depois-do-commit",
            )
        finally:
            logger.handlers = handlers_originais
            logger.propagate = propagacao_original

        self.assertEqual(Atendimento.objects.count(), 1)
        self.assertEqual(Lancamento.objects.count(), 1)
        self.assertEqual(resultado.lancamento_id, Lancamento.objects.get().pk)
