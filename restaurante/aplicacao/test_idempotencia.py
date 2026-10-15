from concurrent.futures import ThreadPoolExecutor
from threading import Barrier, Lock
from unittest.mock import patch

from django.db import (
    IntegrityError,
    close_old_connections,
    connection,
    transaction,
)
from django.test import TestCase, TransactionTestCase

from restaurante.aplicacao.idempotencia import (
    ConflitoIdempotencia,
    calcular_hash_conteudo,
    executar_idempotente,
)
from restaurante.persistencia.models import ComandaFisica, RegistroIdempotencia


class ExecutarIdempotenteTests(TestCase):
    def test_chave_nova_executa_e_persiste_resultado(self):
        execucoes = 0

        def executar():
            nonlocal execucoes
            execucoes += 1
            return {"identificador": 15}

        resultado = executar_idempotente(
            chave="tentativa-1",
            operacao="OPERACAO_DE_TESTE",
            conteudo={"quantidade": 1, "produto": 7},
            executar=executar,
        )

        registro = RegistroIdempotencia.objects.get()
        self.assertEqual(resultado, {"identificador": 15})
        self.assertEqual(execucoes, 1)
        self.assertEqual(registro.chave, "tentativa-1")
        self.assertEqual(registro.operacao, "OPERACAO_DE_TESTE")
        self.assertEqual(len(registro.hash_conteudo), 64)
        self.assertEqual(registro.resultado, resultado)

    def test_repeticao_compativel_retorna_resultado_sem_executar_novamente(self):
        execucoes = 0

        def executar():
            nonlocal execucoes
            execucoes += 1
            return {"identificador": 15}

        argumentos = {
            "chave": "tentativa-1",
            "operacao": "OPERACAO_DE_TESTE",
            "conteudo": {"produto": 7, "quantidade": 1},
            "executar": executar,
        }
        primeiro = executar_idempotente(**argumentos)
        segundo = executar_idempotente(**argumentos)

        self.assertEqual(primeiro, segundo)
        self.assertEqual(execucoes, 1)
        self.assertEqual(RegistroIdempotencia.objects.count(), 1)

    def test_mesma_chave_rejeita_conteudo_ou_operacao_diferente(self):
        executar_idempotente(
            chave="tentativa-1",
            operacao="OPERACAO_A",
            conteudo={"produto": 7, "quantidade": 1},
            executar=lambda: {"identificador": 15},
        )

        incompatibilidades = (
            ("OPERACAO_A", {"produto": 8, "quantidade": 1}),
            ("OPERACAO_B", {"produto": 7, "quantidade": 1}),
        )
        for operacao, conteudo in incompatibilidades:
            with self.subTest(operacao=operacao, conteudo=conteudo):
                with self.assertRaises(ConflitoIdempotencia):
                    executar_idempotente(
                        chave="tentativa-1",
                        operacao=operacao,
                        conteudo=conteudo,
                        executar=lambda: {"identificador": 16},
                    )

        self.assertEqual(RegistroIdempotencia.objects.count(), 1)

    def test_chaves_diferentes_permitem_conteudo_igual(self):
        for chave, identificador in (("tentativa-1", 15), ("tentativa-2", 16)):
            executar_idempotente(
                chave=chave,
                operacao="OPERACAO_DE_TESTE",
                conteudo={"produto": 7, "quantidade": 1},
                executar=lambda identificador=identificador: {
                    "identificador": identificador
                },
            )

        self.assertEqual(RegistroIdempotencia.objects.count(), 2)

    def test_hash_e_deterministico_independentemente_da_ordem_dos_campos(self):
        self.assertEqual(
            calcular_hash_conteudo({"produto": 7, "quantidade": 1}),
            calcular_hash_conteudo({"quantidade": 1, "produto": 7}),
        )

    def test_falha_na_operacao_nao_confirma_registro(self):
        def falhar():
            ComandaFisica.objects.create(identificador="001")
            raise RuntimeError("falha simulada")

        with self.assertRaisesRegex(RuntimeError, "falha simulada"):
            executar_idempotente(
                chave="tentativa-1",
                operacao="OPERACAO_DE_TESTE",
                conteudo={"comanda": "001"},
                executar=falhar,
            )

        self.assertEqual(ComandaFisica.objects.count(), 0)
        self.assertEqual(RegistroIdempotencia.objects.count(), 0)

    def test_falha_ao_registrar_nao_confirma_mutacao(self):
        execucoes = 0

        def executar():
            nonlocal execucoes
            execucoes += 1
            ComandaFisica.objects.create(identificador="001")
            return {"comanda": "001"}

        salvar_original = RegistroIdempotencia.save

        def salvar(registro, *args, **kwargs):
            if kwargs.get("update_fields") == ["resultado"]:
                raise IntegrityError("falha não relacionada")
            return salvar_original(registro, *args, **kwargs)

        with patch.object(RegistroIdempotencia, "save", new=salvar):
            with self.assertRaises(IntegrityError):
                executar_idempotente(
                    chave="tentativa-1",
                    operacao="OPERACAO_DE_TESTE",
                    conteudo={"comanda": "001"},
                    executar=executar,
                )

        self.assertEqual(execucoes, 1)
        self.assertEqual(ComandaFisica.objects.count(), 0)
        self.assertEqual(RegistroIdempotencia.objects.count(), 0)


class PersistenciaIdempotenciaTests(TransactionTestCase):
    def test_chave_possui_unicidade_protegida_pelo_sqlite(self):
        RegistroIdempotencia.objects.create(
            chave="tentativa-unica",
            operacao="OPERACAO_A",
            hash_conteudo="a" * 64,
            resultado={"identificador": 1},
        )

        with self.assertRaises(IntegrityError), transaction.atomic():
            RegistroIdempotencia.objects.create(
                chave="tentativa-unica",
                operacao="OPERACAO_A",
                hash_conteudo="a" * 64,
                resultado={"identificador": 2},
            )

        self.assertEqual(RegistroIdempotencia.objects.count(), 1)

    def test_mesma_chave_simultanea_executa_mutacao_uma_vez(self):
        inicio = Barrier(2)
        bloqueio = Lock()
        execucoes = 0

        def tentar():
            nonlocal execucoes
            close_old_connections()
            inicio.wait()

            def executar():
                nonlocal execucoes
                with bloqueio:
                    execucoes += 1
                ComandaFisica.objects.create(identificador="001")
                return {"comanda": "001"}

            try:
                return executar_idempotente(
                    chave="tentativa-concorrente",
                    operacao="OPERACAO_DE_TESTE",
                    conteudo={"comanda": "001"},
                    executar=executar,
                )
            finally:
                close_old_connections()

        with ThreadPoolExecutor(max_workers=2) as executor:
            resultados = list(executor.map(lambda _: tentar(), range(2)))

        self.assertEqual(
            resultados,
            [{"comanda": "001"}, {"comanda": "001"}],
        )
        self.assertEqual(execucoes, 1)
        self.assertEqual(ComandaFisica.objects.count(), 1)
        self.assertEqual(RegistroIdempotencia.objects.count(), 1)

    def test_resultado_permanece_disponivel_apos_reabrir_conexao(self):
        executar_idempotente(
            chave="tentativa-1",
            operacao="OPERACAO_DE_TESTE",
            conteudo={"produto": 7},
            executar=lambda: {"identificador": 15},
        )
        connection.close()

        resultado = executar_idempotente(
            chave="tentativa-1",
            operacao="OPERACAO_DE_TESTE",
            conteudo={"produto": 7},
            executar=lambda: self.fail("não deveria executar novamente"),
        )

        self.assertEqual(resultado, {"identificador": 15})
