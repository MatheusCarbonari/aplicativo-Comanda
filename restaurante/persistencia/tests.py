from pathlib import Path

from django.core.exceptions import ImproperlyConfigured
from django.db import connection, connections, transaction
from django.test import SimpleTestCase, TransactionTestCase

from restaurante.infraestrutura.configuracao import BASE_DIR, CAMINHO_BANCO
from restaurante.persistencia.sqlite_duravel import (
    observar_pragmas,
    validar_pragmas,
)


class ConfiguracaoSQLiteTests(SimpleTestCase):
    def test_banco_operacional_tem_caminho_persistente_conhecido(self):
        caminho_esperado = BASE_DIR / ".local" / "dados" / "restaurante.sqlite3"

        self.assertEqual(CAMINHO_BANCO.resolve(), caminho_esperado)
        self.assertTrue(CAMINHO_BANCO.parent.is_dir())

    def test_configuracao_invalida_produz_erro_compreensivel(self):
        with self.assertRaisesMessage(
            ImproperlyConfigured,
            "journal_mode=delete, synchronous=0",
        ):
            validar_pragmas(
                journal_mode="delete",
                synchronous=0,
                caminho_banco=CAMINHO_BANCO,
            )

    def test_nova_conexao_incompativel_falha_com_mensagem_clara(self):
        configuracao = connection.settings_dict.copy()
        configuracao["NAME"] = ":memory:"
        configuracao["TEST"] = {"NAME": ":memory:"}
        conexao_incompativel = connections["default"].__class__(
            configuracao,
            alias="sqlite_incompativel",
        )

        with self.assertRaisesMessage(
            ImproperlyConfigured,
            "journal_mode=memory, synchronous=2",
        ):
            conexao_incompativel.ensure_connection()


class PersistenciaSQLiteTests(TransactionTestCase):
    def test_conexao_real_usa_wal_e_synchronous_full(self):
        caminho_teste = Path(connection.settings_dict["NAME"])

        self.assertNotEqual(str(caminho_teste), ":memory:")
        self.assertTrue(caminho_teste.is_file())
        self.assertEqual(
            observar_pragmas(connection),
            {"journal_mode": "wal", "synchronous": 2},
        )

    def test_registro_confirmado_permanece_apos_reabrir_conexao(self):
        nome_tabela = "teste_persistencia_confirmada"

        with connection.cursor() as cursor:
            cursor.execute(
                f"CREATE TABLE {nome_tabela} "
                "(id INTEGER PRIMARY KEY, valor TEXT NOT NULL)"
            )

        try:
            with transaction.atomic():
                with connection.cursor() as cursor:
                    cursor.execute(
                        f"INSERT INTO {nome_tabela} (valor) VALUES (%s)",
                        ["confirmado"],
                    )

            connection.close()
            connection.connect()

            with connection.cursor() as cursor:
                cursor.execute(f"SELECT valor FROM {nome_tabela}")
                registro = cursor.fetchone()

            self.assertEqual(registro, ("confirmado",))
            self.assertEqual(
                observar_pragmas(connection),
                {"journal_mode": "wal", "synchronous": 2},
            )
        finally:
            with connection.cursor() as cursor:
                cursor.execute(f"DROP TABLE IF EXISTS {nome_tabela}")
