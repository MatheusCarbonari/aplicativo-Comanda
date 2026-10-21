import logging
import os
import shutil
import sqlite3
import subprocess
from contextlib import closing
from io import StringIO
from pathlib import Path
from threading import Event, Thread
from unittest.mock import patch
from uuid import uuid4

from django.conf import settings
from django.core.management import call_command, CommandError
from django.db import connections
from django.test import TransactionTestCase, override_settings

from restaurante.persistencia.models import ComandaFisica


class ColetorDeLogs(logging.Handler):
    def __init__(self):
        super().__init__()
        self.registros = []

    def emit(self, record):
        self.registros.append(record)


class ExecutarBackupDiarioTests(TransactionTestCase):
    def setUp(self):
        self.diretorio_backup = (
            settings.DIRETORIO_TESTES / f"backup-diario-{uuid4().hex}"
        )
        self.diretorio_backup.mkdir()
        self.addCleanup(shutil.rmtree, self.diretorio_backup)

    def coletar_logs(self):
        coletor = ColetorDeLogs()
        logger = logging.getLogger("restaurante")
        logger.addHandler(coletor)
        self.addCleanup(logger.removeHandler, coletor)
        return coletor

    def test_execucao_diaria_cria_backup_seguro_com_dados_persistidos(self):
        ComandaFisica.objects.create(identificador="BACKUP-DIARIO")
        saida = StringIO()

        with override_settings(DIRETORIO_BACKUPS=self.diretorio_backup):
            call_command("executar_backup_diario", stdout=saida)

        backups = list(self.diretorio_backup.glob("restaurante-*.sqlite3"))
        self.assertEqual(len(backups), 1)
        with closing(sqlite3.connect(backups[0])) as copia:
            self.assertEqual(
                copia.execute("PRAGMA integrity_check").fetchone(),
                ("ok",),
            )
            self.assertEqual(
                copia.execute(
                    'SELECT identificador FROM "persistencia_comandafisica" '
                    "WHERE identificador = ?",
                    ("BACKUP-DIARIO",),
                ).fetchone(),
                ("BACKUP-DIARIO",),
            )
        self.assertIn("Backup criado com sucesso", saida.getvalue())

    def test_retencao_mantem_sete_mais_recentes_e_ignora_incompleto(self):
        nomes_antigos = [
            f"restaurante-202601{dia:02d}T030000000000Z.sqlite3"
            for dia in range(1, 9)
        ]
        for nome in nomes_antigos:
            (self.diretorio_backup / nome).write_bytes(nome.encode("ascii"))
        incompleto = (
            self.diretorio_backup
            / ".restaurante-20261231T030000000000Z-teste.incompleto"
        )
        incompleto.write_text("não é backup válido", encoding="utf-8")

        with override_settings(DIRETORIO_BACKUPS=self.diretorio_backup):
            call_command("executar_backup_diario", stdout=StringIO())

        backups = sorted(
            caminho.name
            for caminho in self.diretorio_backup.glob("restaurante-*.sqlite3")
        )
        self.assertEqual(len(backups), 7)
        self.assertNotIn(nomes_antigos[0], backups)
        self.assertNotIn(nomes_antigos[1], backups)
        self.assertTrue(set(nomes_antigos[2:]).issubset(backups))
        self.assertTrue(incompleto.exists())

    def test_retencao_ignora_timestamps_impossiveis_e_nomes_invalidos(self):
        backups_validos = []
        for dia in range(1, 8):
            caminho = self.diretorio_backup / (
                f"restaurante-202601{dia:02d}T030000000000Z.sqlite3"
            )
            caminho.write_bytes(f"backup-valido-{dia}".encode("ascii"))
            backups_validos.append(caminho)
        arquivos_ignorados = [
            self.diretorio_backup
            / "restaurante-99999999T999999999999Z.sqlite3",
            self.diretorio_backup
            / "restaurante-20261340T250000000000Z.sqlite3",
            self.diretorio_backup
            / "restaurante-20260101T030000.sqlite3",
            self.diretorio_backup / "arquivo-estranho.sqlite3",
            self.diretorio_backup
            / ".restaurante-20261231T030000000000Z-teste.incompleto",
        ]
        for caminho in arquivos_ignorados:
            caminho.write_text("deve ser ignorado", encoding="utf-8")

        with override_settings(DIRETORIO_BACKUPS=self.diretorio_backup):
            call_command("executar_backup_diario", stdout=StringIO())

        publicados = {
            caminho
            for caminho in self.diretorio_backup.glob("restaurante-*.sqlite3")
            if caminho not in arquivos_ignorados
        }
        self.assertFalse(backups_validos[0].exists())
        self.assertTrue(all(caminho.exists() for caminho in backups_validos[1:]))
        self.assertEqual(len(publicados), 7)
        self.assertTrue(all(caminho.exists() for caminho in arquivos_ignorados))

    def test_de_dois_a_sete_backups_validos_nao_remove_nenhum(self):
        for quantidade_final in range(2, 8):
            with self.subTest(quantidade=quantidade_final):
                diretorio = self.diretorio_backup / str(quantidade_final)
                diretorio.mkdir()
                anteriores = []
                for dia in range(1, quantidade_final):
                    caminho = diretorio / (
                        f"restaurante-202601{dia:02d}T030000000000Z.sqlite3"
                    )
                    caminho.write_bytes(f"anterior-{dia}".encode("ascii"))
                    anteriores.append(caminho)

                with override_settings(DIRETORIO_BACKUPS=diretorio):
                    call_command("executar_backup_diario", stdout=StringIO())

                self.assertTrue(all(caminho.exists() for caminho in anteriores))
                self.assertEqual(
                    len(list(diretorio.glob("restaurante-*.sqlite3"))),
                    quantidade_final,
                )

    def test_retencao_ordena_sufixos_numericamente(self):
        timestamp = "20260101T030000000000Z"
        nomes = [
            f"restaurante-{timestamp}-10.sqlite3",
            f"restaurante-{timestamp}-3.sqlite3",
            f"restaurante-{timestamp}.sqlite3",
            f"restaurante-{timestamp}-9.sqlite3",
            f"restaurante-{timestamp}-1.sqlite3",
            f"restaurante-{timestamp}-5.sqlite3",
            f"restaurante-{timestamp}-2.sqlite3",
            f"restaurante-{timestamp}-4.sqlite3",
        ]
        for nome in nomes:
            (self.diretorio_backup / nome).write_bytes(nome.encode("ascii"))

        with override_settings(DIRETORIO_BACKUPS=self.diretorio_backup):
            call_command("executar_backup_diario", stdout=StringIO())

        restantes = {
            caminho.name
            for caminho in self.diretorio_backup.glob("restaurante-*.sqlite3")
        }
        self.assertNotIn(f"restaurante-{timestamp}.sqlite3", restantes)
        self.assertNotIn(f"restaurante-{timestamp}-1.sqlite3", restantes)
        self.assertIn(f"restaurante-{timestamp}-10.sqlite3", restantes)
        self.assertEqual(len(restantes), 7)

    def test_falha_do_backup_preserva_todas_as_copias_anteriores(self):
        backups_anteriores = {}
        for dia in range(1, 9):
            caminho = self.diretorio_backup / (
                f"restaurante-202601{dia:02d}T030000000000Z.sqlite3"
            )
            conteudo = f"backup-anterior-{dia}".encode("ascii")
            caminho.write_bytes(conteudo)
            backups_anteriores[caminho] = conteudo
        destino_fechado = sqlite3.connect(":memory:")
        destino_fechado.close()
        coletor = self.coletar_logs()
        conectar_real = sqlite3.connect

        def falhar_apenas_no_destino(caminho, *args, **kwargs):
            if str(caminho).endswith(".incompleto"):
                return destino_fechado
            return conectar_real(caminho, *args, **kwargs)

        with (
            override_settings(DIRETORIO_BACKUPS=self.diretorio_backup),
            patch(
                "restaurante.ferramentas_administrativas.management.commands."
                "criar_backup.sqlite3.connect",
                side_effect=falhar_apenas_no_destino,
            ),
            self.assertRaises(CommandError),
        ):
            call_command("executar_backup_diario", stdout=StringIO())

        self.assertEqual(
            {caminho: caminho.read_bytes() for caminho in backups_anteriores},
            backups_anteriores,
        )
        self.assertEqual(
            set(self.diretorio_backup.glob("restaurante-*.sqlite3")),
            set(backups_anteriores),
        )
        eventos = [registro.evento for registro in coletor.registros]
        self.assertIn("backup_diario_iniciado", eventos)
        self.assertIn("backup_sqlite_falhou", eventos)
        self.assertIn("backup_diario_falhou", eventos)
        self.assertNotIn("backup_diario_retencao_aplicada", eventos)
        self.assertNotIn("backup_diario_concluido", eventos)

    def test_falha_apos_remocao_parcial_para_e_preserva_backup_novo(self):
        backups_anteriores = set()
        for dia in range(1, 10):
            caminho = self.diretorio_backup / (
                f"restaurante-202601{dia:02d}T030000000000Z.sqlite3"
            )
            caminho.write_bytes(f"anterior-{dia}".encode("ascii"))
            backups_anteriores.add(caminho)
        primeiro, segundo, terceiro = sorted(backups_anteriores)[:3]
        tentativas_de_remocao = []
        unlink_real = Path.unlink
        coletor = self.coletar_logs()

        def falhar_na_segunda_remocao(caminho, *args, **kwargs):
            if caminho in {primeiro, segundo, terceiro}:
                tentativas_de_remocao.append(caminho)
            if caminho == segundo:
                raise PermissionError("falha sentinela de retenção")
            return unlink_real(caminho, *args, **kwargs)

        with (
            override_settings(DIRETORIO_BACKUPS=self.diretorio_backup),
            patch(
                "restaurante.ferramentas_administrativas.management.commands."
                "executar_backup_diario.Path.unlink",
                new=falhar_na_segunda_remocao,
            ),
            self.assertRaisesMessage(
                CommandError,
                "O backup foi criado, mas a retenção diária falhou.",
            ) as erro_capturado,
        ):
            call_command("executar_backup_diario", stdout=StringIO())

        self.assertEqual(tentativas_de_remocao, [primeiro, segundo])
        self.assertFalse(primeiro.exists())
        self.assertTrue(segundo.exists())
        self.assertTrue(terceiro.exists())
        self.assertIsInstance(erro_capturado.exception.__cause__, PermissionError)
        self.assertIn(
            "falha sentinela de retenção",
            str(erro_capturado.exception.__cause__),
        )
        backups_atuais = set(
            self.diretorio_backup.glob("restaurante-*.sqlite3")
        )
        backups_novos = backups_atuais - backups_anteriores
        self.assertEqual(len(backups_novos), 1)
        with closing(sqlite3.connect(backups_novos.pop())) as copia:
            self.assertEqual(
                copia.execute("PRAGMA integrity_check").fetchone(),
                ("ok",),
            )
        self.assertEqual(
            list(self.diretorio_backup.glob("*.incompleto")),
            [],
        )
        falha = next(
            registro
            for registro in coletor.registros
            if registro.evento == "backup_diario_falhou"
        )
        self.assertEqual(falha.contexto_tecnico["etapa"], "retencao")
        removidos = [
            registro.contexto_tecnico["arquivo_backup"]
            for registro in coletor.registros
            if registro.evento == "backup_diario_excedente_removido"
        ]
        self.assertEqual(removidos, [primeiro.name])

    def test_execucao_sobreposta_sai_sem_criar_backup(self):
        caminho_bloqueio = (
            self.diretorio_backup / ".backup-diario.lock.sqlite3"
        )
        coletor = self.coletar_logs()
        with closing(
            sqlite3.connect(caminho_bloqueio, timeout=0)
        ) as conexao_bloqueio:
            conexao_bloqueio.execute("BEGIN IMMEDIATE")

            with (
                override_settings(DIRETORIO_BACKUPS=self.diretorio_backup),
                self.assertRaisesMessage(
                    CommandError,
                    "Uma execução do backup diário já está em andamento.",
                ),
            ):
                call_command("executar_backup_diario", stdout=StringIO())

        self.assertEqual(
            list(self.diretorio_backup.glob("restaurante-*.sqlite3")),
            [],
        )
        self.assertEqual(
            [registro.evento for registro in coletor.registros],
            ["backup_diario_ignorado_concorrencia"],
        )

    def test_duas_execucoes_concorrentes_so_deixam_uma_prosseguir(self):
        bloqueio_adquirido = Event()
        liberar_primeira_execucao = Event()
        erros_da_primeira_execucao = []
        coletor = self.coletar_logs()

        class PausarDepoisDoBloqueio(logging.Filter):
            def filter(self, record):
                if (
                    record.evento == "backup_diario_iniciado"
                    and not bloqueio_adquirido.is_set()
                ):
                    bloqueio_adquirido.set()
                    liberar_primeira_execucao.wait(timeout=5)
                return True

        coletor.addFilter(PausarDepoisDoBloqueio())

        def executar_primeiro_backup():
            try:
                with override_settings(
                    DIRETORIO_BACKUPS=self.diretorio_backup
                ):
                    call_command("executar_backup_diario", stdout=StringIO())
            except Exception as erro:
                erros_da_primeira_execucao.append(erro)
            finally:
                connections.close_all()

        primeira_execucao = Thread(target=executar_primeiro_backup)
        primeira_execucao.start()
        self.assertTrue(bloqueio_adquirido.wait(timeout=5))
        try:
            with (
                override_settings(DIRETORIO_BACKUPS=self.diretorio_backup),
                self.assertRaisesMessage(
                    CommandError,
                    "Uma execução do backup diário já está em andamento.",
                ),
            ):
                call_command("executar_backup_diario", stdout=StringIO())
        finally:
            liberar_primeira_execucao.set()
            primeira_execucao.join(timeout=5)

        self.assertFalse(primeira_execucao.is_alive())
        self.assertEqual(erros_da_primeira_execucao, [])
        self.assertEqual(
            len(list(self.diretorio_backup.glob("restaurante-*.sqlite3"))),
            1,
        )
        eventos = [registro.evento for registro in coletor.registros]
        self.assertEqual(eventos.count("backup_diario_iniciado"), 1)
        self.assertEqual(
            eventos.count("backup_diario_ignorado_concorrencia"),
            1,
        )
        self.assertEqual(eventos.count("backup_diario_retencao_aplicada"), 1)
        self.assertEqual(eventos.count("backup_diario_concluido"), 1)

    def test_execucoes_repetidas_liberam_lock_e_criam_backups_distintos(self):
        with override_settings(DIRETORIO_BACKUPS=self.diretorio_backup):
            call_command("executar_backup_diario", stdout=StringIO())
            call_command("executar_backup_diario", stdout=StringIO())

        backups = list(
            self.diretorio_backup.glob("restaurante-*.sqlite3")
        )
        self.assertEqual(len(backups), 2)
        for backup in backups:
            with closing(sqlite3.connect(backup)) as copia:
                self.assertEqual(
                    copia.execute("PRAGMA integrity_check").fetchone(),
                    ("ok",),
                )

    def test_falha_libera_lock_para_execucao_seguinte(self):
        destino_fechado = sqlite3.connect(":memory:")
        destino_fechado.close()
        conectar_real = sqlite3.connect

        def falhar_apenas_no_destino(caminho, *args, **kwargs):
            if str(caminho).endswith(".incompleto"):
                return destino_fechado
            return conectar_real(caminho, *args, **kwargs)

        with override_settings(DIRETORIO_BACKUPS=self.diretorio_backup):
            with (
                patch(
                    "restaurante.ferramentas_administrativas.management.commands."
                    "criar_backup.sqlite3.connect",
                    side_effect=falhar_apenas_no_destino,
                ),
                self.assertRaises(CommandError),
            ):
                call_command("executar_backup_diario", stdout=StringIO())

            call_command("executar_backup_diario", stdout=StringIO())

        backups = list(
            self.diretorio_backup.glob("restaurante-*.sqlite3")
        )
        self.assertEqual(len(backups), 1)
        with closing(sqlite3.connect(backups[0])) as copia:
            self.assertEqual(
                copia.execute("PRAGMA integrity_check").fetchone(),
                ("ok",),
            )

    def test_logs_registram_sucesso_retencao_e_excedentes_removidos(self):
        for dia in range(1, 9):
            caminho = self.diretorio_backup / (
                f"restaurante-202601{dia:02d}T030000000000Z.sqlite3"
            )
            caminho.write_bytes(f"anterior-{dia}".encode("ascii"))
        coletor = self.coletar_logs()

        with override_settings(DIRETORIO_BACKUPS=self.diretorio_backup):
            call_command("executar_backup_diario", stdout=StringIO())

        eventos = [registro.evento for registro in coletor.registros]
        self.assertEqual(eventos[0], "backup_diario_iniciado")
        self.assertIn("backup_sqlite_concluido", eventos)
        self.assertEqual(
            eventos.count("backup_diario_excedente_removido"),
            2,
        )
        self.assertLess(
            eventos.index("backup_sqlite_concluido"),
            eventos.index("backup_diario_retencao_aplicada"),
        )
        self.assertEqual(eventos[-1], "backup_diario_concluido")
        retencao = next(
            registro
            for registro in coletor.registros
            if registro.evento == "backup_diario_retencao_aplicada"
        )
        self.assertEqual(
            retencao.contexto_tecnico["backups_mantidos"],
            7,
        )
        self.assertEqual(
            retencao.contexto_tecnico["arquivos_removidos"],
            2,
        )

    def test_wrapper_powershell_executa_fluxo_a_partir_de_outro_diretorio(self):
        powershell = shutil.which("powershell.exe")
        if powershell is None:
            self.skipTest("PowerShell do Windows não disponível")

        nome_configuracao = f"configuracao_wrapper_{uuid4().hex}"
        caminho_configuracao = (
            self.diretorio_backup / f"{nome_configuracao}.py"
        )
        caminho_banco = self.diretorio_backup / "origem-wrapper.sqlite3"
        caminho_configuracao.write_text(
            "\n".join(
                [
                    "from restaurante.infraestrutura.configuracao import *",
                    f"DIRETORIO_BACKUPS = Path({str(self.diretorio_backup)!r})",
                    "DATABASES = {",
                    '    "default": {',
                    '        "ENGINE": "django.db.backends.sqlite3",',
                    f'        "NAME": Path({str(caminho_banco)!r}),',
                    '        "OPTIONS": {',
                    '            "init_command": "PRAGMA journal_mode=WAL; '
                    'PRAGMA synchronous=FULL",',
                    "        },",
                    "    },",
                    "}",
                    "LOGGING = {",
                    '    "version": 1,',
                    '    "disable_existing_loggers": False,',
                    '    "handlers": {"nulo": {"class": "logging.NullHandler"}},',
                    '    "loggers": {',
                    '        "restaurante": {',
                    '            "handlers": ["nulo"],',
                    '            "level": "INFO",',
                    '            "propagate": False,',
                    "        },",
                    "    },",
                    "}",
                ]
            ),
            encoding="utf-8",
        )
        ambiente = os.environ.copy()
        ambiente["DJANGO_SETTINGS_MODULE"] = nome_configuracao
        ambiente["PYTHONPATH"] = os.pathsep.join(
            filter(
                None,
                [
                    str(self.diretorio_backup),
                    ambiente.get("PYTHONPATH"),
                ],
            )
        )
        raiz_projeto = Path(settings.BASE_DIR)
        resultado = subprocess.run(
            [
                powershell,
                "-NoProfile",
                "-ExecutionPolicy",
                "Bypass",
                "-File",
                str(raiz_projeto / "scripts" / "executar_backup_diario.ps1"),
            ],
            cwd=self.diretorio_backup,
            env=ambiente,
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )

        self.assertEqual(
            resultado.returncode,
            0,
            resultado.stdout + resultado.stderr,
        )
        backups = list(
            self.diretorio_backup.glob("restaurante-*.sqlite3")
        )
        self.assertEqual(len(backups), 1)
        with closing(sqlite3.connect(backups[0])) as copia:
            self.assertEqual(
                copia.execute("PRAGMA integrity_check").fetchone(),
                ("ok",),
            )
