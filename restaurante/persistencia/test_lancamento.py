from django.db import DatabaseError, IntegrityError, connection, transaction
from django.test import TestCase

from restaurante.aplicacao.registrar_primeiro_lancamento import (
    registrar_primeiro_lancamento,
)
from restaurante.persistencia.models import (
    Atendimento,
    ComandaFisica,
    Lancamento,
    Produto,
    UsuarioOperacional,
)


class LancamentoPersistenciaTests(TestCase):
    def setUp(self):
        self.garcom = UsuarioOperacional.objects.create(
            nome="Garçom 1",
            papel=UsuarioOperacional.Papel.GARCOM,
        )
        self.comanda = ComandaFisica.objects.create(identificador="001")
        self.produto = Produto.objects.create(
            nome="Batata frita",
            preco_centavos=2000,
        )

    def test_relacoes_e_preco_snapshot_sao_persistidos(self):
        resultado = registrar_primeiro_lancamento(
            self.garcom.pk,
            "001",
            self.produto.pk,
            2,
        )

        lancamento = Lancamento.objects.get(pk=resultado.lancamento_id)
        self.assertEqual(lancamento.atendimento.comanda, self.comanda)
        self.assertEqual(lancamento.produto, self.produto)
        self.assertEqual(lancamento.autor, self.garcom)
        self.assertEqual(lancamento.quantidade, 2)
        self.assertEqual(lancamento.preco_unitario_centavos, 2000)

    def test_sqlite_rejeita_quantidade_nao_positiva(self):
        atendimento = Atendimento.objects.create(comanda=self.comanda)

        with self.assertRaises(IntegrityError), transaction.atomic():
            Lancamento.objects.create(
                atendimento=atendimento,
                produto=self.produto,
                quantidade=0,
                preco_unitario_centavos=2000,
                autor=self.garcom,
            )

        self.assertEqual(Lancamento.objects.count(), 0)

    def test_falha_ao_inserir_lancamento_reverte_atendimento(self):
        def falhar_na_insercao(execute, sql, params, many, context):
            if 'insert into "persistencia_lancamento"' in sql.lower():
                raise DatabaseError("falha simulada na persistência")
            return execute(sql, params, many, context)

        with connection.execute_wrapper(falhar_na_insercao):
            with self.assertRaises(DatabaseError):
                registrar_primeiro_lancamento(
                    self.garcom.pk,
                    "001",
                    self.produto.pk,
                    1,
                )

        self.assertEqual(Atendimento.objects.count(), 0)
        self.assertEqual(Lancamento.objects.count(), 0)

    def test_integrity_error_do_lancamento_nao_vira_conflito_de_atendimento(self):
        def falhar_na_insercao(execute, sql, params, many, context):
            if 'insert into "persistencia_lancamento"' in sql.lower():
                raise IntegrityError("constraint simulada do lançamento")
            return execute(sql, params, many, context)

        with connection.execute_wrapper(falhar_na_insercao):
            with self.assertRaisesRegex(
                IntegrityError,
                "constraint simulada do lançamento",
            ):
                registrar_primeiro_lancamento(
                    self.garcom.pk,
                    "001",
                    self.produto.pk,
                    1,
                )

        self.assertEqual(Atendimento.objects.count(), 0)
        self.assertEqual(Lancamento.objects.count(), 0)
