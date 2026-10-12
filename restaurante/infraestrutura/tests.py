from unittest.mock import patch

from django.conf import settings
from django.db import DatabaseError
from django.test import TestCase

from restaurante.persistencia.models import (
    ComandaFisica,
    Produto,
    UsuarioOperacional,
)


class SaudeBackendTests(TestCase):
    def test_endpoint_saudavel_tem_contrato_publico_minimo_sem_sessao(self):
        resposta = self.client.get("/saude/")

        self.assertEqual(resposta.status_code, 200)
        self.assertEqual(resposta.headers["Content-Type"], "application/json")
        self.assertEqual(resposta.json(), {"status": "ok"})
        self.assertNotIn(settings.SESSION_COOKIE_NAME, self.client.cookies)

    @patch(
        "restaurante.infraestrutura.saude.connection.cursor",
        side_effect=DatabaseError("detalhe interno que não pode ser exposto"),
    )
    def test_falha_na_persistencia_retorna_indisponibilidade_sem_detalhes(
        self,
        cursor_indisponivel,
    ):
        resposta = self.client.get("/saude/")

        self.assertEqual(resposta.status_code, 503)
        self.assertEqual(resposta.headers["Content-Type"], "application/json")
        self.assertEqual(resposta.json(), {"status": "indisponivel"})
        self.assertNotContains(
            resposta,
            "detalhe interno",
            status_code=503,
        )
        cursor_indisponivel.assert_called_once_with()

    def test_endpoint_aceita_somente_get(self):
        resposta = self.client.post("/saude/")

        self.assertEqual(resposta.status_code, 405)

    def test_consulta_de_saude_nao_altera_dados_de_dominio(self):
        ComandaFisica.objects.create(identificador="001")
        Produto.objects.create(nome="Café", preco_centavos=600)
        UsuarioOperacional.objects.create(
            nome="Garçom 1",
            papel=UsuarioOperacional.Papel.GARCOM,
        )
        estado_antes = {
            "comandas": list(ComandaFisica.objects.values()),
            "produtos": list(Produto.objects.values()),
            "usuarios": list(UsuarioOperacional.objects.values()),
        }

        resposta = self.client.get("/saude/")

        estado_depois = {
            "comandas": list(ComandaFisica.objects.values()),
            "produtos": list(Produto.objects.values()),
            "usuarios": list(UsuarioOperacional.objects.values()),
        }
        self.assertEqual(resposta.status_code, 200)
        self.assertEqual(estado_depois, estado_antes)
