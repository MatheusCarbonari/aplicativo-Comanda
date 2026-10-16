from django.db import IntegrityError, transaction
from django.test import TestCase

from restaurante.persistencia.models import (
    Atendimento,
    CancelamentoLancamento,
    ComandaFisica,
    Lancamento,
    Produto,
    UsuarioOperacional,
)


class CancelamentoLancamentoPersistenciaTests(TestCase):
    def test_sqlite_impede_dois_cancelamentos_do_mesmo_lancamento(self):
        garcom = UsuarioOperacional.objects.create(
            nome="Garçom 1",
            papel=UsuarioOperacional.Papel.GARCOM,
        )
        comanda = ComandaFisica.objects.create(identificador="001")
        atendimento = Atendimento.objects.create(comanda=comanda)
        produto = Produto.objects.create(nome="Café", preco_centavos=600)
        lancamento = Lancamento.objects.create(
            atendimento=atendimento,
            produto=produto,
            quantidade=1,
            preco_unitario_centavos=600,
            autor=garcom,
        )
        CancelamentoLancamento.objects.create(
            lancamento=lancamento,
            motivo=CancelamentoLancamento.Motivo.DUPLICADO,
            descricao="",
            autor=garcom,
        )

        with self.assertRaises(IntegrityError), transaction.atomic():
            CancelamentoLancamento.objects.create(
                lancamento=lancamento,
                motivo=CancelamentoLancamento.Motivo.DESISTENCIA,
                descricao="",
                autor=garcom,
            )

        self.assertEqual(CancelamentoLancamento.objects.count(), 1)
