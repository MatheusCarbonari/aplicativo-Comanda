import re
from datetime import UTC, datetime
from uuid import UUID

from django.db import OperationalError, connection
from django.test import TestCase

from restaurante.persistencia.models import (
    Atendimento,
    CancelamentoLancamento,
    ComandaFisica,
    Lancamento,
    Produto,
    RegistroIdempotencia,
    UsuarioOperacional,
)


class FolhaCodigosBarrasTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        ComandaFisica.objects.bulk_create(
            [
                ComandaFisica(identificador=f"{numero:03d}")
                for numero in range(1, 22)
            ]
        )

    def test_mostra_exatamente_as_comandas_de_001_a_020(self):
        resposta = self.client.get("/utilitarios/codigos-barras/")

        identificadores = re.findall(
            rb'data-identificador="([^"]+)"',
            resposta.content,
        )
        self.assertEqual(resposta.status_code, 200)
        self.assertEqual(
            identificadores,
            [f"{numero:03d}".encode() for numero in range(1, 21)],
        )

    def test_cada_comanda_tem_code_128_e_texto_legivel(self):
        resposta = self.client.get("/utilitarios/codigos-barras/")

        conteudos_codificados = re.findall(
            rb'data-code128="([^"]+)"',
            resposta.content,
        )
        self.assertEqual(
            conteudos_codificados,
            [f"{numero:03d}".encode() for numero in range(1, 21)],
        )
        self.assertContains(
            resposta,
            'data-simbologia="Code 128"',
            count=20,
            html=False,
        )
        for numero in range(1, 21):
            self.assertContains(
                resposta,
                f'<span class="identificador-comanda">{numero:03d}</span>',
                html=True,
            )

    def test_svgs_contem_barras_e_geometria_code_128_valida(self):
        resposta = self.client.get("/utilitarios/codigos-barras/")

        svgs = re.findall(
            rb'<svg[^>]+data-code128="([^"]+)"[^>]*>(.*?)</svg>',
            resposta.content,
            flags=re.DOTALL,
        )
        self.assertEqual(len(svgs), 20)
        for _, conteudo_svg in svgs:
            self.assertEqual(conteudo_svg.count(b"<rect "), 19)

        barras_001 = re.findall(
            rb'<rect x="(\d+)" y="0" width="(\d+)" height="50">',
            svgs[0][1],
        )
        self.assertEqual(
            barras_001,
            [
                (b"10", b"2"), (b"13", b"1"), (b"16", b"1"),
                (b"21", b"1"), (b"24", b"3"), (b"28", b"2"),
                (b"32", b"1"), (b"35", b"3"), (b"39", b"2"),
                (b"43", b"1"), (b"46", b"3"), (b"51", b"2"),
                (b"54", b"1"), (b"56", b"4"), (b"61", b"3"),
                (b"65", b"2"), (b"70", b"3"), (b"74", b"1"),
                (b"76", b"2"),
            ],
        )

    def test_avisa_uso_de_teste_e_usa_somente_recursos_locais(self):
        resposta = self.client.get("/utilitarios/codigos-barras/")

        self.assertContains(
            resposta,
            "Uso exclusivo para desenvolvimento e demonstração.",
        )
        self.assertContains(
            resposta,
            "Não é recibo, documento fiscal ou Comanda operacional.",
        )
        self.assertContains(
            resposta,
            "/static/interface_web/css/folha_codigos_barras.css",
        )
        self.assertNotContains(resposta, "https://")
        self.assertNotContains(resposta, "http://")
        self.assertNotContains(resposta, "//cdn")


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
        self.assertContains(resposta, 'name="chave_idempotencia"', html=False)
        self.assertContains(
            resposta,
            "/static/interface_web/js/atualizacao_periodica.mjs",
        )
        UUID(resposta.context["chave_idempotencia"])

    def test_nova_renderizacao_gera_nova_chave(self):
        self.selecionar(self.garcom)

        primeira = self.client.get("/garcom/")
        segunda = self.client.get("/garcom/")

        self.assertNotEqual(
            primeira.context["chave_idempotencia"],
            segunda.context["chave_idempotencia"],
        )

    def test_caixa_nao_ve_nem_pode_usar_acao_de_lancamento(self):
        self.selecionar(self.caixa)

        pagina = self.client.get("/caixa/")
        resposta = self.client.post(
            "/lancamentos/primeiro/",
            {
                "identificador_comanda": "001",
                "produto_id": self.produto.pk,
                "quantidade": "1",
                "chave_idempotencia": "caixa-primeiro",
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
                "chave_idempotencia": "primeiro-interface",
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

    def test_reenvio_da_mesma_requisicao_nao_duplica_lancamento(self):
        self.selecionar(self.garcom)
        dados = {
            "identificador_comanda": "001",
            "produto_id": self.produto.pk,
            "quantidade": "1",
            "chave_idempotencia": "toque-duplo-primeiro",
        }

        primeira = self.client.post("/lancamentos/primeiro/", dados)
        repetida = self.client.post("/lancamentos/primeiro/", dados)

        self.assertEqual(primeira.status_code, 200)
        self.assertEqual(repetida.status_code, 200)
        self.assertEqual(Atendimento.objects.count(), 1)
        self.assertEqual(Lancamento.objects.count(), 1)

    def test_reutilizar_chave_com_outro_conteudo_retorna_conflito(self):
        self.selecionar(self.garcom)
        dados = {
            "identificador_comanda": "001",
            "produto_id": self.produto.pk,
            "quantidade": "1",
            "chave_idempotencia": "conflito-interface",
        }
        self.client.post("/lancamentos/primeiro/", dados)
        dados["quantidade"] = "2"

        resposta = self.client.post("/lancamentos/primeiro/", dados)

        self.assertEqual(resposta.status_code, 409)
        self.assertContains(
            resposta,
            "Esta tentativa já foi usada com dados diferentes",
            status_code=409,
        )
        self.assertEqual(Lancamento.objects.count(), 1)

    def test_entrada_invalida_exibe_erro_sem_criar_estado_parcial(self):
        self.selecionar(self.garcom)
        cenarios = (
            (
                {"identificador_comanda": "999", "produto_id": self.produto.pk, "quantidade": "1", "chave_idempotencia": "comanda-invalida"},
                "Comanda não encontrada",
            ),
            (
                {"identificador_comanda": "001", "produto_id": "999999", "quantidade": "1", "chave_idempotencia": "produto-invalido"},
                "Produto não encontrado",
            ),
            (
                {"identificador_comanda": "001", "produto_id": self.produto.pk, "quantidade": "1.5", "chave_idempotencia": "quantidade-invalida"},
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

    def test_contencao_sqlite_persistente_informa_indisponibilidade_temporaria(
        self,
    ):
        self.selecionar(self.garcom)

        def conter_insercao(execute, sql, params, many, context):
            if 'insert into "persistencia_atendimento"' in sql.lower():
                raise OperationalError("database is locked")
            return execute(sql, params, many, context)

        with connection.execute_wrapper(conter_insercao):
            resposta = self.client.post(
                "/lancamentos/primeiro/",
                {
                    "identificador_comanda": "001",
                    "produto_id": self.produto.pk,
                    "quantidade": "1",
                    "chave_idempotencia": "contencao-interface",
                },
            )

        self.assertEqual(resposta.status_code, 503)
        self.assertContains(
            resposta,
            "Banco ocupado temporariamente. Tente novamente",
            status_code=503,
        )
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
        self.assertContains(resposta, 'name="chave_idempotencia"', html=False)

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
                "chave_idempotencia": "caixa-adicional",
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
                    "chave_idempotencia": f"adicional-{quantidade}",
                },
            )
            self.assertEqual(resposta.status_code, 200)

        lancamentos = list(self.atendimento.lancamentos.order_by("pk"))
        self.assertEqual(len(lancamentos), 2)
        self.assertEqual(
            [lancamento.quantidade for lancamento in lancamentos],
            [1, 2],
        )

    def test_reenvio_da_mesma_requisicao_adicional_nao_duplica(self):
        self.selecionar(self.garcom)
        dados = {
            "identificador_comanda": "001",
            "produto_id": self.cafe.pk,
            "quantidade": "1",
            "chave_idempotencia": "toque-duplo-adicional",
        }

        primeira = self.client.post("/lancamentos/adicional/", dados)
        repetida = self.client.post("/lancamentos/adicional/", dados)

        self.assertEqual(primeira.status_code, 200)
        self.assertEqual(repetida.status_code, 200)
        self.assertEqual(self.atendimento.lancamentos.count(), 1)

    def test_contencao_persistente_retorna_503_sem_lancamento_parcial(self):
        self.selecionar(self.garcom)
        tentativas = 0

        def bloquear_insercao(execute, sql, params, many, context):
            nonlocal tentativas
            if 'insert into "persistencia_lancamento"' in sql.lower():
                tentativas += 1
                raise OperationalError("database is locked")
            return execute(sql, params, many, context)

        with connection.execute_wrapper(bloquear_insercao):
            resposta = self.client.post(
                "/lancamentos/adicional/",
                {
                    "identificador_comanda": "001",
                    "produto_id": self.cafe.pk,
                    "quantidade": "1",
                    "chave_idempotencia": "contencao-adicional-interface",
                },
            )

        self.assertEqual(resposta.status_code, 503)
        self.assertContains(
            resposta,
            "Banco ocupado temporariamente. Tente novamente",
            status_code=503,
        )
        self.assertEqual(tentativas, 2)
        self.assertEqual(Lancamento.objects.count(), 0)
        self.assertFalse(
            RegistroIdempotencia.objects.filter(
                chave="contencao-adicional-interface"
            ).exists()
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
                "chave_idempotencia": "total-interface",
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
                "chave_idempotencia": "atendimento-encerrado",
            },
        )

        self.assertEqual(resposta.status_code, 400)
        self.assertContains(
            resposta,
            "Nenhum atendimento aberto para esta Comanda",
            status_code=400,
        )
        self.assertEqual(Lancamento.objects.count(), 0)


class CancelamentoLancamentoInterfaceTests(TestCase):
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
        self.lancamento_cafe = Lancamento.objects.create(
            atendimento=self.atendimento,
            produto=self.cafe,
            quantidade=2,
            preco_unitario_centavos=600,
            autor=self.garcom,
        )
        Lancamento.objects.create(
            atendimento=self.atendimento,
            produto=self.pizza,
            quantidade=1,
            preco_unitario_centavos=4500,
            autor=self.garcom,
        )

    def selecionar(self, usuario):
        self.client.post("/usuarios/selecionar/", {"usuario_id": usuario.pk})

    def test_garcom_cancela_lancamento_valido_e_total_e_atualizado(self):
        self.selecionar(self.garcom)
        consulta = self.client.get(
            "/comandas/consultar/",
            {"identificador": "001"},
        )

        self.assertContains(consulta, "Cancelar lançamento")
        self.assertContains(consulta, "Produto incorreto")
        self.assertContains(consulta, "Quantidade incorreta")
        chave = consulta.context["acoes_cancelamento"][0]["chave"]

        resposta = self.client.post(
            "/lancamentos/cancelar/",
            {
                "lancamento_id": self.lancamento_cafe.pk,
                "motivo": CancelamentoLancamento.Motivo.OUTRO,
                "descricao": "Cliente mudou o pedido",
                "chave_idempotencia": chave,
            },
        )

        self.assertEqual(resposta.status_code, 200)
        self.assertContains(resposta, "Lançamento cancelado")
        self.assertContains(resposta, "R$ 45,00")
        self.assertTrue(
            Lancamento.objects.filter(pk=self.lancamento_cafe.pk).exists()
        )
        self.assertEqual(CancelamentoLancamento.objects.count(), 1)

    def test_caixa_nao_ve_nem_pode_cancelar(self):
        self.selecionar(self.caixa)

        consulta = self.client.get(
            "/comandas/consultar/",
            {"identificador": "001"},
        )
        resposta = self.client.post(
            "/lancamentos/cancelar/",
            {
                "lancamento_id": self.lancamento_cafe.pk,
                "motivo": CancelamentoLancamento.Motivo.DUPLICADO,
                "descricao": "",
                "chave_idempotencia": "caixa-cancelamento",
            },
        )

        self.assertNotContains(consulta, "Cancelar lançamento")
        self.assertEqual(resposta.status_code, 403)
        self.assertEqual(CancelamentoLancamento.objects.count(), 0)

    def test_outro_sem_descricao_exibe_validacao_sem_cancelar(self):
        self.selecionar(self.garcom)

        resposta = self.client.post(
            "/lancamentos/cancelar/",
            {
                "lancamento_id": self.lancamento_cafe.pk,
                "motivo": CancelamentoLancamento.Motivo.OUTRO,
                "descricao": " ",
                "chave_idempotencia": "outro-interface",
            },
        )

        self.assertEqual(resposta.status_code, 400)
        self.assertContains(
            resposta,
            "Informe uma descrição quando o motivo for Outro",
            status_code=400,
        )
        self.assertEqual(CancelamentoLancamento.objects.count(), 0)

    def test_contencao_persistente_retorna_503_sem_cancelar(self):
        self.selecionar(self.garcom)
        tentativas = 0

        def bloquear_insercao(execute, sql, params, many, context):
            nonlocal tentativas
            if 'insert into "persistencia_cancelamentolancamento"' in sql.lower():
                tentativas += 1
                raise OperationalError("database is locked")
            return execute(sql, params, many, context)

        with connection.execute_wrapper(bloquear_insercao):
            resposta = self.client.post(
                "/lancamentos/cancelar/",
                {
                    "lancamento_id": self.lancamento_cafe.pk,
                    "motivo": CancelamentoLancamento.Motivo.DUPLICADO,
                    "descricao": "",
                    "chave_idempotencia": "contencao-interface",
                },
            )

        self.assertEqual(resposta.status_code, 503)
        self.assertContains(
            resposta,
            "Banco ocupado temporariamente. Tente novamente",
            status_code=503,
        )
        self.assertEqual(tentativas, 2)
        self.assertEqual(CancelamentoLancamento.objects.count(), 0)

    def test_consulta_exibe_total_zero_apos_cancelar_todos(self):
        self.selecionar(self.garcom)
        Lancamento.objects.exclude(pk=self.lancamento_cafe.pk).delete()
        CancelamentoLancamento.objects.create(
            lancamento=self.lancamento_cafe,
            motivo=CancelamentoLancamento.Motivo.DESISTENCIA,
            descricao="",
            autor=self.garcom,
        )

        resposta = self.client.get(
            "/comandas/consultar/",
            {"identificador": "001"},
        )

        self.assertContains(resposta, "R$ 0,00")
        self.assertNotContains(resposta, "Cancelar lançamento")


class HistoricoCancelamentosInterfaceTests(TestCase):
    def setUp(self):
        self.garcom = UsuarioOperacional.objects.create(
            nome="Garçom 1",
            papel=UsuarioOperacional.Papel.GARCOM,
        )
        self.outro_garcom = UsuarioOperacional.objects.create(
            nome="Garçom 2",
            papel=UsuarioOperacional.Papel.GARCOM,
        )
        self.comanda = ComandaFisica.objects.create(identificador="001")
        self.atendimento = Atendimento.objects.create(comanda=self.comanda)
        self.cafe = Produto.objects.create(nome="Café", preco_centavos=600)
        self.pizza = Produto.objects.create(nome="Pizza", preco_centavos=4500)

    def selecionar_garcom(self):
        self.client.post(
            "/usuarios/selecionar/",
            {"usuario_id": self.garcom.pk},
        )

    def consultar(self):
        return self.client.get(
            "/comandas/consultar/",
            {"identificador": "001"},
        )

    def test_separa_consumos_validos_dos_cancelados_e_calcula_total(self):
        cancelado = Lancamento.objects.create(
            atendimento=self.atendimento,
            produto=self.cafe,
            quantidade=2,
            preco_unitario_centavos=600,
            autor=self.garcom,
        )
        Lancamento.objects.create(
            atendimento=self.atendimento,
            produto=self.pizza,
            quantidade=1,
            preco_unitario_centavos=4500,
            autor=self.outro_garcom,
        )
        CancelamentoLancamento.objects.create(
            lancamento=cancelado,
            motivo=CancelamentoLancamento.Motivo.DUPLICADO,
            descricao="",
            autor=self.outro_garcom,
        )
        self.selecionar_garcom()

        resposta = self.consultar()

        html = resposta.content.decode()
        consumos_validos = html.split('id="consumos-validos"', 1)[1].split(
            "</section>", 1
        )[0]
        historico = html.split('id="historico-cancelamentos"', 1)[1].split(
            "</section>", 1
        )[0]
        self.assertIn("Pizza", consumos_validos)
        self.assertNotIn("Café", consumos_validos)
        self.assertIn("Café", historico)
        self.assertNotIn("Pizza", historico)
        self.assertContains(resposta, "R$ 45,00")

    def test_historico_mostra_dados_e_horarios_em_sao_paulo(self):
        lancamento = Lancamento.objects.create(
            atendimento=self.atendimento,
            produto=self.cafe,
            quantidade=3,
            preco_unitario_centavos=600,
            autor=self.garcom,
        )
        cancelamento = CancelamentoLancamento.objects.create(
            lancamento=lancamento,
            motivo=CancelamentoLancamento.Motivo.OUTRO,
            descricao="Cliente mudou de ideia",
            autor=self.outro_garcom,
        )
        Lancamento.objects.filter(pk=lancamento.pk).update(
            horario=datetime(2026, 1, 15, 15, 30, tzinfo=UTC)
        )
        CancelamentoLancamento.objects.filter(pk=cancelamento.pk).update(
            horario=datetime(2026, 1, 15, 16, 45, tzinfo=UTC)
        )
        self.selecionar_garcom()

        resposta = self.consultar()

        self.assertContains(resposta, "Café")
        self.assertContains(resposta, "Quantidade: 3")
        self.assertContains(resposta, "Preço unitário original: R$ 6,00")
        self.assertContains(resposta, "Autor do lançamento: Garçom 1")
        self.assertContains(resposta, "Lançado em: 15/01/2026 12:30")
        self.assertContains(resposta, "Autor do cancelamento: Garçom 2")
        self.assertContains(resposta, "Cancelado em: 15/01/2026 13:45")
        self.assertContains(resposta, "Motivo: Outro")
        self.assertContains(resposta, "Descrição: Cliente mudou de ideia")

    def test_historico_mostra_multiplos_cancelamentos(self):
        cafe = Lancamento.objects.create(
            atendimento=self.atendimento,
            produto=self.cafe,
            quantidade=1,
            preco_unitario_centavos=600,
            autor=self.garcom,
        )
        pizza = Lancamento.objects.create(
            atendimento=self.atendimento,
            produto=self.pizza,
            quantidade=2,
            preco_unitario_centavos=4500,
            autor=self.outro_garcom,
        )
        CancelamentoLancamento.objects.create(
            lancamento=cafe,
            motivo=CancelamentoLancamento.Motivo.DUPLICADO,
            descricao="",
            autor=self.outro_garcom,
        )
        CancelamentoLancamento.objects.create(
            lancamento=pizza,
            motivo=CancelamentoLancamento.Motivo.PRODUTO_INCORRETO,
            descricao="Item escolhido incorretamente",
            autor=self.garcom,
        )
        self.selecionar_garcom()

        resposta = self.consultar()

        html = resposta.content.decode()
        historico = html.split('id="historico-cancelamentos"', 1)[1].split(
            "</section>", 1
        )[0]
        self.assertIn("Café", historico)
        self.assertIn("Pizza", historico)
        self.assertIn("Motivo: Duplicado", historico)
        self.assertIn("Motivo: Produto incorreto", historico)
        self.assertEqual(historico.count("Descrição:"), 1)

    def test_todos_cancelados_mantem_atendimento_aberto_e_total_zero(self):
        lancamento = Lancamento.objects.create(
            atendimento=self.atendimento,
            produto=self.cafe,
            quantidade=1,
            preco_unitario_centavos=600,
            autor=self.garcom,
        )
        CancelamentoLancamento.objects.create(
            lancamento=lancamento,
            motivo=CancelamentoLancamento.Motivo.DESISTENCIA,
            descricao="",
            autor=self.garcom,
        )
        self.selecionar_garcom()

        resposta = self.consultar()

        self.atendimento.refresh_from_db()
        self.assertEqual(self.atendimento.estado, Atendimento.Estado.ABERTO)
        self.assertContains(resposta, "Em atendimento")
        self.assertContains(resposta, "R$ 0,00")
        self.assertContains(resposta, "Lançamentos cancelados")
        self.assertNotContains(resposta, 'id="consumos-validos"', html=False)

    def test_sem_cancelamentos_nao_exibe_secao_vazia(self):
        Lancamento.objects.create(
            atendimento=self.atendimento,
            produto=self.cafe,
            quantidade=1,
            preco_unitario_centavos=600,
            autor=self.garcom,
        )
        self.selecionar_garcom()

        resposta = self.consultar()

        self.assertContains(resposta, "Consumos válidos")
        self.assertNotContains(resposta, "Lançamentos cancelados")


class ConsultaComandaCaixaInterfaceTests(TestCase):
    def setUp(self):
        self.caixa = UsuarioOperacional.objects.create(
            nome="Caixa 1",
            papel=UsuarioOperacional.Papel.CAIXA,
        )
        self.garcom = UsuarioOperacional.objects.create(
            nome="Garçom 1",
            papel=UsuarioOperacional.Papel.GARCOM,
        )
        self.comanda = ComandaFisica.objects.create(identificador="001")
        self.atendimento = Atendimento.objects.create(comanda=self.comanda)

    def selecionar(self, usuario):
        self.client.post(
            "/usuarios/selecionar/",
            {"usuario_id": usuario.pk},
        )

    def test_backend_permite_caixa_e_rejeita_garcom(self):
        self.selecionar(self.caixa)
        resposta_caixa = self.client.get(
            "/caixa/comandas/consultar/",
            {"identificador": "001"},
        )

        self.selecionar(self.garcom)
        resposta_garcom = self.client.get(
            "/caixa/comandas/consultar/",
            {"identificador": "001"},
        )

        self.assertEqual(resposta_caixa.status_code, 200)
        self.assertContains(resposta_caixa, "Resumo do atendimento")
        self.assertEqual(resposta_garcom.status_code, 403)

    def test_experiencia_do_caixa_envia_consulta_para_rota_protegida(self):
        self.selecionar(self.caixa)

        resposta = self.client.get("/caixa/")

        self.assertContains(
            resposta,
            'action="/caixa/comandas/consultar/"',
            html=False,
        )

    def test_campo_de_consulta_e_textual_preserva_zeros_e_recebe_foco(self):
        self.selecionar(self.caixa)

        pagina_inicial = self.client.get("/caixa/")
        resultado = self.client.get(
            "/caixa/comandas/consultar/",
            {"identificador": "001"},
        )

        self.assertContains(pagina_inicial, 'type="text"', html=False)
        self.assertContains(pagina_inicial, "autofocus", html=False)
        self.assertContains(resultado, "Comanda 001")
        self.assertContains(resultado, 'value="001"', html=False)

    def test_enter_e_clique_submetem_o_mesmo_formulario_get(self):
        self.selecionar(self.caixa)

        pagina_inicial = self.client.get("/caixa/")
        resposta_enter = self.client.get(
            "/caixa/comandas/consultar/?identificador=001"
        )
        resposta_clique = self.client.get(
            "/caixa/comandas/consultar/",
            {"identificador": "001"},
        )

        self.assertContains(
            pagina_inicial,
            '<form class="formulario-consulta" method="get" '
            'action="/caixa/comandas/consultar/">',
            html=False,
        )
        self.assertContains(
            pagina_inicial,
            '<button type="submit">Consultar</button>',
            html=True,
        )
        self.assertEqual(resposta_enter.status_code, 200)
        self.assertEqual(resposta_clique.status_code, 200)
        self.assertEqual(
            resposta_enter.context["mensagem"],
            resposta_clique.context["mensagem"],
        )
        self.assertEqual(
            resposta_enter.context["identificador"],
            resposta_clique.context["identificador"],
        )

    def test_mensagens_de_comanda_desconhecida_e_disponivel_sao_mantidas(self):
        ComandaFisica.objects.create(identificador="002")
        self.selecionar(self.caixa)

        disponivel = self.client.get(
            "/caixa/comandas/consultar/",
            {"identificador": "002"},
        )
        desconhecida = self.client.get(
            "/caixa/comandas/consultar/",
            {"identificador": "999"},
        )

        self.assertContains(
            disponivel,
            "Comanda disponível — nenhum atendimento aberto",
        )
        self.assertContains(desconhecida, "Comanda não encontrada")

    def test_consolida_produto_e_preco_sem_juntar_precos_diferentes(self):
        cafe = Produto.objects.create(nome="Café", preco_centavos=700)
        for quantidade, preco in ((1, 600), (2, 600), (1, 700)):
            Lancamento.objects.create(
                atendimento=self.atendimento,
                produto=cafe,
                quantidade=quantidade,
                preco_unitario_centavos=preco,
                autor=self.garcom,
            )
        self.selecionar(self.caixa)

        resposta = self.client.get(
            "/caixa/comandas/consultar/",
            {"identificador": "001"},
        )

        self.assertContains(
            resposta,
            "Café | qtd 3 | R$ 6,00 | subtotal R$ 18,00",
        )
        self.assertContains(
            resposta,
            "Café | qtd 1 | R$ 7,00 | subtotal R$ 7,00",
        )
        self.assertContains(resposta, "Total atual: R$ 25,00")

    def test_cancelados_ficam_fora_do_resumo_e_historico_permanece(self):
        cafe = Produto.objects.create(nome="Café", preco_centavos=600)
        valido = Lancamento.objects.create(
            atendimento=self.atendimento,
            produto=cafe,
            quantidade=2,
            preco_unitario_centavos=600,
            autor=self.garcom,
        )
        cancelado = Lancamento.objects.create(
            atendimento=self.atendimento,
            produto=cafe,
            quantidade=4,
            preco_unitario_centavos=600,
            autor=self.garcom,
        )
        CancelamentoLancamento.objects.create(
            lancamento=cancelado,
            motivo=CancelamentoLancamento.Motivo.QUANTIDADE_INCORRETA,
            descricao="Quantidade digitada incorretamente",
            autor=self.garcom,
        )
        quantidade_antes = Lancamento.objects.count()
        self.selecionar(self.caixa)

        resposta = self.client.get(
            "/caixa/comandas/consultar/",
            {"identificador": "001"},
        )

        self.assertContains(
            resposta,
            "Café | qtd 2 | R$ 6,00 | subtotal R$ 12,00",
        )
        self.assertNotContains(resposta, "Café | qtd 6")
        self.assertContains(resposta, "Total atual: R$ 12,00")
        self.assertContains(resposta, "Lançamentos cancelados")
        self.assertContains(resposta, "Motivo: Quantidade incorreta")
        self.assertContains(
            resposta,
            "Descrição: Quantidade digitada incorretamente",
        )
        self.assertEqual(Lancamento.objects.count(), quantidade_antes)
        self.assertTrue(Lancamento.objects.filter(pk=valido.pk).exists())
        self.assertTrue(Lancamento.objects.filter(pk=cancelado.pk).exists())

    def test_caixa_confere_resumo_antes_de_confirmar_fechamento(self):
        cafe = Produto.objects.create(nome="Café", preco_centavos=600)
        Lancamento.objects.create(
            atendimento=self.atendimento,
            produto=cafe,
            quantidade=2,
            preco_unitario_centavos=600,
            autor=self.garcom,
        )
        self.selecionar(self.caixa)

        consulta = self.client.get(
            "/caixa/comandas/consultar/",
            {"identificador": "001"},
        )
        conferencia = self.client.get(
            f"/caixa/atendimentos/{self.atendimento.pk}/fechar/"
        )

        self.assertContains(
            consulta,
            f'href="/caixa/atendimentos/{self.atendimento.pk}/fechar/"',
            html=False,
        )
        self.assertEqual(conferencia.status_code, 200)
        self.assertContains(conferencia, "Confirmar fechamento")
        self.assertContains(conferencia, "Comanda 001")
        self.assertContains(
            conferencia,
            "Café | qtd 2 | R$ 6,00 | subtotal R$ 12,00",
        )
        self.assertContains(conferencia, "Total atual: R$ 12,00")
        self.assertContains(
            conferencia,
            "O fechamento é irreversível.",
        )
        self.assertContains(
            conferencia,
            '<button type="submit">Fechar atendimento</button>',
            html=True,
        )
        self.assertContains(
            conferencia,
            'name="chave_idempotencia"',
            html=False,
        )
        self.assertContains(
            conferencia,
            f'name="revisao" value="{conferencia.context["revisao"]}"',
            html=False,
        )
        self.assertEqual(len(conferencia.context["revisao"]), 64)
        self.atendimento.refresh_from_db()
        self.assertEqual(self.atendimento.estado, Atendimento.Estado.ABERTO)

    def test_caixa_confirma_fechamento_com_total_zero_por_post(self):
        self.selecionar(self.caixa)
        url = f"/caixa/atendimentos/{self.atendimento.pk}/fechar/"
        conferencia = self.client.get(url)

        resposta = self.client.post(
            url,
            {
                "chave_idempotencia": conferencia.context[
                    "chave_idempotencia"
                ],
                "revisao": conferencia.context["revisao"],
            },
        )

        self.assertContains(conferencia, "Total atual: R$ 0,00")
        self.assertRedirects(
            resposta,
            f"/caixa/atendimentos/{self.atendimento.pk}/resumo-final/",
            fetch_redirect_response=False,
        )
        self.atendimento.refresh_from_db()
        self.assertEqual(
            self.atendimento.estado,
            Atendimento.Estado.ENCERRADO,
        )
        self.assertEqual(self.atendimento.fechado_por, self.caixa)
        self.assertIsNotNone(self.atendimento.fechado_em)

        consulta = self.client.get(
            "/caixa/comandas/consultar/",
            {"identificador": "001"},
        )
        self.assertContains(
            consulta,
            "Comanda disponível — nenhum atendimento aberto",
        )

    def test_garcom_nao_acessa_nem_confirma_fechamento(self):
        self.selecionar(self.garcom)
        url = f"/caixa/atendimentos/{self.atendimento.pk}/fechar/"

        conferencia = self.client.get(url)
        confirmacao = self.client.post(
            url,
            {"chave_idempotencia": str(UUID(int=1))},
        )

        self.assertEqual(conferencia.status_code, 403)
        self.assertEqual(confirmacao.status_code, 403)
        self.atendimento.refresh_from_db()
        self.assertEqual(self.atendimento.estado, Atendimento.Estado.ABERTO)

    def test_replay_do_post_reutiliza_fechamento_confirmado(self):
        self.selecionar(self.caixa)
        url = f"/caixa/atendimentos/{self.atendimento.pk}/fechar/"
        conferencia = self.client.get(url)
        dados = {
            "chave_idempotencia": conferencia.context[
                "chave_idempotencia"
            ],
            "revisao": conferencia.context["revisao"],
        }

        primeira = self.client.post(url, dados)
        repetida = self.client.post(url, dados)

        self.assertEqual(primeira.status_code, 302)
        self.assertEqual(repetida.status_code, 302)
        self.assertEqual(primeira.url, repetida.url)
        self.assertEqual(RegistroIdempotencia.objects.count(), 1)

    def test_revisao_antiga_recarrega_resumo_e_exige_nova_confirmacao(self):
        cafe = Produto.objects.create(nome="Café", preco_centavos=600)
        Lancamento.objects.create(
            atendimento=self.atendimento,
            produto=cafe,
            quantidade=1,
            preco_unitario_centavos=600,
            autor=self.garcom,
        )
        self.selecionar(self.caixa)
        url = f"/caixa/atendimentos/{self.atendimento.pk}/fechar/"
        conferencia_antiga = self.client.get(url)
        revisao_antiga = conferencia_antiga.context["revisao"]

        Lancamento.objects.create(
            atendimento=self.atendimento,
            produto=cafe,
            quantidade=2,
            preco_unitario_centavos=600,
            autor=self.garcom,
        )
        conflito = self.client.post(
            url,
            {
                "chave_idempotencia": conferencia_antiga.context[
                    "chave_idempotencia"
                ],
                "revisao": revisao_antiga,
            },
        )

        self.assertEqual(conflito.status_code, 409)
        self.assertContains(
            conflito,
            "O Atendimento mudou desde a conferência.",
            status_code=409,
        )
        self.assertContains(conflito, "Total atual: R$ 18,00", status_code=409)
        self.assertNotEqual(conflito.context["revisao"], revisao_antiga)
        self.assertEqual(RegistroIdempotencia.objects.count(), 0)
        self.atendimento.refresh_from_db()
        self.assertEqual(self.atendimento.estado, Atendimento.Estado.ABERTO)

        confirmacao = self.client.post(
            url,
            {
                "chave_idempotencia": conflito.context[
                    "chave_idempotencia"
                ],
                "revisao": conflito.context["revisao"],
            },
        )

        self.assertEqual(confirmacao.status_code, 302)
        self.atendimento.refresh_from_db()
        self.assertEqual(self.atendimento.estado, Atendimento.Estado.ENCERRADO)
        self.assertEqual(Lancamento.objects.count(), 2)

    def test_cancelamento_entre_conferencia_e_post_invalida_revisao(self):
        cafe = Produto.objects.create(nome="Café", preco_centavos=600)
        lancamento = Lancamento.objects.create(
            atendimento=self.atendimento,
            produto=cafe,
            quantidade=2,
            preco_unitario_centavos=600,
            autor=self.garcom,
        )
        self.selecionar(self.caixa)
        url = f"/caixa/atendimentos/{self.atendimento.pk}/fechar/"
        conferencia = self.client.get(url)

        CancelamentoLancamento.objects.create(
            lancamento=lancamento,
            motivo=CancelamentoLancamento.Motivo.DESISTENCIA,
            descricao="",
            autor=self.garcom,
        )
        conflito = self.client.post(
            url,
            {
                "chave_idempotencia": conferencia.context[
                    "chave_idempotencia"
                ],
                "revisao": conferencia.context["revisao"],
            },
        )

        self.assertEqual(conflito.status_code, 409)
        self.assertContains(conflito, "Total atual: R$ 0,00", status_code=409)
        self.assertContains(conflito, "Lançamentos cancelados", status_code=409)
        self.atendimento.refresh_from_db()
        self.assertEqual(self.atendimento.estado, Atendimento.Estado.ABERTO)


class ResumoFinalAtendimentoInterfaceTests(TestCase):
    def setUp(self):
        self.caixa = UsuarioOperacional.objects.create(
            nome="Caixa 1",
            papel=UsuarioOperacional.Papel.CAIXA,
        )
        self.garcom = UsuarioOperacional.objects.create(
            nome="Garçom 1",
            papel=UsuarioOperacional.Papel.GARCOM,
        )
        self.comanda = ComandaFisica.objects.create(identificador="001")
        self.atendimento = Atendimento.objects.create(comanda=self.comanda)
        self.cafe = Produto.objects.create(nome="Café", preco_centavos=700)
        self.lancamentos = [
            Lancamento.objects.create(
                atendimento=self.atendimento,
                produto=self.cafe,
                quantidade=quantidade,
                preco_unitario_centavos=preco,
                autor=self.garcom,
            )
            for quantidade, preco in ((1, 600), (2, 600), (1, 700))
        ]
        self.abertura = datetime(2026, 1, 2, 15, 4, tzinfo=UTC)
        self.fechamento = datetime(2026, 1, 2, 18, 45, tzinfo=UTC)

    def encerrar_atendimento(self):
        Atendimento.objects.filter(pk=self.atendimento.pk).update(
            aberto_em=self.abertura,
            estado=Atendimento.Estado.ENCERRADO,
            fechado_por=self.caixa,
            fechado_em=self.fechamento,
        )

    def selecionar(self, usuario):
        self.client.post(
            "/usuarios/selecionar/",
            {"usuario_id": usuario.pk},
        )

    def test_mostra_identificacao_horarios_caixa_itens_e_total_final(self):
        self.encerrar_atendimento()
        self.selecionar(self.caixa)

        resposta = self.client.get(
            f"/caixa/atendimentos/{self.atendimento.pk}/resumo-final/"
        )

        self.assertEqual(resposta.status_code, 200)
        self.assertContains(resposta, "Comanda 001")
        self.assertContains(resposta, f"Atendimento {self.atendimento.pk}")
        self.assertContains(resposta, "Aberto em: 02/01/2026 12:04")
        self.assertContains(resposta, "Fechado em: 02/01/2026 15:45")
        self.assertContains(resposta, "Caixa responsável: Caixa 1")
        self.assertContains(
            resposta,
            "Café | qtd 3 | R$ 6,00 | subtotal R$ 18,00",
        )
        self.assertContains(
            resposta,
            "Café | qtd 1 | R$ 7,00 | subtotal R$ 7,00",
        )
        self.assertContains(resposta, "Total final: R$ 25,00")

    def test_mostra_cancelamento_separado_com_rastreabilidade(self):
        autor_cancelamento = UsuarioOperacional.objects.create(
            nome="Garçom 2",
            papel=UsuarioOperacional.Papel.GARCOM,
        )
        lancamento = self.lancamentos[1]
        horario_lancamento = datetime(2026, 1, 2, 16, 10, tzinfo=UTC)
        Lancamento.objects.filter(pk=lancamento.pk).update(
            horario=horario_lancamento
        )
        cancelamento = CancelamentoLancamento.objects.create(
            lancamento=lancamento,
            motivo=CancelamentoLancamento.Motivo.OUTRO,
            descricao="Cliente mudou o pedido",
            autor=autor_cancelamento,
        )
        CancelamentoLancamento.objects.filter(pk=cancelamento.pk).update(
            horario=datetime(2026, 1, 2, 17, 20, tzinfo=UTC)
        )
        self.encerrar_atendimento()
        self.selecionar(self.caixa)

        resposta = self.client.get(
            f"/caixa/atendimentos/{self.atendimento.pk}/resumo-final/"
        )

        self.assertContains(resposta, "Lançamentos cancelados")
        self.assertContains(resposta, "Quantidade: 2")
        self.assertContains(resposta, "Preço unitário original: R$ 6,00")
        self.assertContains(resposta, "Autor do lançamento: Garçom 1")
        self.assertContains(resposta, "Lançado em: 02/01/2026 13:10")
        self.assertContains(resposta, "Motivo: Outro")
        self.assertContains(resposta, "Descrição: Cliente mudou o pedido")
        self.assertContains(resposta, "Autor do cancelamento: Garçom 2")
        self.assertContains(resposta, "Cancelado em: 02/01/2026 14:20")
        self.assertContains(resposta, "Total final: R$ 13,00")

    def test_todos_cancelados_mantem_total_zero_e_tela_somente_leitura(self):
        for lancamento in self.lancamentos:
            CancelamentoLancamento.objects.create(
                lancamento=lancamento,
                motivo=CancelamentoLancamento.Motivo.DESISTENCIA,
                descricao="",
                autor=self.garcom,
            )
        self.encerrar_atendimento()
        self.selecionar(self.caixa)

        resposta = self.client.get(
            f"/caixa/atendimentos/{self.atendimento.pk}/resumo-final/"
        )

        self.assertContains(resposta, "Nenhum consumo válido.")
        self.assertContains(resposta, "Total final: R$ 0,00")
        for acao_ausente in (
            "Pagamento",
            "Forma de pagamento",
            "Imprimir recibo",
            "Emissão fiscal",
            "Reabrir",
            "Cancelar lançamento",
        ):
            with self.subTest(acao=acao_ausente):
                self.assertNotContains(resposta, acao_ausente)

    def test_resumo_permanece_no_atendimento_encerrado_apos_reuso_da_comanda(
        self,
    ):
        self.encerrar_atendimento()
        novo_atendimento = Atendimento.objects.create(comanda=self.comanda)
        self.selecionar(self.caixa)

        resposta = self.client.get(
            f"/caixa/atendimentos/{self.atendimento.pk}/resumo-final/"
        )

        self.assertContains(resposta, f"Atendimento {self.atendimento.pk}")
        self.assertNotContains(resposta, f"Atendimento {novo_atendimento.pk}")
        self.assertEqual(resposta.context["atendimento"].pk, self.atendimento.pk)

    def test_somente_caixa_acessa_resumo_final(self):
        self.encerrar_atendimento()
        self.selecionar(self.garcom)

        resposta = self.client.get(
            f"/caixa/atendimentos/{self.atendimento.pk}/resumo-final/"
        )

        self.assertEqual(resposta.status_code, 403)


class AtualizacaoPeriodicaInterfaceTests(TestCase):
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
        self.produto = Produto.objects.create(
            nome="Café",
            preco_centavos=600,
        )

    def selecionar(self, usuario):
        self.client.post(
            "/usuarios/selecionar/",
            {"usuario_id": usuario.pk},
        )

    def test_consultas_do_garcom_e_caixa_expoem_estado_atualizavel(self):
        self.selecionar(self.garcom)
        garcom_antes = self.client.get(
            "/comandas/consultar/",
            {"identificador": "001"},
        )

        Lancamento.objects.create(
            atendimento=self.atendimento,
            produto=self.produto,
            quantidade=2,
            preco_unitario_centavos=600,
            autor=self.garcom,
        )
        garcom_depois = self.client.get(
            "/comandas/consultar/",
            {"identificador": "001"},
        )
        self.selecionar(self.caixa)
        caixa = self.client.get(
            "/caixa/comandas/consultar/",
            {"identificador": "001"},
        )

        for resposta in (garcom_antes, garcom_depois, caixa):
            self.assertContains(
                resposta,
                "/static/interface_web/js/atualizacao_periodica.mjs",
            )
            self.assertContains(
                resposta,
                "data-atualizacao-periodica",
                html=False,
            )
        self.assertNotEqual(
            garcom_antes.context["revisao_atualizacao"],
            garcom_depois.context["revisao_atualizacao"],
        )
        self.assertContains(garcom_depois, "Total atual: <strong>R$ 12,00")
        self.assertContains(
            caixa,
            "Café | qtd 2 | R$ 6,00 | subtotal R$ 12,00",
        )

    def test_conferencia_atualiza_resumo_revisao_e_reflete_fechamento(self):
        Lancamento.objects.create(
            atendimento=self.atendimento,
            produto=self.produto,
            quantidade=1,
            preco_unitario_centavos=600,
            autor=self.garcom,
        )
        self.selecionar(self.caixa)
        url = f"/caixa/atendimentos/{self.atendimento.pk}/fechar/"
        antes = self.client.get(url)

        Lancamento.objects.create(
            atendimento=self.atendimento,
            produto=self.produto,
            quantidade=2,
            preco_unitario_centavos=600,
            autor=self.garcom,
        )
        depois = self.client.get(url)

        self.assertContains(
            antes,
            "/static/interface_web/js/atualizacao_periodica.mjs",
        )
        self.assertContains(antes, "data-atualizacao-periodica", html=False)
        self.assertNotEqual(
            antes.context["revisao"],
            depois.context["revisao"],
        )
        self.assertContains(depois, "Total atual: R$ 18,00")
        self.assertContains(
            depois,
            f'name="revisao" value="{depois.context["revisao"]}"',
            html=False,
        )

        Atendimento.objects.filter(pk=self.atendimento.pk).update(
            estado=Atendimento.Estado.ENCERRADO,
            fechado_por=self.caixa,
            fechado_em=datetime.now(UTC),
        )
        encerrado = self.client.get(url)

        self.assertRedirects(
            encerrado,
            f"/caixa/atendimentos/{self.atendimento.pk}/resumo-final/",
            fetch_redirect_response=False,
        )

    def test_cancelamento_e_encerramento_externos_aparecem_na_consulta(self):
        lancamento = Lancamento.objects.create(
            atendimento=self.atendimento,
            produto=self.produto,
            quantidade=2,
            preco_unitario_centavos=600,
            autor=self.garcom,
        )
        self.selecionar(self.garcom)
        antes = self.client.get(
            "/comandas/consultar/",
            {"identificador": "001"},
        )

        CancelamentoLancamento.objects.create(
            lancamento=lancamento,
            motivo=CancelamentoLancamento.Motivo.DESISTENCIA,
            descricao="",
            autor=self.garcom,
        )
        cancelado = self.client.get(
            "/comandas/consultar/",
            {"identificador": "001"},
        )

        self.assertNotEqual(
            antes.context["revisao_atualizacao"],
            cancelado.context["revisao_atualizacao"],
        )
        self.assertContains(cancelado, "Lançamentos cancelados")
        self.assertContains(cancelado, "Total atual: <strong>R$ 0,00")

        Atendimento.objects.filter(pk=self.atendimento.pk).update(
            estado=Atendimento.Estado.ENCERRADO,
            fechado_por=self.caixa,
            fechado_em=datetime.now(UTC),
        )
        encerrado_garcom = self.client.get(
            "/comandas/consultar/",
            {"identificador": "001"},
        )
        self.selecionar(self.caixa)
        encerrado_caixa = self.client.get(
            "/caixa/comandas/consultar/",
            {"identificador": "001"},
        )

        for resposta in (encerrado_garcom, encerrado_caixa):
            self.assertContains(
                resposta,
                "Comanda disponível — nenhum atendimento aberto",
            )
            self.assertNotContains(resposta, "Cancelar lançamento")
            self.assertNotContains(resposta, "Fechar atendimento")

    def test_consultas_periodicas_nao_criam_nem_repetem_operacoes(self):
        Lancamento.objects.create(
            atendimento=self.atendimento,
            produto=self.produto,
            quantidade=1,
            preco_unitario_centavos=600,
            autor=self.garcom,
        )
        self.selecionar(self.garcom)
        quantidades_antes = (
            Atendimento.objects.count(),
            Lancamento.objects.count(),
            CancelamentoLancamento.objects.count(),
            RegistroIdempotencia.objects.count(),
        )

        for _ in range(3):
            resposta = self.client.get(
                "/comandas/consultar/",
                {"identificador": "001"},
            )
            self.assertEqual(resposta.status_code, 200)

        self.assertEqual(
            (
                Atendimento.objects.count(),
                Lancamento.objects.count(),
                CancelamentoLancamento.objects.count(),
                RegistroIdempotencia.objects.count(),
            ),
            quantidades_antes,
        )

    def test_telas_atualizaveis_expoem_contrato_visual_de_comunicacao(self):
        self.selecionar(self.garcom)
        consulta = self.client.get(
            "/comandas/consultar/",
            {"identificador": "001"},
        )
        self.selecionar(self.caixa)
        fechamento = self.client.get(
            f"/caixa/atendimentos/{self.atendimento.pk}/fechar/"
        )

        for resposta in (consulta, fechamento):
            with self.subTest(url=resposta.request["PATH_INFO"]):
                self.assertContains(
                    resposta,
                    "Sem comunicação com o servidor",
                )
                self.assertContains(
                    resposta,
                    "Dados exibidos podem estar desatualizados",
                )
                self.assertContains(
                    resposta,
                    "data-aviso-comunicacao",
                    html=False,
                )
                self.assertContains(
                    resposta,
                    "data-aviso-resultado-incerto",
                    html=False,
                )
                self.assertContains(
                    resposta,
                    "data-acao-mutavel",
                    html=False,
                )

    def test_primeiro_lancamento_usa_saude_e_consulta_comanda_na_recuperacao(self):
        self.selecionar(self.garcom)

        resposta = self.client.get("/garcom/")

        self.assertContains(
            resposta,
            "/static/interface_web/js/atualizacao_periodica.mjs",
        )
        self.assertContains(resposta, 'data-url-saude="/saude/"', html=False)
        self.assertContains(
            resposta,
            'data-url-verificacao="/comandas/consultar/"',
            html=False,
        )
        self.assertContains(resposta, "data-acao-mutavel", html=False)
