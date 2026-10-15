from django.test import TestCase

from restaurante.aplicacao.idempotencia import ConflitoIdempotencia
from restaurante.aplicacao.registrar_lancamento_adicional import (
    AtendimentoAbertoNaoEncontrado,
    registrar_lancamento_adicional,
)
from restaurante.aplicacao.consultar_estado_comanda import (
    PapelNaoPermitido,
    UsuarioOperacionalInvalido,
)
from restaurante.aplicacao.registrar_primeiro_lancamento import (
    ComandaNaoEncontrada,
    ProdutoNaoEncontrado,
    registrar_primeiro_lancamento,
)
from restaurante.dominio.lancamentos import QuantidadeInvalida
from restaurante.persistencia.models import (
    Atendimento,
    ComandaFisica,
    Lancamento,
    Produto,
    UsuarioOperacional,
)


class RegistrarLancamentoAdicionalTests(TestCase):
    def criar_cenario_aberto(self):
        garcom = UsuarioOperacional.objects.create(
            nome="Garçom 1",
            papel=UsuarioOperacional.Papel.GARCOM,
        )
        comanda = ComandaFisica.objects.create(identificador="001")
        atendimento = Atendimento.objects.create(comanda=comanda)
        produto = Produto.objects.create(nome="Café", preco_centavos=600)
        return garcom, atendimento, produto

    def test_repetir_mesma_tentativa_nao_cria_outro_lancamento(self):
        garcom, atendimento, produto = self.criar_cenario_aberto()

        primeiro = registrar_lancamento_adicional(
            garcom.pk, "001", produto.pk, 1, "mesma-tentativa"
        )
        repetido = registrar_lancamento_adicional(
            garcom.pk, "001", produto.pk, 1, "mesma-tentativa"
        )

        self.assertEqual(repetido, primeiro)
        self.assertEqual(atendimento.lancamentos.count(), 1)

    def test_replay_preserva_resultado_apos_produto_e_comanda_mudarem(self):
        garcom, atendimento, produto = self.criar_cenario_aberto()
        original = registrar_lancamento_adicional(
            garcom.pk, "001", produto.pk, 1, "replay-apos-cadastros"
        )
        produto.nome = "Café especial"
        produto.preco_centavos = 900
        produto.save(update_fields=["nome", "preco_centavos"])
        atendimento.comanda.identificador = "099"
        atendimento.comanda.save(update_fields=["identificador"])

        repetido = registrar_lancamento_adicional(
            garcom.pk, "001", produto.pk, 1, "replay-apos-cadastros"
        )

        self.assertEqual(repetido, original)
        self.assertEqual(repetido.produto, "Café")
        self.assertEqual(repetido.preco_unitario_centavos, 600)
        self.assertEqual(atendimento.lancamentos.count(), 1)
        with self.assertRaises(ComandaNaoEncontrada):
            registrar_lancamento_adicional(
                garcom.pk,
                "001",
                produto.pk,
                1,
                "nova-chave-apos-cadastros",
            )

    def test_mesma_chave_com_produto_diferente_e_conflito(self):
        garcom, atendimento, produto = self.criar_cenario_aberto()
        pizza = Produto.objects.create(nome="Pizza", preco_centavos=4500)
        registrar_lancamento_adicional(
            garcom.pk, "001", produto.pk, 1, "tentativa-conflitante"
        )

        with self.assertRaises(ConflitoIdempotencia):
            registrar_lancamento_adicional(
                garcom.pk,
                "001",
                pizza.pk,
                1,
                "tentativa-conflitante",
            )

        self.assertEqual(atendimento.lancamentos.count(), 1)

    def test_chaves_diferentes_criam_lancamentos_intencionais_iguais(self):
        garcom, atendimento, produto = self.criar_cenario_aberto()

        for chave in ("tentativa-a", "tentativa-b"):
            registrar_lancamento_adicional(
                garcom.pk, "001", produto.pk, 1, chave
            )

        self.assertEqual(atendimento.lancamentos.count(), 2)

    def test_mesma_chave_nao_pode_ser_reutilizada_em_outra_operacao(self):
        garcom = UsuarioOperacional.objects.create(
            nome="Garçom 1",
            papel=UsuarioOperacional.Papel.GARCOM,
        )
        ComandaFisica.objects.create(identificador="001")
        produto = Produto.objects.create(nome="Café", preco_centavos=600)
        registrar_primeiro_lancamento(
            garcom.pk, "001", produto.pk, 1, "chave-entre-operacoes"
        )

        with self.assertRaises(ConflitoIdempotencia):
            registrar_lancamento_adicional(
                garcom.pk,
                "001",
                produto.pk,
                1,
                "chave-entre-operacoes",
            )

        self.assertEqual(Lancamento.objects.count(), 1)

    def test_outro_garcom_adiciona_registro_independente_ao_atendimento(self):
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
        cafe = Produto.objects.create(nome="Café", preco_centavos=600)
        Lancamento.objects.create(
            atendimento=atendimento,
            produto=cafe,
            quantidade=1,
            preco_unitario_centavos=600,
            autor=garcom_1,
        )

        resultado = registrar_lancamento_adicional(
            garcom_2.pk,
            "001",
            cafe.pk,
            2,
            "adicional-outro-garcom",
        )

        lancamentos = list(atendimento.lancamentos.order_by("pk"))
        self.assertEqual(Atendimento.objects.count(), 1)
        self.assertEqual(len(lancamentos), 2)
        self.assertNotEqual(lancamentos[0].pk, lancamentos[1].pk)
        self.assertEqual(lancamentos[0].autor, garcom_1)
        self.assertEqual(lancamentos[1].autor, garcom_2)
        self.assertEqual(lancamentos[0].quantidade, 1)
        self.assertEqual(lancamentos[1].quantidade, 2)
        self.assertIsNotNone(lancamentos[1].horario)
        self.assertEqual(resultado.atendimento_id, atendimento.pk)
        self.assertEqual(resultado.lancamento_id, lancamentos[1].pk)
        self.assertEqual(resultado.comanda, "001")
        self.assertEqual(resultado.produto, "Café")
        self.assertEqual(resultado.autor, "Garçom 2")
        self.assertEqual(resultado.preco_unitario_centavos, 600)
        self.assertEqual(resultado.total_centavos, 1800)

    def test_preco_snapshot_e_total_usam_valores_dos_lancamentos(self):
        garcom, atendimento, cafe = self.criar_cenario_aberto()
        Lancamento.objects.create(
            atendimento=atendimento,
            produto=cafe,
            quantidade=2,
            preco_unitario_centavos=600,
            autor=garcom,
        )
        cafe.preco_centavos = 700
        cafe.save(update_fields=["preco_centavos"])

        resultado = registrar_lancamento_adicional(
            garcom.pk,
            "001",
            cafe.pk,
            1,
            "adicional-snapshot",
        )
        cafe.preco_centavos = 900
        cafe.save(update_fields=["preco_centavos"])

        precos = list(
            atendimento.lancamentos.order_by("pk").values_list(
                "preco_unitario_centavos",
                flat=True,
            )
        )
        self.assertEqual(precos, [600, 700])
        self.assertEqual(resultado.total_centavos, 1900)

    def test_comanda_desconhecida_e_rejeitada_sem_criar_dados(self):
        garcom = UsuarioOperacional.objects.create(
            nome="Garçom 1",
            papel=UsuarioOperacional.Papel.GARCOM,
        )
        ComandaFisica.objects.create(identificador="001")
        produto = Produto.objects.create(nome="Café", preco_centavos=600)

        for identificador in ("999", "1"):
            with self.subTest(identificador=identificador):
                with self.assertRaises(ComandaNaoEncontrada):
                    registrar_lancamento_adicional(
                        garcom.pk,
                        identificador,
                        produto.pk,
                        1,
                        f"comanda-{identificador}",
                    )

        self.assertEqual(Atendimento.objects.count(), 0)
        self.assertEqual(Lancamento.objects.count(), 0)

    def test_produto_ou_quantidade_invalida_nao_cria_lancamento(self):
        garcom, atendimento, produto = self.criar_cenario_aberto()

        with self.assertRaises(ProdutoNaoEncontrado):
            registrar_lancamento_adicional(
                garcom.pk, "001", 999_999, 1, "produto-inexistente"
            )
        for quantidade in (0, -1, "1.5", "abc", ""):
            with self.subTest(quantidade=quantidade):
                with self.assertRaises(QuantidadeInvalida):
                    registrar_lancamento_adicional(
                        garcom.pk,
                        "001",
                        produto.pk,
                        quantidade,
                        f"quantidade-{quantidade}",
                    )

        self.assertEqual(Atendimento.objects.get(), atendimento)
        self.assertEqual(Lancamento.objects.count(), 0)

    def test_caixa_ou_usuario_invalido_nao_pode_lancar(self):
        caixa = UsuarioOperacional.objects.create(
            nome="Caixa 1",
            papel=UsuarioOperacional.Papel.CAIXA,
        )

        with self.assertRaises(PapelNaoPermitido):
            registrar_lancamento_adicional(
                caixa.pk, "001", 1, 1, "caixa-sem-permissao"
            )
        for usuario_id in (999_999, "inválido", None):
            with self.subTest(usuario_id=usuario_id):
                with self.assertRaises(UsuarioOperacionalInvalido):
                    registrar_lancamento_adicional(
                        usuario_id,
                        "001",
                        1,
                        1,
                        f"usuario-{usuario_id}",
                    )

        self.assertEqual(Atendimento.objects.count(), 0)
        self.assertEqual(Lancamento.objects.count(), 0)

    def test_sem_atendimento_aberto_rejeita_sem_criar_dados(self):
        garcom = UsuarioOperacional.objects.create(
            nome="Garçom 1",
            papel=UsuarioOperacional.Papel.GARCOM,
        )
        comanda = ComandaFisica.objects.create(identificador="001")
        atendimento_encerrado = Atendimento.objects.create(
            comanda=comanda,
            estado=Atendimento.Estado.ENCERRADO,
        )
        produto = Produto.objects.create(nome="Café", preco_centavos=600)

        with self.assertRaises(AtendimentoAbertoNaoEncontrado):
            registrar_lancamento_adicional(
                garcom.pk,
                "001",
                produto.pk,
                1,
                "atendimento-encerrado",
            )

        self.assertEqual(Atendimento.objects.get(), atendimento_encerrado)
        self.assertEqual(Lancamento.objects.count(), 0)
