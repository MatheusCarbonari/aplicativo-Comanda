from django.test import SimpleTestCase


class PaginaInicialTests(SimpleTestCase):
    def test_aplicacao_inicia_e_exibe_pagina_base_em_portugues(self):
        resposta = self.client.get("/")

        self.assertEqual(resposta.status_code, 200)
        self.assertContains(resposta, '<html lang="pt-BR">', html=False)
        self.assertContains(resposta, "Comandas do restaurante")
        self.assertContains(resposta, "/static/interface_web/css/base.css")
