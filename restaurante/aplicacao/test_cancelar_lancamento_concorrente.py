from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

from django.db import close_old_connections
from django.test import TransactionTestCase

from restaurante.aplicacao.cancelar_lancamento import (
    LancamentoJaCancelado,
    cancelar_lancamento,
)
from restaurante.persistencia.models import (
    Atendimento,
    CancelamentoLancamento,
    ComandaFisica,
    Lancamento,
    Produto,
    UsuarioOperacional,
)


class CancelarLancamentoConcorrenteTests(TransactionTestCase):
    def test_duas_chaves_distintas_preservam_um_unico_cancelamento(self):
        garcom_1 = UsuarioOperacional.objects.create(
            nome="Garçom 1",
            papel=UsuarioOperacional.Papel.GARCOM,
        )
        garcom_2 = UsuarioOperacional.objects.create(
            nome="Garçom 2",
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
            autor=garcom_1,
        )
        inicio = Barrier(2)
        solicitacoes = (
            (garcom_1.pk, "cancelamento-concorrente-1"),
            (garcom_2.pk, "cancelamento-concorrente-2"),
        )

        def tentar(solicitacao):
            close_old_connections()
            inicio.wait()
            try:
                garcom_id, chave = solicitacao
                resultado = cancelar_lancamento(
                    garcom_id,
                    lancamento.pk,
                    CancelamentoLancamento.Motivo.DUPLICADO,
                    "",
                    chave,
                )
                return "confirmado", resultado.autor
            except LancamentoJaCancelado:
                return "ja_cancelado", None
            finally:
                close_old_connections()

        with ThreadPoolExecutor(max_workers=2) as executor:
            resultados = list(executor.map(tentar, solicitacoes))

        cancelamento = CancelamentoLancamento.objects.get(
            lancamento=lancamento
        )
        self.assertEqual(
            sorted(resultado[0] for resultado in resultados),
            ["confirmado", "ja_cancelado"],
        )
        self.assertEqual(
            next(
                autor
                for estado, autor in resultados
                if estado == "confirmado"
            ),
            cancelamento.autor.nome,
        )
