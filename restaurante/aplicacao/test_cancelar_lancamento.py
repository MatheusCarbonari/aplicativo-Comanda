from datetime import timedelta

from django.db import DatabaseError, IntegrityError, OperationalError, connection
from django.test import TestCase

from restaurante.aplicacao.cancelar_lancamento import (
    AtendimentoEncerrado,
    DescricaoCancelamentoInvalida,
    LancamentoJaCancelado,
    LancamentoNaoEncontrado,
    MotivoCancelamentoInvalido,
    cancelar_lancamento,
)
from restaurante.aplicacao.contencao_persistencia import (
    PersistenciaTemporariamenteIndisponivel,
)
from restaurante.aplicacao.idempotencia import ConflitoIdempotencia
from restaurante.aplicacao.registrar_lancamento_adicional import (
    registrar_lancamento_adicional,
)
from restaurante.aplicacao.usuarios_operacionais import PapelNaoPermitido
from restaurante.persistencia.models import (
    Atendimento,
    CancelamentoLancamento,
    ComandaFisica,
    Lancamento,
    Produto,
    RegistroIdempotencia,
    UsuarioOperacional,
)


class CancelarLancamentoTests(TestCase):
    def setUp(self):
        self.garcom_1 = UsuarioOperacional.objects.create(
            nome="Garçom 1",
            papel=UsuarioOperacional.Papel.GARCOM,
        )
        self.garcom_2 = UsuarioOperacional.objects.create(
            nome="Garçom 2",
            papel=UsuarioOperacional.Papel.GARCOM,
        )
        self.caixa = UsuarioOperacional.objects.create(
            nome="Caixa 1",
            papel=UsuarioOperacional.Papel.CAIXA,
        )
        self.comanda = ComandaFisica.objects.create(identificador="001")
        self.atendimento = Atendimento.objects.create(comanda=self.comanda)
        self.produto = Produto.objects.create(nome="Café", preco_centavos=600)
        self.lancamento = Lancamento.objects.create(
            atendimento=self.atendimento,
            produto=self.produto,
            quantidade=2,
            preco_unitario_centavos=600,
            autor=self.garcom_1,
        )

    def test_garcom_cancela_lancamento_proprio_sem_alterar_original(self):
        original = {
            "atendimento_id": self.lancamento.atendimento_id,
            "produto_id": self.lancamento.produto_id,
            "quantidade": self.lancamento.quantidade,
            "preco_unitario_centavos": self.lancamento.preco_unitario_centavos,
            "autor_id": self.lancamento.autor_id,
            "horario": self.lancamento.horario,
        }

        resultado = cancelar_lancamento(
            self.garcom_1.pk,
            self.lancamento.pk,
            "DUPLICADO",
            "",
            "cancelamento-proprio",
        )

        cancelamento = CancelamentoLancamento.objects.get()
        self.lancamento.refresh_from_db()
        self.assertEqual(resultado.cancelamento_id, cancelamento.pk)
        self.assertEqual(cancelamento.lancamento, self.lancamento)
        self.assertEqual(cancelamento.motivo, "DUPLICADO")
        self.assertEqual(cancelamento.descricao, "")
        self.assertEqual(cancelamento.autor, self.garcom_1)
        self.assertEqual(cancelamento.horario.utcoffset(), timedelta(0))
        self.assertEqual(
            {
                "atendimento_id": self.lancamento.atendimento_id,
                "produto_id": self.lancamento.produto_id,
                "quantidade": self.lancamento.quantidade,
                "preco_unitario_centavos": (
                    self.lancamento.preco_unitario_centavos
                ),
                "autor_id": self.lancamento.autor_id,
                "horario": self.lancamento.horario,
            },
            original,
        )

    def test_aceita_cada_motivo_aprovado(self):
        cenarios = (
            (CancelamentoLancamento.Motivo.DUPLICADO, ""),
            (CancelamentoLancamento.Motivo.PRODUTO_INCORRETO, ""),
            (CancelamentoLancamento.Motivo.QUANTIDADE_INCORRETA, ""),
            (CancelamentoLancamento.Motivo.DESISTENCIA, ""),
            (CancelamentoLancamento.Motivo.OUTRO, "Cliente mudou o pedido"),
        )
        for indice, (motivo, descricao) in enumerate(cenarios):
            with self.subTest(motivo=motivo):
                lancamento = Lancamento.objects.create(
                    atendimento=self.atendimento,
                    produto=self.produto,
                    quantidade=1,
                    preco_unitario_centavos=600,
                    autor=self.garcom_1,
                )

                cancelar_lancamento(
                    self.garcom_1.pk,
                    lancamento.pk,
                    motivo,
                    descricao,
                    f"motivo-{indice}",
                )

                cancelamento = CancelamentoLancamento.objects.get(
                    lancamento=lancamento
                )
                self.assertEqual(cancelamento.motivo, motivo)
                self.assertEqual(cancelamento.descricao, descricao)

    def test_outro_exige_descricao_e_motivo_deve_ser_aprovado(self):
        for indice, descricao in enumerate((None, "", "   ")):
            with self.subTest(descricao=descricao):
                with self.assertRaises(DescricaoCancelamentoInvalida):
                    cancelar_lancamento(
                        self.garcom_1.pk,
                        self.lancamento.pk,
                        CancelamentoLancamento.Motivo.OUTRO,
                        descricao,
                        f"outro-sem-descricao-{indice}",
                    )
        with self.assertRaises(MotivoCancelamentoInvalido):
            cancelar_lancamento(
                self.garcom_1.pk,
                self.lancamento.pk,
                "MOTIVO_INVENTADO",
                "",
                "motivo-invalido",
            )

        self.assertEqual(CancelamentoLancamento.objects.count(), 0)
        self.assertEqual(RegistroIdempotencia.objects.count(), 0)

    def test_garcom_cancela_lancamento_de_outro_garcom(self):
        resultado = cancelar_lancamento(
            self.garcom_2.pk,
            self.lancamento.pk,
            CancelamentoLancamento.Motivo.DESISTENCIA,
            "",
            "autoria-cruzada",
        )

        cancelamento = CancelamentoLancamento.objects.get()
        self.assertEqual(cancelamento.autor, self.garcom_2)
        self.assertEqual(resultado.autor, "Garçom 2")
        self.assertEqual(self.lancamento.autor, self.garcom_1)

    def test_caixa_atendimento_encerrado_e_lancamento_inexistente_rejeitados(
        self,
    ):
        with self.assertRaises(PapelNaoPermitido):
            cancelar_lancamento(
                self.caixa.pk,
                self.lancamento.pk,
                CancelamentoLancamento.Motivo.DUPLICADO,
                "",
                "caixa",
            )

        self.atendimento.estado = Atendimento.Estado.ENCERRADO
        self.atendimento.save(update_fields=["estado"])
        with self.assertRaises(AtendimentoEncerrado):
            cancelar_lancamento(
                self.garcom_1.pk,
                self.lancamento.pk,
                CancelamentoLancamento.Motivo.DUPLICADO,
                "",
                "encerrado",
            )

        with self.assertRaises(LancamentoNaoEncontrado):
            cancelar_lancamento(
                self.garcom_1.pk,
                999_999,
                CancelamentoLancamento.Motivo.DUPLICADO,
                "",
                "inexistente",
            )

        self.assertEqual(CancelamentoLancamento.objects.count(), 0)
        self.assertEqual(RegistroIdempotencia.objects.count(), 0)

    def test_idempotencia_retorna_original_e_nova_chave_nao_recancela(self):
        argumentos = (
            self.garcom_1.pk,
            self.lancamento.pk,
            CancelamentoLancamento.Motivo.PRODUTO_INCORRETO,
            "",
            "cancelamento-idempotente",
        )
        primeiro = cancelar_lancamento(*argumentos)
        repetido = cancelar_lancamento(*argumentos)

        self.assertEqual(repetido, primeiro)
        self.assertEqual(CancelamentoLancamento.objects.count(), 1)
        with self.assertRaises(LancamentoJaCancelado):
            cancelar_lancamento(
                self.garcom_2.pk,
                self.lancamento.pk,
                CancelamentoLancamento.Motivo.DUPLICADO,
                "",
                "outra-chave",
            )
        with self.assertRaises(ConflitoIdempotencia):
            cancelar_lancamento(
                self.garcom_1.pk,
                self.lancamento.pk,
                CancelamentoLancamento.Motivo.QUANTIDADE_INCORRETA,
                "",
                "cancelamento-idempotente",
            )
        self.assertEqual(CancelamentoLancamento.objects.count(), 1)

    def test_cancelado_deixa_total_e_novos_totais(self):
        pizza = Produto.objects.create(nome="Pizza", preco_centavos=4500)
        Lancamento.objects.create(
            atendimento=self.atendimento,
            produto=pizza,
            quantidade=1,
            preco_unitario_centavos=4500,
            autor=self.garcom_2,
        )

        cancelamento = cancelar_lancamento(
            self.garcom_1.pk,
            self.lancamento.pk,
            CancelamentoLancamento.Motivo.QUANTIDADE_INCORRETA,
            "",
            "retirar-do-total",
        )
        adicional = registrar_lancamento_adicional(
            self.garcom_2.pk,
            "001",
            self.produto.pk,
            1,
            "total-apos-cancelamento",
        )

        self.assertEqual(cancelamento.total_centavos, 4500)
        self.assertEqual(adicional.total_centavos, 5100)

    def test_falha_apos_cancelamento_reverte_toda_operacao(self):
        def falhar_ao_confirmar_resultado(execute, sql, params, many, context):
            sql_normalizado = sql.lower()
            if (
                sql_normalizado.startswith("update")
                and '"persistencia_registroidempotencia"' in sql_normalizado
            ):
                raise DatabaseError("falha simulada ao confirmar resultado")
            return execute(sql, params, many, context)

        with connection.execute_wrapper(falhar_ao_confirmar_resultado):
            with self.assertRaisesRegex(
                DatabaseError,
                "falha simulada ao confirmar resultado",
            ):
                cancelar_lancamento(
                    self.garcom_1.pk,
                    self.lancamento.pk,
                    CancelamentoLancamento.Motivo.DUPLICADO,
                    "",
                    "rollback-cancelamento",
                )

        self.assertEqual(CancelamentoLancamento.objects.count(), 0)
        self.assertEqual(RegistroIdempotencia.objects.count(), 0)
        self.assertTrue(Lancamento.objects.filter(pk=self.lancamento.pk).exists())

    def test_integrity_error_nao_relacionado_nao_vira_ja_cancelado(self):
        def falhar_na_insercao(execute, sql, params, many, context):
            if 'insert into "persistencia_cancelamentolancamento"' in sql.lower():
                raise IntegrityError("constraint simulada não relacionada")
            return execute(sql, params, many, context)

        with connection.execute_wrapper(falhar_na_insercao):
            with self.assertRaisesRegex(
                IntegrityError,
                "constraint simulada não relacionada",
            ):
                cancelar_lancamento(
                    self.garcom_1.pk,
                    self.lancamento.pk,
                    CancelamentoLancamento.Motivo.DUPLICADO,
                    "",
                    "integridade-nao-relacionada",
                )

        self.assertEqual(CancelamentoLancamento.objects.count(), 0)
        self.assertEqual(RegistroIdempotencia.objects.count(), 0)

    def test_contencao_transitoria_tenta_novamente_sem_duplicar(self):
        tentativas = 0

        def bloquear_primeira_insercao(execute, sql, params, many, context):
            nonlocal tentativas
            if 'insert into "persistencia_cancelamentolancamento"' in sql.lower():
                tentativas += 1
                if tentativas == 1:
                    raise OperationalError("database is locked")
            return execute(sql, params, many, context)

        with connection.execute_wrapper(bloquear_primeira_insercao):
            resultado = cancelar_lancamento(
                self.garcom_1.pk,
                self.lancamento.pk,
                CancelamentoLancamento.Motivo.DUPLICADO,
                "",
                "retry-cancelamento",
            )

        self.assertEqual(tentativas, 2)
        self.assertEqual(CancelamentoLancamento.objects.count(), 1)
        self.assertEqual(RegistroIdempotencia.objects.count(), 1)
        self.assertEqual(
            CancelamentoLancamento.objects.get().pk,
            resultado.cancelamento_id,
        )

    def test_contencao_persistente_falha_controlada_sem_estado_parcial(self):
        tentativas = 0

        def bloquear_insercao(execute, sql, params, many, context):
            nonlocal tentativas
            if 'insert into "persistencia_cancelamentolancamento"' in sql.lower():
                tentativas += 1
                raise OperationalError("database is locked")
            return execute(sql, params, many, context)

        with connection.execute_wrapper(bloquear_insercao):
            with self.assertRaises(PersistenciaTemporariamenteIndisponivel):
                cancelar_lancamento(
                    self.garcom_1.pk,
                    self.lancamento.pk,
                    CancelamentoLancamento.Motivo.DUPLICADO,
                    "",
                    "contencao-persistente-cancelamento",
                )

        self.assertEqual(tentativas, 2)
        self.assertEqual(CancelamentoLancamento.objects.count(), 0)
        self.assertEqual(RegistroIdempotencia.objects.count(), 0)
