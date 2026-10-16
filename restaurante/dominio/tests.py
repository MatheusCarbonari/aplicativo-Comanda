from unittest import TestCase

from restaurante.dominio.lancamentos import (
    LancamentoParaConsolidacao,
    QuantidadeInvalida,
    calcular_total_atendimento,
    consolidar_lancamentos,
    validar_quantidade,
)


class ValidarQuantidadeTests(TestCase):
    def test_aceita_inteiros_positivos(self):
        for entrada, esperado in ((1, 1), (2, 2), ("10", 10)):
            with self.subTest(entrada=entrada):
                self.assertEqual(validar_quantidade(entrada), esperado)

    def test_rejeita_valores_que_nao_sao_inteiros_positivos(self):
        for entrada in (0, -1, "1.5", "abc", "", 1.5, True, None):
            with self.subTest(entrada=entrada):
                with self.assertRaises(QuantidadeInvalida):
                    validar_quantidade(entrada)


class CalcularTotalAtendimentoTests(TestCase):
    def test_soma_quantidade_vezes_preco_registrado_em_centavos(self):
        lancamentos = [(2, 600), (1, 4500)]

        total = calcular_total_atendimento(lancamentos)

        self.assertEqual(total, 5700)

    def test_atendimento_sem_lancamentos_tem_total_zero(self):
        self.assertEqual(calcular_total_atendimento([]), 0)


class ConsolidarLancamentosTests(TestCase):
    def test_soma_quantidades_do_mesmo_produto_e_preco(self):
        lancamentos = [
            LancamentoParaConsolidacao(1, "Café", 1, 600),
            LancamentoParaConsolidacao(1, "Café", 2, 600),
        ]

        consolidados = consolidar_lancamentos(lancamentos)

        self.assertEqual(len(consolidados), 1)
        self.assertEqual(consolidados[0].produto, "Café")
        self.assertEqual(consolidados[0].quantidade, 3)
        self.assertEqual(consolidados[0].preco_unitario_centavos, 600)
        self.assertEqual(consolidados[0].subtotal_centavos, 1800)

    def test_mantem_precos_diferentes_em_linhas_separadas(self):
        lancamentos = [
            LancamentoParaConsolidacao(1, "Café", 2, 600),
            LancamentoParaConsolidacao(1, "Café", 1, 700),
        ]

        consolidados = consolidar_lancamentos(lancamentos)

        self.assertEqual(
            [
                (
                    item.produto,
                    item.quantidade,
                    item.preco_unitario_centavos,
                    item.subtotal_centavos,
                )
                for item in consolidados
            ],
            [
                ("Café", 2, 600, 1200),
                ("Café", 1, 700, 700),
            ],
        )
