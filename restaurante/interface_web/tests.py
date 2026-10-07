from django.test import TestCase

from restaurante.persistencia.models import UsuarioOperacional


class FluxoUsuarioOperacionalTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.garcom_1 = UsuarioOperacional.objects.create(
            nome="Garçom 1",
            papel=UsuarioOperacional.Papel.GARCOM,
        )
        cls.garcom_2 = UsuarioOperacional.objects.create(
            nome="Garçom 2",
            papel=UsuarioOperacional.Papel.GARCOM,
        )
        cls.caixa_1 = UsuarioOperacional.objects.create(
            nome="Caixa 1",
            papel=UsuarioOperacional.Papel.CAIXA,
        )

    def test_tela_inicial_lista_usuarios_e_papeis(self):
        resposta = self.client.get("/")

        self.assertEqual(resposta.status_code, 200)
        self.assertContains(resposta, '<html lang="pt-BR">', html=False)
        self.assertContains(resposta, "Selecionar usuário")
        self.assertContains(resposta, "Garçom 1")
        self.assertContains(resposta, "Garçom 2")
        self.assertContains(resposta, "Caixa 1")
        self.assertContains(resposta, "GARCOM", count=2)
        self.assertContains(resposta, "CAIXA", count=1)
        self.assertContains(resposta, "/static/interface_web/css/base.css")

    def test_selecionar_garcom_direciona_para_experiencia_de_garcom(self):
        resposta = self.client.post(
            "/usuarios/selecionar/",
            {"usuario_id": self.garcom_1.pk},
        )

        self.assertRedirects(resposta, "/garcom/", fetch_redirect_response=False)

        experiencia = self.client.get("/garcom/")
        self.assertEqual(experiencia.status_code, 200)
        self.assertContains(experiencia, "Experiência do Garçom")
        self.assertContains(experiencia, "Garçom 1")

    def test_selecionar_caixa_usa_papel_armazenado_no_backend(self):
        resposta = self.client.post(
            "/usuarios/selecionar/",
            {
                "usuario_id": self.caixa_1.pk,
                "papel": UsuarioOperacional.Papel.GARCOM,
            },
        )

        self.assertRedirects(resposta, "/caixa/", fetch_redirect_response=False)

        experiencia = self.client.get("/caixa/")
        self.assertEqual(experiencia.status_code, 200)
        self.assertContains(experiencia, "Experiência do Caixa")
        self.assertContains(experiencia, "Caixa 1")

        rota_de_outro_papel = self.client.get("/garcom/")
        self.assertRedirects(
            rota_de_outro_papel,
            "/caixa/",
            fetch_redirect_response=False,
        )

    def test_selecao_persiste_entre_requisicoes(self):
        self.client.post(
            "/usuarios/selecionar/",
            {"usuario_id": self.garcom_2.pk},
        )

        resposta = self.client.get("/")

        self.assertRedirects(resposta, "/garcom/", fetch_redirect_response=False)
        experiencia = self.client.get("/garcom/")
        self.assertContains(experiencia, "Garçom 2")

    def test_trocar_usuario_remove_selecao_e_retorna_a_tela_inicial(self):
        self.client.post(
            "/usuarios/selecionar/",
            {"usuario_id": self.garcom_1.pk},
        )

        resposta = self.client.post("/usuarios/trocar/")

        self.assertRedirects(resposta, "/", fetch_redirect_response=False)
        selecao = self.client.get("/")
        self.assertEqual(selecao.status_code, 200)
        self.assertContains(selecao, "Selecionar usuário")

    def test_selecao_com_identificador_inexistente_retorna_com_seguranca(self):
        for identificador in (999_999, "identificador-inválido"):
            with self.subTest(identificador=identificador):
                resposta = self.client.post(
                    "/usuarios/selecionar/",
                    {"usuario_id": identificador},
                    follow=True,
                )

                self.assertEqual(resposta.status_code, 200)
                self.assertContains(resposta, "Usuário operacional não encontrado")
                self.assertContains(resposta, "Selecionar usuário")

    def test_usuario_removido_descarta_selecao_persistida(self):
        self.client.post(
            "/usuarios/selecionar/",
            {"usuario_id": self.garcom_1.pk},
        )
        UsuarioOperacional.objects.filter(pk=self.garcom_1.pk).delete()

        resposta = self.client.get("/", follow=True)

        self.assertEqual(resposta.status_code, 200)
        self.assertContains(resposta, "Usuário operacional não encontrado")
        self.assertContains(resposta, "Selecionar usuário")
        self.assertEqual(self.client.get("/").status_code, 200)
