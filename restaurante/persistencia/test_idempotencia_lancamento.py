from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

from django.db import close_old_connections, connection
from django.test import TransactionTestCase

from restaurante.aplicacao.registrar_lancamento_adicional import (
    registrar_lancamento_adicional,
)
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


class IdempotenciaLancamentoPersistenciaTests(TransactionTestCase):
    def test_primeiro_lancamento_simultaneo_com_mesma_chave_e_aplicado_uma_vez(self):
        garcom = UsuarioOperacional.objects.create(
            nome="Garçom 1",
            papel=UsuarioOperacional.Papel.GARCOM,
        )
        ComandaFisica.objects.create(identificador="001")
        produto = Produto.objects.create(nome="Café", preco_centavos=600)
        inicio = Barrier(2)

        def tentar():
            close_old_connections()
            inicio.wait()
            try:
                return registrar_primeiro_lancamento(
                    garcom.pk,
                    "001",
                    produto.pk,
                    1,
                    "primeiro-concorrente",
                )
            finally:
                close_old_connections()

        with ThreadPoolExecutor(max_workers=2) as executor:
            resultados = list(executor.map(lambda _: tentar(), range(2)))

        self.assertEqual(resultados[0], resultados[1])
        self.assertEqual(Atendimento.objects.count(), 1)
        self.assertEqual(Lancamento.objects.count(), 1)

    def test_repeticao_apos_reabrir_conexao_nao_duplica_lancamento(self):
        garcom = UsuarioOperacional.objects.create(
            nome="Garçom 1",
            papel=UsuarioOperacional.Papel.GARCOM,
        )
        comanda = ComandaFisica.objects.create(identificador="001")
        Atendimento.objects.create(comanda=comanda)
        produto = Produto.objects.create(nome="Café", preco_centavos=600)

        primeiro = registrar_lancamento_adicional(
            garcom.pk, "001", produto.pk, 1, "tentativa-persistida"
        )
        connection.close()
        repetido = registrar_lancamento_adicional(
            garcom.pk, "001", produto.pk, 1, "tentativa-persistida"
        )

        self.assertEqual(repetido, primeiro)
        self.assertEqual(Lancamento.objects.count(), 1)
