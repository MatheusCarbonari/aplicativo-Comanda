from datetime import UTC, datetime
from uuid import uuid4

from django.db import DatabaseError, connection
from django.db.models.deletion import ProtectedError
from django.test import TestCase

from restaurante.aplicacao.cancelar_lancamento import (
    AtendimentoEncerrado,
    cancelar_lancamento,
)
from restaurante.aplicacao.consultar_estado_comanda import (
    EstadoComanda,
    consultar_estado_comanda_caixa,
)
from restaurante.aplicacao.fechar_atendimento import (
    AtendimentoJaEncerrado,
    fechar_atendimento,
)
from restaurante.aplicacao.registrar_lancamento_adicional import (
    AtendimentoAbertoNaoEncontrado,
    registrar_lancamento_adicional,
)
from restaurante.aplicacao.registrar_primeiro_lancamento import (
    registrar_primeiro_lancamento,
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


class FecharAtendimentoTests(TestCase):
    def setUp(self):
        self.caixa = UsuarioOperacional.objects.create(
            nome="Caixa 1",
            papel=UsuarioOperacional.Papel.CAIXA,
        )
        self.comanda = ComandaFisica.objects.create(identificador="001")
        self.atendimento = Atendimento.objects.create(comanda=self.comanda)

    def test_caixa_fecha_atendimento_aberto_e_libera_comanda(self):
        resultado = fechar_atendimento(
            self.caixa.pk,
            self.atendimento.pk,
            str(uuid4()),
        )

        self.atendimento.refresh_from_db()
        estado_comanda = consultar_estado_comanda_caixa(
            self.caixa.pk,
            self.comanda.identificador,
        )
        self.assertEqual(
            self.atendimento.estado,
            Atendimento.Estado.ENCERRADO,
        )
        self.assertEqual(self.atendimento.fechado_por, self.caixa)
        self.assertIsNotNone(self.atendimento.fechado_em)
        self.assertEqual(self.atendimento.fechado_em.tzinfo, UTC)
        self.assertEqual(resultado.atendimento_id, self.atendimento.pk)
        self.assertEqual(resultado.comanda_identificador, "001")
        self.assertEqual(
            datetime.fromisoformat(resultado.fechado_em),
            self.atendimento.fechado_em,
        )
        self.assertEqual(estado_comanda.estado, EstadoComanda.DISPONIVEL)

    def test_garcom_nao_pode_fechar_atendimento(self):
        garcom = UsuarioOperacional.objects.create(
            nome="Garçom 1",
            papel=UsuarioOperacional.Papel.GARCOM,
        )

        with self.assertRaises(PapelNaoPermitido):
            fechar_atendimento(
                garcom.pk,
                self.atendimento.pk,
                str(uuid4()),
            )

        self.atendimento.refresh_from_db()
        self.assertEqual(self.atendimento.estado, Atendimento.Estado.ABERTO)
        self.assertIsNone(self.atendimento.fechado_por)
        self.assertIsNone(self.atendimento.fechado_em)
        self.assertEqual(RegistroIdempotencia.objects.count(), 0)

    def test_replay_com_mesma_chave_retorna_fechamento_original(self):
        chave = str(uuid4())

        primeiro = fechar_atendimento(
            self.caixa.pk,
            self.atendimento.pk,
            chave,
        )
        repetido = fechar_atendimento(
            self.caixa.pk,
            self.atendimento.pk,
            chave,
        )

        self.assertEqual(repetido, primeiro)
        self.assertEqual(RegistroIdempotencia.objects.count(), 1)

    def test_nova_chave_nao_fecha_atendimento_encerrado_novamente(self):
        fechar_atendimento(
            self.caixa.pk,
            self.atendimento.pk,
            str(uuid4()),
        )

        with self.assertRaises(AtendimentoJaEncerrado):
            fechar_atendimento(
                self.caixa.pk,
                self.atendimento.pk,
                str(uuid4()),
            )

        self.assertEqual(RegistroIdempotencia.objects.count(), 1)

    def test_fechamento_preserva_historico_e_bloqueia_novas_mutacoes(self):
        garcom = UsuarioOperacional.objects.create(
            nome="Garçom 1",
            papel=UsuarioOperacional.Papel.GARCOM,
        )
        produto = Produto.objects.create(nome="Café", preco_centavos=600)
        lancamento_valido = Lancamento.objects.create(
            atendimento=self.atendimento,
            produto=produto,
            quantidade=2,
            preco_unitario_centavos=600,
            autor=garcom,
        )
        lancamento_cancelado = Lancamento.objects.create(
            atendimento=self.atendimento,
            produto=produto,
            quantidade=1,
            preco_unitario_centavos=600,
            autor=garcom,
        )
        cancelamento = CancelamentoLancamento.objects.create(
            lancamento=lancamento_cancelado,
            motivo=CancelamentoLancamento.Motivo.DUPLICADO,
            descricao="",
            autor=garcom,
        )

        fechar_atendimento(
            self.caixa.pk,
            self.atendimento.pk,
            str(uuid4()),
        )

        with self.assertRaises(AtendimentoAbertoNaoEncontrado):
            registrar_lancamento_adicional(
                garcom.pk,
                self.comanda.identificador,
                produto.pk,
                1,
                str(uuid4()),
            )
        with self.assertRaises(AtendimentoEncerrado):
            cancelar_lancamento(
                garcom.pk,
                lancamento_valido.pk,
                CancelamentoLancamento.Motivo.DESISTENCIA,
                "",
                str(uuid4()),
            )

        self.atendimento.refresh_from_db()
        self.assertEqual(self.atendimento.estado, Atendimento.Estado.ENCERRADO)
        self.assertEqual(Lancamento.objects.count(), 2)
        self.assertTrue(
            Lancamento.objects.filter(pk=lancamento_valido.pk).exists()
        )
        self.assertTrue(
            Lancamento.objects.filter(pk=lancamento_cancelado.pk).exists()
        )
        self.assertTrue(
            CancelamentoLancamento.objects.filter(pk=cancelamento.pk).exists()
        )

    def test_referencia_ao_caixa_impede_exclusao_do_autor(self):
        fechar_atendimento(
            self.caixa.pk,
            self.atendimento.pk,
            str(uuid4()),
        )

        with self.assertRaises(ProtectedError):
            self.caixa.delete()

    def test_comanda_liberada_pode_receber_novo_atendimento(self):
        garcom = UsuarioOperacional.objects.create(
            nome="Garçom 1",
            papel=UsuarioOperacional.Papel.GARCOM,
        )
        produto = Produto.objects.create(nome="Café", preco_centavos=600)
        fechar_atendimento(
            self.caixa.pk,
            self.atendimento.pk,
            str(uuid4()),
        )

        novo_lancamento = registrar_primeiro_lancamento(
            garcom.pk,
            self.comanda.identificador,
            produto.pk,
            1,
            str(uuid4()),
        )

        self.atendimento.refresh_from_db()
        novo_atendimento = Atendimento.objects.get(
            pk=novo_lancamento.atendimento_id
        )
        self.assertNotEqual(novo_atendimento.pk, self.atendimento.pk)
        self.assertEqual(self.atendimento.estado, Atendimento.Estado.ENCERRADO)
        self.assertEqual(novo_atendimento.estado, Atendimento.Estado.ABERTO)

    def test_falha_ao_confirmar_resultado_reverte_fechamento(self):
        def falhar_ao_confirmar_resultado(execute, sql, params, many, context):
            sql_normalizado = sql.lower()
            if (
                sql_normalizado.startswith("update")
                and '"persistencia_registroidempotencia"'
                in sql_normalizado
            ):
                raise DatabaseError("falha simulada ao confirmar resultado")
            return execute(sql, params, many, context)

        with connection.execute_wrapper(falhar_ao_confirmar_resultado):
            with self.assertRaisesRegex(
                DatabaseError,
                "falha simulada ao confirmar resultado",
            ):
                fechar_atendimento(
                    self.caixa.pk,
                    self.atendimento.pk,
                    str(uuid4()),
                )

        self.atendimento.refresh_from_db()
        self.assertEqual(self.atendimento.estado, Atendimento.Estado.ABERTO)
        self.assertIsNone(self.atendimento.fechado_por)
        self.assertIsNone(self.atendimento.fechado_em)
        self.assertEqual(RegistroIdempotencia.objects.count(), 0)
