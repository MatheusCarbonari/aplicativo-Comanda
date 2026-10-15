from unittest import TestCase

from restaurante.dominio.lancamentos import (
    QuantidadeInvalida,
    calcular_total_atendimento,
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
