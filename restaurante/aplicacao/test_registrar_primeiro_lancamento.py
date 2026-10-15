from datetime import timedelta

from django.test import TestCase

from restaurante.aplicacao.idempotencia import ConflitoIdempotencia
from restaurante.aplicacao.registrar_primeiro_lancamento import (
    ComandaEmAtendimento,
    ComandaNaoEncontrada,
    ProdutoNaoEncontrado,
    registrar_primeiro_lancamento,
)
from restaurante.aplicacao.consultar_estado_comanda import (
    PapelNaoPermitido,
    UsuarioOperacionalInvalido,
)
from restaurante.dominio.lancamentos import QuantidadeInvalida
from restaurante.persistencia.models import (
    Atendimento,
    ComandaFisica,
    Lancamento,
    Produto,
    UsuarioOperacional,
)


class RegistrarPrimeiroLancamentoTests(TestCase):
    def test_repetir_mesma_tentativa_retorna_resultado_sem_duplicar(self):
        garcom = UsuarioOperacional.objects.create(
            nome="Garçom 1",
            papel=UsuarioOperacional.Papel.GARCOM,
        )
        ComandaFisica.objects.create(identificador="001")
        produto = Produto.objects.create(nome="Café", preco_centavos=600)

        primeiro = registrar_primeiro_lancamento(
            garcom.pk, "001", produto.pk, 1, "mesma-tentativa"
        )
        repetido = registrar_primeiro_lancamento(
            garcom.pk, "001", produto.pk, 1, "mesma-tentativa"
        )

        self.assertEqual(repetido, primeiro)
        self.assertEqual(Atendimento.objects.count(), 1)
        self.assertEqual(Lancamento.objects.count(), 1)

    def test_replay_retorna_resultado_original_apos_garcom_mudar_de_papel(self):
        garcom = UsuarioOperacional.objects.create(
            nome="Garçom 1",
            papel=UsuarioOperacional.Papel.GARCOM,
        )
        ComandaFisica.objects.create(identificador="001")
        produto = Produto.objects.create(nome="Café", preco_centavos=600)
        original = registrar_primeiro_lancamento(
            garcom.pk, "001", produto.pk, 1, "replay-apos-papel"
        )
        garcom.papel = UsuarioOperacional.Papel.CAIXA
        garcom.save(update_fields=["papel"])

        repetido = registrar_primeiro_lancamento(
            garcom.pk, "001", produto.pk, 1, "replay-apos-papel"
        )

        self.assertEqual(repetido, original)
        self.assertEqual(Atendimento.objects.count(), 1)
        self.assertEqual(Lancamento.objects.count(), 1)
        with self.assertRaises(PapelNaoPermitido):
            registrar_primeiro_lancamento(
                garcom.pk, "001", produto.pk, 1, "nova-chave-apos-papel"
            )

    def test_mesma_chave_com_quantidade_diferente_e_conflito(self):
        garcom = UsuarioOperacional.objects.create(
            nome="Garçom 1",
            papel=UsuarioOperacional.Papel.GARCOM,
        )
        ComandaFisica.objects.create(identificador="001")
        produto = Produto.objects.create(nome="Café", preco_centavos=600)
        registrar_primeiro_lancamento(
            garcom.pk, "001", produto.pk, 1, "tentativa-conflitante"
        )

        with self.assertRaises(ConflitoIdempotencia):
            registrar_primeiro_lancamento(
                garcom.pk,
                "001",
                produto.pk,
                2,
                "tentativa-conflitante",
            )

        self.assertEqual(Atendimento.objects.count(), 1)
        self.assertEqual(Lancamento.objects.count(), 1)

    def test_garcom_registra_primeiro_lancamento_em_comanda_disponivel(self):
        garcom = UsuarioOperacional.objects.create(
            nome="Garçom 1",
            papel=UsuarioOperacional.Papel.GARCOM,
        )
        ComandaFisica.objects.create(identificador="001")
        produto = Produto.objects.create(
            nome="Batata frita",
            preco_centavos=2000,
        )

        resultado = registrar_primeiro_lancamento(
            garcom.pk,
            "001",
            produto.pk,
            2,
            "primeiro-sucesso",
        )

        atendimento = Atendimento.objects.get()
        lancamento = Lancamento.objects.get()
        self.assertEqual(resultado.atendimento_id, atendimento.pk)
        self.assertEqual(resultado.lancamento_id, lancamento.pk)
        self.assertEqual(resultado.comanda, "001")
        self.assertEqual(resultado.produto, "Batata frita")
        self.assertEqual(resultado.quantidade, 2)
        self.assertEqual(resultado.preco_unitario_centavos, 2000)
        self.assertEqual(atendimento.comanda.identificador, "001")
        self.assertEqual(atendimento.estado, Atendimento.Estado.ABERTO)
        self.assertEqual(lancamento.atendimento, atendimento)
        self.assertEqual(lancamento.produto, produto)
        self.assertEqual(lancamento.autor, garcom)
        self.assertIsNotNone(lancamento.horario)
        self.assertEqual(lancamento.horario.utcoffset(), timedelta(0))

    def test_preco_do_lancamento_e_snapshot_do_produto(self):
        garcom = UsuarioOperacional.objects.create(
            nome="Garçom 1",
            papel=UsuarioOperacional.Papel.GARCOM,
        )
        ComandaFisica.objects.create(identificador="001")
        produto = Produto.objects.create(
            nome="Batata frita",
            preco_centavos=2000,
        )

        registrar_primeiro_lancamento(
            garcom.pk, "001", produto.pk, 1, "snapshot-preco"
        )
        produto.preco_centavos = 2500
        produto.save(update_fields=["preco_centavos"])

        self.assertEqual(Lancamento.objects.get().preco_unitario_centavos, 2000)

    def test_comanda_desconhecida_ou_identificador_diferente_e_rejeitado(self):
        garcom = UsuarioOperacional.objects.create(
            nome="Garçom 1",
            papel=UsuarioOperacional.Papel.GARCOM,
        )
        ComandaFisica.objects.create(identificador="001")
        produto = Produto.objects.create(nome="Café", preco_centavos=600)

        for identificador in ("999", "1"):
            with self.subTest(identificador=identificador):
                with self.assertRaises(ComandaNaoEncontrada):
                    registrar_primeiro_lancamento(
                        garcom.pk,
                        identificador,
                        produto.pk,
                        1,
                        f"comanda-{identificador}",
                    )

        self.assertEqual(Atendimento.objects.count(), 0)
        self.assertEqual(Lancamento.objects.count(), 0)

    def test_produto_desconhecido_e_rejeitado_sem_estado_parcial(self):
        garcom = UsuarioOperacional.objects.create(
            nome="Garçom 1",
            papel=UsuarioOperacional.Papel.GARCOM,
        )
        ComandaFisica.objects.create(identificador="001")

        with self.assertRaises(ProdutoNaoEncontrado):
            registrar_primeiro_lancamento(
                garcom.pk, "001", 999_999, 1, "produto-inexistente"
            )

        self.assertEqual(Atendimento.objects.count(), 0)
        self.assertEqual(Lancamento.objects.count(), 0)

    def test_quantidade_deve_ser_inteira_positiva(self):
        garcom = UsuarioOperacional.objects.create(
            nome="Garçom 1",
            papel=UsuarioOperacional.Papel.GARCOM,
        )
        ComandaFisica.objects.create(identificador="001")
        produto = Produto.objects.create(nome="Café", preco_centavos=600)

        for quantidade in (0, -1, "1.5", "abc", "", 1.5, True):
            with self.subTest(quantidade=quantidade):
                with self.assertRaises(QuantidadeInvalida):
                    registrar_primeiro_lancamento(
                        garcom.pk,
                        "001",
                        produto.pk,
                        quantidade,
                        f"quantidade-{quantidade}",
                    )

        self.assertEqual(Atendimento.objects.count(), 0)
        self.assertEqual(Lancamento.objects.count(), 0)

    def test_caixa_nao_pode_realizar_lancamento(self):
        caixa = UsuarioOperacional.objects.create(
            nome="Caixa 1",
            papel=UsuarioOperacional.Papel.CAIXA,
        )

        with self.assertRaises(PapelNaoPermitido):
            registrar_primeiro_lancamento(
                caixa.pk, "001", 1, 1, "caixa-sem-permissao"
            )

        self.assertEqual(Atendimento.objects.count(), 0)
        self.assertEqual(Lancamento.objects.count(), 0)

    def test_usuario_inexistente_ou_invalido_e_rejeitado(self):
        for usuario_id in (999_999, "inválido", None):
            with self.subTest(usuario_id=usuario_id):
                with self.assertRaises(UsuarioOperacionalInvalido):
                    registrar_primeiro_lancamento(
                        usuario_id,
                        "001",
                        1,
                        1,
                        f"usuario-{usuario_id}",
                    )

        self.assertEqual(Atendimento.objects.count(), 0)
        self.assertEqual(Lancamento.objects.count(), 0)

    def test_comanda_com_atendimento_aberto_rejeita_primeiro_lancamento(self):
        garcom = UsuarioOperacional.objects.create(
            nome="Garçom 1",
            papel=UsuarioOperacional.Papel.GARCOM,
        )
        comanda = ComandaFisica.objects.create(identificador="001")
        Atendimento.objects.create(comanda=comanda)
        produto = Produto.objects.create(nome="Café", preco_centavos=600)

        with self.assertRaises(ComandaEmAtendimento):
            registrar_primeiro_lancamento(
                garcom.pk,
                "001",
                produto.pk,
                1,
                "comanda-em-atendimento",
            )

        self.assertEqual(Atendimento.objects.count(), 1)
        self.assertEqual(Lancamento.objects.count(), 0)
