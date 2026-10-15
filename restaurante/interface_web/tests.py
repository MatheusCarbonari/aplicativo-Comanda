from django.test import TestCase

from restaurante.persistencia.models import (
    Atendimento,
    ComandaFisica,
    Lancamento,
    Produto,
    UsuarioOperacional,
)


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
        self.assertContains(experiencia, "Identificador da comanda")

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
        self.assertContains(experiencia, "Identificador da comanda")

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


class ConsultaComandaInterfaceTests(TestCase):
    def selecionar(self, usuario: UsuarioOperacional) -> None:
        self.client.post(
            "/usuarios/selecionar/",
            {"usuario_id": usuario.pk},
        )

    def test_garcom_consulta_comanda_disponivel_sem_criar_atendimento(self):
        usuario = UsuarioOperacional.objects.create(
            nome="Garçom 1",
            papel=UsuarioOperacional.Papel.GARCOM,
        )
        ComandaFisica.objects.create(identificador="001")
        self.selecionar(usuario)

        resposta = self.client.get(
            "/comandas/consultar/",
            {"identificador": "001"},
        )

        self.assertEqual(resposta.status_code, 200)
        self.assertContains(resposta, "Comanda 001")
        self.assertContains(
            resposta,
            "Comanda disponível — nenhum atendimento aberto",
        )
        self.assertEqual(Atendimento.objects.count(), 0)

    def test_caixa_consulta_comanda_em_atendimento(self):
        usuario = UsuarioOperacional.objects.create(
            nome="Caixa 1",
            papel=UsuarioOperacional.Papel.CAIXA,
        )
        comanda = ComandaFisica.objects.create(identificador="002")
        Atendimento.objects.create(comanda=comanda)
        self.selecionar(usuario)

        resposta = self.client.get(
            "/comandas/consultar/",
            {"identificador": "002"},
        )

        self.assertEqual(resposta.status_code, 200)
        self.assertContains(resposta, "Comanda 002")
        self.assertContains(resposta, "Em atendimento")

    def test_comanda_desconhecida_nao_e_criada(self):
        usuario = UsuarioOperacional.objects.create(
            nome="Garçom 1",
            papel=UsuarioOperacional.Papel.GARCOM,
        )
        self.selecionar(usuario)

        resposta = self.client.get(
            "/comandas/consultar/",
            {"identificador": "999"},
        )

        self.assertEqual(resposta.status_code, 200)
        self.assertContains(resposta, "Comanda não encontrada")
        self.assertEqual(ComandaFisica.objects.count(), 0)
        self.assertEqual(Atendimento.objects.count(), 0)

    def test_consulta_sem_usuario_retorna_a_selecao(self):
        resposta = self.client.get(
            "/comandas/consultar/",
            {"identificador": "001"},
        )

        self.assertRedirects(
            resposta,
            "/?selecao_invalida=1",
            fetch_redirect_response=False,
        )


class PrimeiroLancamentoInterfaceTests(TestCase):
    def setUp(self):
        self.garcom = UsuarioOperacional.objects.create(
            nome="Garçom 1",
            papel=UsuarioOperacional.Papel.GARCOM,
        )
        self.caixa = UsuarioOperacional.objects.create(
            nome="Caixa 1",
            papel=UsuarioOperacional.Papel.CAIXA,
        )
        self.comanda = ComandaFisica.objects.create(identificador="001")
        self.produto = Produto.objects.create(
            nome="Batata frita",
            preco_centavos=2000,
        )

    def selecionar(self, usuario: UsuarioOperacional) -> None:
        self.client.post(
            "/usuarios/selecionar/",
            {"usuario_id": usuario.pk},
        )

    def test_garcom_ve_formulario_de_primeiro_lancamento(self):
        self.selecionar(self.garcom)

        resposta = self.client.get("/garcom/")

        self.assertEqual(resposta.status_code, 200)
        self.assertContains(resposta, "Registrar primeiro lançamento")
        self.assertContains(resposta, "Batata frita")
        self.assertContains(resposta, 'name="quantidade"', html=False)

    def test_caixa_nao_ve_nem_pode_usar_acao_de_lancamento(self):
        self.selecionar(self.caixa)

        pagina = self.client.get("/caixa/")
        resposta = self.client.post(
            "/lancamentos/primeiro/",
            {
                "identificador_comanda": "001",
                "produto_id": self.produto.pk,
                "quantidade": "1",
            },
        )

        self.assertNotContains(pagina, "Registrar primeiro lançamento")
        self.assertEqual(resposta.status_code, 403)
        self.assertEqual(Atendimento.objects.count(), 0)
        self.assertEqual(Lancamento.objects.count(), 0)

    def test_lancamento_valido_mostra_dados_criados_e_total_em_brl(self):
        self.selecionar(self.garcom)

        resposta = self.client.post(
            "/lancamentos/primeiro/",
            {
                "identificador_comanda": "001",
                "produto_id": self.produto.pk,
                "quantidade": "2",
            },
        )

        self.assertEqual(resposta.status_code, 200)
        self.assertContains(resposta, "Lançamento registrado")
        self.assertContains(resposta, "Comanda 001")
        self.assertContains(resposta, "Batata frita")
        self.assertContains(resposta, "Quantidade: 2")
        self.assertContains(resposta, "R$ 40,00")
        self.assertContains(resposta, "Em atendimento")
        self.assertEqual(Atendimento.objects.count(), 1)
        self.assertEqual(Lancamento.objects.count(), 1)

    def test_entrada_invalida_exibe_erro_sem_criar_estado_parcial(self):
        self.selecionar(self.garcom)
        cenarios = (
            (
                {"identificador_comanda": "999", "produto_id": self.produto.pk, "quantidade": "1"},
                "Comanda não encontrada",
            ),
            (
                {"identificador_comanda": "001", "produto_id": "999999", "quantidade": "1"},
                "Produto não encontrado",
            ),
            (
                {"identificador_comanda": "001", "produto_id": self.produto.pk, "quantidade": "1.5"},
                "Informe uma quantidade inteira positiva",
            ),
        )

        for dados, mensagem in cenarios:
            with self.subTest(mensagem=mensagem):
                resposta = self.client.post("/lancamentos/primeiro/", dados)

                self.assertEqual(resposta.status_code, 400)
                self.assertContains(resposta, mensagem, status_code=400)
                self.assertEqual(Atendimento.objects.count(), 0)
                self.assertEqual(Lancamento.objects.count(), 0)


