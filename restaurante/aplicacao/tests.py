from django.test import TestCase

from restaurante.aplicacao.consultar_estado_comanda import (
    EstadoComanda,
    PapelNaoPermitido,
    UsuarioOperacionalInvalido,
    consultar_estado_comanda,
)
from restaurante.persistencia.models import (
    Atendimento,
    ComandaFisica,
    UsuarioOperacional,
)


class ConsultarEstadoComandaTests(TestCase):
    def test_comanda_existente_sem_atendimento_esta_disponivel(self):
        usuario = UsuarioOperacional.objects.create(
            nome="Garçom 1",
            papel=UsuarioOperacional.Papel.GARCOM,
        )
        ComandaFisica.objects.create(identificador="001")

        resultado = consultar_estado_comanda(usuario.pk, "001")

        self.assertEqual(resultado.estado, EstadoComanda.DISPONIVEL)
        self.assertEqual(resultado.identificador, "001")
        self.assertEqual(Atendimento.objects.count(), 0)

    def test_comanda_com_atendimento_aberto_esta_em_atendimento(self):
        usuario = UsuarioOperacional.objects.create(
            nome="Garçom 1",
            papel=UsuarioOperacional.Papel.GARCOM,
        )
        comanda = ComandaFisica.objects.create(identificador="001")
        Atendimento.objects.create(comanda=comanda)

        resultado = consultar_estado_comanda(usuario.pk, "001")

        self.assertEqual(resultado.estado, EstadoComanda.EM_ATENDIMENTO)
        self.assertEqual(resultado.identificador, "001")

    def test_comanda_com_apenas_atendimento_encerrado_esta_disponivel(self):
        usuario = UsuarioOperacional.objects.create(
            nome="Garçom 1",
            papel=UsuarioOperacional.Papel.GARCOM,
        )
        comanda = ComandaFisica.objects.create(identificador="001")
        Atendimento.objects.create(
            comanda=comanda,
            estado=Atendimento.Estado.ENCERRADO,
        )

        resultado = consultar_estado_comanda(usuario.pk, "001")

        self.assertEqual(resultado.estado, EstadoComanda.DISPONIVEL)

    def test_identificador_e_textual_e_desconhecido_nao_cria_comanda(self):
        usuario = UsuarioOperacional.objects.create(
            nome="Garçom 1",
            papel=UsuarioOperacional.Papel.GARCOM,
        )
        ComandaFisica.objects.create(identificador="001")

        resultado = consultar_estado_comanda(usuario.pk, "1")

        self.assertEqual(resultado.estado, EstadoComanda.NAO_ENCONTRADA)
        self.assertIsNone(resultado.identificador)
        self.assertEqual(
            list(ComandaFisica.objects.values_list("identificador", flat=True)),
            ["001"],
        )

    def test_caixa_pode_consultar_comanda(self):
        usuario = UsuarioOperacional.objects.create(
            nome="Caixa 1",
            papel=UsuarioOperacional.Papel.CAIXA,
        )
        ComandaFisica.objects.create(identificador="020")

        resultado = consultar_estado_comanda(usuario.pk, "020")

        self.assertEqual(resultado.estado, EstadoComanda.DISPONIVEL)
        self.assertEqual(resultado.identificador, "020")

    def test_usuario_inexistente_ou_papel_invalido_e_rejeitado(self):
        usuario_sem_permissao = UsuarioOperacional.objects.create(
            nome="Gerente 1",
            papel="GERENTE",
        )

        with self.assertRaises(UsuarioOperacionalInvalido):
            consultar_estado_comanda(999_999, "001")
        with self.assertRaises(UsuarioOperacionalInvalido):
            consultar_estado_comanda("identificador-inválido", "001")
        with self.assertRaises(PapelNaoPermitido):
            consultar_estado_comanda(usuario_sem_permissao.pk, "001")
