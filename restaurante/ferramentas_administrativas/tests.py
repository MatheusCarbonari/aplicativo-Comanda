from io import StringIO

from django.core.management import call_command
from django.db import IntegrityError, transaction
from django.test import TestCase

from restaurante.persistencia.models import ComandaFisica, Produto, UsuarioOperacional


class CargaDadosIniciaisTests(TestCase):
    def executar_carga(self) -> str:
        saida = StringIO()
        call_command("carregar_dados_iniciais", stdout=saida)
        return saida.getvalue()

    def test_primeira_carga_cria_a_massa_aprovada(self):
        self.executar_carga()

        self.assertEqual(
            list(
                ComandaFisica.objects.order_by("identificador").values_list(
                    "identificador",
                    flat=True,
                )
            ),
            [
                "001",
                "002",
                "003",
                "004",
                "005",
                "006",
                "007",
                "008",
                "009",
                "010",
                "011",
                "012",
                "013",
                "014",
                "015",
                "016",
                "017",
                "018",
                "019",
                "020",
            ],
        )
        self.assertEqual(
            dict(UsuarioOperacional.objects.values_list("nome", "papel")),
            {
                "Garçom 1": UsuarioOperacional.Papel.GARCOM,
                "Garçom 2": UsuarioOperacional.Papel.GARCOM,
                "Caixa 1": UsuarioOperacional.Papel.CAIXA,
            },
        )
        self.assertEqual(
            dict(Produto.objects.values_list("nome", "preco_centavos")),
            {
                "Água mineral": 500,
                "Refrigerante": 750,
                "Suco": 900,
                "Cerveja": 1200,
                "Batata frita": 2000,
                "Hambúrguer": 2800,
                "Pizza": 4500,
                "Salada": 1800,
                "Sobremesa": 1500,
                "Café": 600,
            },
        )

    def test_segunda_execucao_nao_cria_duplicatas(self):
        self.executar_carga()
        self.executar_carga()

        self.assertEqual(ComandaFisica.objects.count(), 20)
        self.assertEqual(UsuarioOperacional.objects.count(), 3)
        self.assertEqual(Produto.objects.count(), 10)

    def test_carga_preserva_alteracoes_e_registros_extras(self):
        comanda_existente = ComandaFisica.objects.create(identificador="001")
        comanda_extra = ComandaFisica.objects.create(identificador="999")
        produto_existente = Produto.objects.create(
            nome="Batata frita",
            preco_centavos=2500,
        )
        produto_extra = Produto.objects.create(
            nome="Produto local",
            preco_centavos=1234,
        )
        usuario_existente = UsuarioOperacional.objects.create(
            nome="Garçom 1",
            papel=UsuarioOperacional.Papel.CAIXA,
        )
        usuario_extra = UsuarioOperacional.objects.create(
            nome="Usuário local",
            papel=UsuarioOperacional.Papel.GARCOM,
        )

        self.executar_carga()
        self.executar_carga()

        produto_existente.refresh_from_db()
        usuario_existente.refresh_from_db()
        self.assertEqual(produto_existente.preco_centavos, 2500)
        self.assertEqual(usuario_existente.papel, UsuarioOperacional.Papel.CAIXA)
        self.assertTrue(ComandaFisica.objects.filter(pk=comanda_existente.pk).exists())
        self.assertTrue(ComandaFisica.objects.filter(pk=comanda_extra.pk).exists())
        self.assertTrue(Produto.objects.filter(pk=produto_extra.pk).exists())
        self.assertTrue(UsuarioOperacional.objects.filter(pk=usuario_extra.pk).exists())
        self.assertEqual(ComandaFisica.objects.count(), 21)
        self.assertEqual(Produto.objects.count(), 11)
        self.assertEqual(UsuarioOperacional.objects.count(), 4)

    def test_identidades_naturais_sao_unicas(self):
        ComandaFisica.objects.create(identificador="001")
        Produto.objects.create(nome="Café", preco_centavos=600)
        UsuarioOperacional.objects.create(
            nome="Caixa 1",
            papel=UsuarioOperacional.Papel.CAIXA,
        )

        duplicatas = (
            lambda: ComandaFisica.objects.create(identificador="001"),
            lambda: Produto.objects.create(nome="Café", preco_centavos=700),
            lambda: UsuarioOperacional.objects.create(
                nome="Caixa 1",
                papel=UsuarioOperacional.Papel.GARCOM,
            ),
        )

        for criar_duplicata in duplicatas:
            with self.subTest(criar_duplicata=criar_duplicata):
                with self.assertRaises(IntegrityError), transaction.atomic():
                    criar_duplicata()
