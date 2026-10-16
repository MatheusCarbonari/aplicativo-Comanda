from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

from django.db import close_old_connections
from django.test import TransactionTestCase

from restaurante.aplicacao.registrar_primeiro_lancamento import (
    registrar_primeiro_lancamento,
)
from restaurante.persistencia.models import (
    Atendimento,
    ComandaFisica,
    Lancamento,
    Produto,
    RegistroIdempotencia,
    UsuarioOperacional,
)


class AberturaSimultaneaAtendimentoTests(TransactionTestCase):
    repeticoes = 5

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.garcom_1 = UsuarioOperacional.objects.create(
            nome="Garçom 1",
            papel=UsuarioOperacional.Papel.GARCOM,
        )
        cls.garcom_2 = UsuarioOperacional.objects.create(
            nome="Garçom 2",
            papel=UsuarioOperacional.Papel.GARCOM,
        )
        cls.cafe = Produto.objects.create(nome="Café", preco_centavos=600)
        cls.pizza = Produto.objects.create(nome="Pizza", preco_centavos=4500)

    def test_primeiros_lancamentos_simultaneos_convergem_sem_perda_ou_duplicacao(
        self,
    ):
        for repeticao in range(self.repeticoes):
            with self.subTest(repeticao=repeticao):
                comanda = ComandaFisica.objects.create(
                    identificador=f"{repeticao:03d}"
                )
                inicio = Barrier(2)
                solicitacoes = (
                    (
                        self.garcom_1.pk,
                        self.cafe.pk,
                        2,
                        f"abertura-{repeticao}-garcom-1",
                    ),
                    (
                        self.garcom_2.pk,
                        self.pizza.pk,
                        1,
                        f"abertura-{repeticao}-garcom-2",
                    ),
                )

                def tentar(solicitacao):
                    close_old_connections()
                    inicio.wait()
                    try:
                        garcom_id, produto_id, quantidade, chave = solicitacao
                        return registrar_primeiro_lancamento(
                            garcom_id,
                            comanda.identificador,
                            produto_id,
                            quantidade,
                            chave,
                        )
                    finally:
                        close_old_connections()

                with ThreadPoolExecutor(max_workers=2) as executor:
                    resultados = list(executor.map(tentar, solicitacoes))

                atendimento = Atendimento.objects.get(
                    comanda=comanda,
                    estado=Atendimento.Estado.ABERTO,
                )
                lancamentos = list(
                    Lancamento.objects.filter(atendimento=atendimento)
                    .order_by("autor__nome")
                    .values_list(
                        "autor__nome",
                        "produto__nome",
                        "quantidade",
                    )
                )

                self.assertEqual(
                    {resultado.atendimento_id for resultado in resultados},
                    {atendimento.pk},
                )
                self.assertEqual(
                    lancamentos,
                    [
                        ("Garçom 1", "Café", 2),
                        ("Garçom 2", "Pizza", 1),
                    ],
                )
                self.assertEqual(
                    RegistroIdempotencia.objects.filter(
                        chave__startswith=f"abertura-{repeticao}-"
                    ).count(),
                    2,
                )

                repetidos = [
                    registrar_primeiro_lancamento(
                        garcom_id,
                        comanda.identificador,
                        produto_id,
                        quantidade,
                        chave,
                    )
                    for garcom_id, produto_id, quantidade, chave in solicitacoes
                ]
                self.assertEqual(repetidos, resultados)
                self.assertEqual(
                    Lancamento.objects.filter(atendimento=atendimento).count(),
                    2,
                )
