from concurrent.futures import ThreadPoolExecutor
from threading import Event

from django.db import (
    IntegrityError,
    OperationalError,
    close_old_connections,
    connection,
    transaction,
)
from django.test import TransactionTestCase

from restaurante.aplicacao.fechar_atendimento import (
    RevisaoFechamentoDesatualizada,
    fechar_atendimento,
)
from restaurante.aplicacao.registrar_lancamento_adicional import (
    AtendimentoAbertoNaoEncontrado,
    registrar_lancamento_adicional,
)
from restaurante.aplicacao.revisao_fechamento import (
    calcular_revisao_fechamento,
)
from restaurante.dominio.lancamentos import calcular_total_atendimento
from restaurante.persistencia.conflitos_sqlite import (
    e_contencao_transitoria,
    e_lancamento_em_atendimento_encerrado,
)
from restaurante.persistencia.models import (
    Atendimento,
    ComandaFisica,
    Lancamento,
    Produto,
    RegistroIdempotencia,
    UsuarioOperacional,
)


class CorridaLancamentoFechamentoTests(TransactionTestCase):
    repeticoes = 5

    def setUp(self):
        self.garcom = UsuarioOperacional.objects.create(
            nome="Garçom 1",
            papel=UsuarioOperacional.Papel.GARCOM,
        )
        self.caixa = UsuarioOperacional.objects.create(
            nome="Caixa 1",
            papel=UsuarioOperacional.Papel.CAIXA,
        )
        self.produto = Produto.objects.create(nome="Café", preco_centavos=600)

    def test_fechamento_confirmado_primeiro_rejeita_lancamento_concorrente(
        self,
    ):
        for repeticao in range(self.repeticoes):
            with self.subTest(repeticao=repeticao):
                comanda, atendimento = self._criar_atendimento(repeticao)
                revisao = calcular_revisao_fechamento(atendimento)
                fechamento_escreveu = Event()
                lancamento_encontrou_contencao = Event()
                fechamento_confirmou = Event()

                def pausar_fechamento(execute, sql, params, many, context):
                    resultado = execute(sql, params, many, context)
                    if (
                        sql.lower().startswith("update")
                        and '"persistencia_atendimento"' in sql.lower()
                    ):
                        fechamento_escreveu.set()
                        if not lancamento_encontrou_contencao.wait(10):
                            raise AssertionError(
                                "O Lançamento não disputou a escrita."
                            )
                    return resultado

                def observar_lancamento(execute, sql, params, many, context):
                    try:
                        return execute(sql, params, many, context)
                    except OperationalError as erro:
                        if e_contencao_transitoria(erro):
                            lancamento_encontrou_contencao.set()
                            if not fechamento_confirmou.wait(10):
                                raise AssertionError(
                                    "O Fechamento não confirmou a tempo."
                                ) from erro
                        raise

                def fechar():
                    close_old_connections()
                    self._desabilitar_espera_sqlite()
                    try:
                        with connection.execute_wrapper(pausar_fechamento):
                            return fechar_atendimento(
                                self.caixa.pk,
                                atendimento.pk,
                                revisao,
                                f"fechar-primeiro-{repeticao}",
                            )
                    finally:
                        fechamento_confirmou.set()
                        close_old_connections()

                def lancar():
                    close_old_connections()
                    self._desabilitar_espera_sqlite()
                    if not fechamento_escreveu.wait(10):
                        raise AssertionError("O Fechamento não iniciou a escrita.")
                    try:
                        with connection.execute_wrapper(observar_lancamento):
                            registrar_lancamento_adicional(
                                self.garcom.pk,
                                comanda.identificador,
                                self.produto.pk,
                                2,
                                f"lancar-depois-{repeticao}",
                            )
                    except AtendimentoAbertoNaoEncontrado:
                        return "rejeitado"
                    finally:
                        close_old_connections()
                    return "confirmado"

                with ThreadPoolExecutor(max_workers=2) as executor:
                    fechamento_futuro = executor.submit(fechar)
                    lancamento_futuro = executor.submit(lancar)
                    resultado_fechamento = fechamento_futuro.result()
                    resultado_lancamento = lancamento_futuro.result()

                atendimento.refresh_from_db()
                self.assertEqual(
                    atendimento.estado,
                    Atendimento.Estado.ENCERRADO,
                )
                self.assertEqual(resultado_fechamento.estado, "ENCERRADO")
                self.assertEqual(resultado_lancamento, "rejeitado")
                self.assertEqual(
                    Lancamento.objects.filter(atendimento=atendimento).count(),
                    1,
                )
                lancamento_original = Lancamento.objects.get(
                    atendimento=atendimento
                )
                self.assertEqual(lancamento_original.quantidade, 1)
                self.assertEqual(
                    lancamento_original.preco_unitario_centavos,
                    600,
                )
                self.assertLessEqual(
                    lancamento_original.horario,
                    atendimento.fechado_em,
                )
                self.assertEqual(
                    calcular_total_atendimento(
                        atendimento.lancamentos.validos().values_list(
                            "quantidade",
                            "preco_unitario_centavos",
                        )
                    ),
                    600,
                )
                self.assertTrue(
                    RegistroIdempotencia.objects.filter(
                        chave=f"fechar-primeiro-{repeticao}"
                    ).exists()
                )
                self.assertFalse(
                    RegistroIdempotencia.objects.filter(
                        chave=f"lancar-depois-{repeticao}"
                    ).exists()
                )

    def test_banco_impede_lancamento_associado_a_atendimento_encerrado(self):
        _, atendimento = self._criar_atendimento(100)
        atendimento.estado = Atendimento.Estado.ENCERRADO
        atendimento.fechado_por = self.caixa
        atendimento.save(update_fields=["estado", "fechado_por"])

        with self.assertRaises(IntegrityError) as erro_capturado:
            with transaction.atomic():
                Lancamento.objects.create(
                    atendimento=atendimento,
                    produto=self.produto,
                    quantidade=2,
                    preco_unitario_centavos=600,
                    autor=self.garcom,
                )

        self.assertTrue(
            e_lancamento_em_atendimento_encerrado(erro_capturado.exception)
        )
        self.assertEqual(
            Lancamento.objects.filter(atendimento=atendimento).count(),
            1,
        )

    def test_lancamento_confirmado_primeiro_invalida_fechamento_concorrente(
        self,
    ):
        for repeticao in range(self.repeticoes):
            with self.subTest(repeticao=repeticao):
                comanda, atendimento = self._criar_atendimento(
                    repeticao + 200
                )
                revisao_antiga = calcular_revisao_fechamento(atendimento)
                lancamento_escreveu = Event()
                fechamento_encontrou_contencao = Event()
                lancamento_confirmou = Event()

                def pausar_lancamento(execute, sql, params, many, context):
                    resultado = execute(sql, params, many, context)
                    if (
                        sql.lower().startswith("insert")
                        and '"persistencia_lancamento"' in sql.lower()
                    ):
                        lancamento_escreveu.set()
                        if not fechamento_encontrou_contencao.wait(10):
                            raise AssertionError(
                                "O Fechamento não disputou a escrita."
                            )
                    return resultado

                def observar_fechamento(execute, sql, params, many, context):
                    try:
                        return execute(sql, params, many, context)
                    except OperationalError as erro:
                        if e_contencao_transitoria(erro):
                            fechamento_encontrou_contencao.set()
                            if not lancamento_confirmou.wait(10):
                                raise AssertionError(
                                    "O Lançamento não confirmou a tempo."
                                ) from erro
                        raise

                def lancar():
                    close_old_connections()
                    self._desabilitar_espera_sqlite()
                    try:
                        with connection.execute_wrapper(pausar_lancamento):
                            return registrar_lancamento_adicional(
                                self.garcom.pk,
                                comanda.identificador,
                                self.produto.pk,
                                2,
                                f"lancar-primeiro-{repeticao}",
                            )
                    finally:
                        lancamento_confirmou.set()
                        close_old_connections()

                def fechar():
                    close_old_connections()
                    self._desabilitar_espera_sqlite()
                    if not lancamento_escreveu.wait(10):
                        raise AssertionError("O Lançamento não iniciou a escrita.")
                    try:
                        with connection.execute_wrapper(observar_fechamento):
                            fechar_atendimento(
                                self.caixa.pk,
                                atendimento.pk,
                                revisao_antiga,
                                f"fechar-depois-{repeticao}",
                            )
                    except RevisaoFechamentoDesatualizada:
                        return "revisao_desatualizada"
                    finally:
                        close_old_connections()
                    return "confirmado"

                with ThreadPoolExecutor(max_workers=2) as executor:
                    lancamento_futuro = executor.submit(lancar)
                    fechamento_futuro = executor.submit(fechar)
                    resultado_lancamento = lancamento_futuro.result()
                    resultado_fechamento = fechamento_futuro.result()

                atendimento.refresh_from_db()
                self.assertEqual(
                    atendimento.estado,
                    Atendimento.Estado.ABERTO,
                )
                self.assertEqual(resultado_lancamento.total_centavos, 1800)
                self.assertEqual(
                    resultado_fechamento,
                    "revisao_desatualizada",
                )
                self.assertEqual(
                    Lancamento.objects.filter(atendimento=atendimento).count(),
                    2,
                )
                self.assertTrue(
                    RegistroIdempotencia.objects.filter(
                        chave=f"lancar-primeiro-{repeticao}"
                    ).exists()
                )
                self.assertFalse(
                    RegistroIdempotencia.objects.filter(
                        chave=f"fechar-depois-{repeticao}"
                    ).exists()
                )

                revisao_atual = calcular_revisao_fechamento(atendimento)
                self.assertNotEqual(revisao_atual, revisao_antiga)
                fechar_atendimento(
                    self.caixa.pk,
                    atendimento.pk,
                    revisao_atual,
                    f"fechar-atual-{repeticao}",
                )

                atendimento.refresh_from_db()
                self.assertEqual(
                    atendimento.estado,
                    Atendimento.Estado.ENCERRADO,
                )
                self.assertEqual(
                    Lancamento.objects.filter(atendimento=atendimento).count(),
                    2,
                )

    def _criar_atendimento(self, repeticao):
        comanda = ComandaFisica.objects.create(
            identificador=f"corrida-{repeticao:03d}"
        )
        atendimento = Atendimento.objects.create(comanda=comanda)
        Lancamento.objects.create(
            atendimento=atendimento,
            produto=self.produto,
            quantidade=1,
            preco_unitario_centavos=600,
            autor=self.garcom,
        )
        return comanda, atendimento

    def _desabilitar_espera_sqlite(self):
        with connection.cursor() as cursor:
            cursor.execute("PRAGMA busy_timeout = 0")
