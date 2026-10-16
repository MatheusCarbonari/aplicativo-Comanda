from django.db import (
    DatabaseError,
    IntegrityError,
    OperationalError,
    connection,
    transaction,
)
from django.test import TestCase

from restaurante.aplicacao.contencao_persistencia import (
    PersistenciaTemporariamenteIndisponivel,
)
from restaurante.aplicacao.registrar_primeiro_lancamento import (
    registrar_primeiro_lancamento,
)
from restaurante.aplicacao.registrar_lancamento_adicional import (
    registrar_lancamento_adicional,
)
from restaurante.persistencia.models import (
    Atendimento,
    ComandaFisica,
    Lancamento,
    Produto,
    RegistroIdempotencia,
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
            "persistencia-primeiro",
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
                    "rollback-atendimento",
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
                    "integridade-lancamento",
                )

        self.assertEqual(Atendimento.objects.count(), 0)
        self.assertEqual(Lancamento.objects.count(), 0)

    def test_integrity_error_nao_relacionado_ao_indice_de_abertura_e_propagado(
        self,
    ):
        def falhar_na_insercao(execute, sql, params, many, context):
            if 'insert into "persistencia_atendimento"' in sql.lower():
                raise IntegrityError("constraint simulada do atendimento")
            return execute(sql, params, many, context)

        with connection.execute_wrapper(falhar_na_insercao):
            with self.assertRaisesRegex(
                IntegrityError,
                "constraint simulada do atendimento",
            ):
                registrar_primeiro_lancamento(
                    self.garcom.pk,
                    "001",
                    self.produto.pk,
                    1,
                    "integridade-atendimento",
                )

        self.assertEqual(Atendimento.objects.count(), 0)
        self.assertEqual(Lancamento.objects.count(), 0)

    def test_contencao_sqlite_transitoria_repete_sem_duplicar(self):
        tentativas = 0

        def conter_primeira_insercao(execute, sql, params, many, context):
            nonlocal tentativas
            if 'insert into "persistencia_atendimento"' in sql.lower():
                tentativas += 1
                if tentativas == 1:
                    raise OperationalError("database is locked")
            return execute(sql, params, many, context)

        with connection.execute_wrapper(conter_primeira_insercao):
            resultado = registrar_primeiro_lancamento(
                self.garcom.pk,
                "001",
                self.produto.pk,
                1,
                "contencao-transitoria",
            )

        self.assertEqual(tentativas, 2)
        self.assertEqual(Atendimento.objects.get().pk, resultado.atendimento_id)
        self.assertEqual(Lancamento.objects.get().pk, resultado.lancamento_id)
        self.assertEqual(RegistroIdempotencia.objects.count(), 1)

    def test_contencao_sqlite_persistente_falha_sem_estado_parcial(self):
        tentativas = 0

        def conter_insercao(execute, sql, params, many, context):
            nonlocal tentativas
            if 'insert into "persistencia_atendimento"' in sql.lower():
                tentativas += 1
                raise OperationalError("database is locked")
            return execute(sql, params, many, context)

        with connection.execute_wrapper(conter_insercao):
            with self.assertRaises(PersistenciaTemporariamenteIndisponivel):
                registrar_primeiro_lancamento(
                    self.garcom.pk,
                    "001",
                    self.produto.pk,
                    1,
                    "contencao-persistente",
                )

        self.assertEqual(tentativas, 2)
        self.assertEqual(Atendimento.objects.count(), 0)
        self.assertEqual(Lancamento.objects.count(), 0)
        self.assertEqual(RegistroIdempotencia.objects.count(), 0)

    def test_sqlite_preserva_produto_repetido_e_autores_no_mesmo_atendimento(self):
        outro_garcom = UsuarioOperacional.objects.create(
            nome="Garçom 2",
            papel=UsuarioOperacional.Papel.GARCOM,
        )
        atendimento = Atendimento.objects.create(comanda=self.comanda)

        registrar_lancamento_adicional(
            self.garcom.pk,
            "001",
            self.produto.pk,
            1,
            "adicional-1",
        )
        registrar_lancamento_adicional(
            outro_garcom.pk,
            "001",
            self.produto.pk,
            2,
            "adicional-2",
        )

        lancamentos = list(atendimento.lancamentos.order_by("pk"))
        self.assertEqual(len(lancamentos), 2)
        self.assertEqual(
            [lancamento.produto for lancamento in lancamentos],
            [self.produto, self.produto],
        )
        self.assertEqual(
            [lancamento.autor for lancamento in lancamentos],
            [self.garcom, outro_garcom],
        )
        self.assertEqual(
            [lancamento.quantidade for lancamento in lancamentos],
            [1, 2],
        )
        self.assertEqual(
            [
                lancamento.preco_unitario_centavos
                for lancamento in lancamentos
            ],
            [2000, 2000],
        )