class LancamentoAdicionalInterfaceTests(TestCase):
    def setUp(self):
        self.garcom = UsuarioOperacional.objects.create(
            nome="Garçom 1",
            papel=UsuarioOperacional.Papel.GARCOM,
        )
        self.caixa = UsuarioOperacional.objects.create(
            nome="Caixa 1",
            papel=UsuarioOperacional.Papel.CAIXA,
        )
        self.comanda = ComandaFisica.objects.create(identificador="001")
        self.atendimento = Atendimento.objects.create(comanda=self.comanda)
        self.cafe = Produto.objects.create(nome="Café", preco_centavos=600)
        self.pizza = Produto.objects.create(nome="Pizza", preco_centavos=4500)

    def selecionar(self, usuario: UsuarioOperacional) -> None:
        self.client.post(
            "/usuarios/selecionar/",
            {"usuario_id": usuario.pk},
        )

    def test_garcom_ve_acao_ao_consultar_comanda_em_atendimento(self):
        self.selecionar(self.garcom)

        resposta = self.client.get(
            "/comandas/consultar/",
            {"identificador": "001"},
        )

        self.assertEqual(resposta.status_code, 200)
        self.assertContains(resposta, "Adicionar consumo")
        self.assertContains(resposta, "Café")
        self.assertContains(resposta, "Pizza")

    def test_caixa_nao_ve_nem_pode_usar_acao_adicional(self):
        self.selecionar(self.caixa)

        pagina = self.client.get(
            "/comandas/consultar/",
            {"identificador": "001"},
        )
        resposta = self.client.post(
            "/lancamentos/adicional/",
            {
                "identificador_comanda": "001",
                "produto_id": self.cafe.pk,
                "quantidade": "1",
            },
        )

        self.assertNotContains(pagina, "Adicionar consumo")
        self.assertEqual(resposta.status_code, 403)
        self.assertEqual(Lancamento.objects.count(), 0)

    def test_dois_lancamentos_sucessivos_continuam_independentes(self):
        self.selecionar(self.garcom)

        for quantidade in ("1", "2"):
            resposta = self.client.post(
                "/lancamentos/adicional/",
                {
                    "identificador_comanda": "001",
                    "produto_id": self.cafe.pk,
                    "quantidade": quantidade,
                },
            )
            self.assertEqual(resposta.status_code, 200)

        lancamentos = list(self.atendimento.lancamentos.order_by("pk"))
        self.assertEqual(len(lancamentos), 2)
        self.assertEqual(
            [lancamento.quantidade for lancamento in lancamentos],
            [1, 2],
        )

    def test_total_atual_e_exibido_em_brl(self):
        Lancamento.objects.create(
            atendimento=self.atendimento,
            produto=self.cafe,
            quantidade=2,
            preco_unitario_centavos=600,
            autor=self.garcom,
        )
        self.selecionar(self.garcom)

        resposta = self.client.post(
            "/lancamentos/adicional/",
            {
                "identificador_comanda": "001",
                "produto_id": self.pizza.pk,
                "quantidade": "1",
            },
        )

        self.assertEqual(resposta.status_code, 200)
        self.assertContains(resposta, "Lançamento registrado")
        self.assertContains(resposta, "Comanda 001")
        self.assertContains(resposta, "Pizza")
        self.assertContains(resposta, "Quantidade: 1")
        self.assertContains(resposta, "Total atual")
        self.assertContains(resposta, "R$ 57,00")

    def test_atendimento_encerrado_exibe_erro_sem_criar_lancamento(self):
        self.atendimento.estado = Atendimento.Estado.ENCERRADO
        self.atendimento.save(update_fields=["estado"])
        self.selecionar(self.garcom)

        resposta = self.client.post(
            "/lancamentos/adicional/",
            {
                "identificador_comanda": "001",
                "produto_id": self.cafe.pk,
                "quantidade": "1",
            },
        )

        self.assertEqual(resposta.status_code, 400)
        self.assertContains(
            resposta,
            "Nenhum atendimento aberto para esta Comanda",
            status_code=400,
        )
        self.assertEqual(Lancamento.objects.count(), 0)
