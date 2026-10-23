import ctypes
import os
import re
import shutil
import signal
import socket
import subprocess
import sys
import time
from pathlib import Path
from urllib.error import URLError
from urllib.request import Request, urlopen
from uuid import uuid4
from ctypes import wintypes

from django.conf import settings
from django.test import SimpleTestCase, TestCase

from restaurante.persistencia.models import Produto, UsuarioOperacional


RAIZ_PROJETO = Path(__file__).resolve().parents[2]
SCRIPT_INICIALIZACAO = RAIZ_PROJETO / "scripts" / "iniciar_servidor.ps1"

LIMITE_ENCERRAR_AO_FECHAR_JOB = 0x00002000
INFORMACAO_ESTENDIDA_LIMITE_JOB = 9
PROCESS_SET_QUOTA = 0x0100
PROCESS_TERMINATE = 0x0001


class _InformacaoBasicaLimiteJob(ctypes.Structure):
    _fields_ = [
        ("PerProcessUserTimeLimit", ctypes.c_longlong),
        ("PerJobUserTimeLimit", ctypes.c_longlong),
        ("LimitFlags", wintypes.DWORD),
        ("MinimumWorkingSetSize", ctypes.c_size_t),
        ("MaximumWorkingSetSize", ctypes.c_size_t),
        ("ActiveProcessLimit", wintypes.DWORD),
        ("Affinity", ctypes.c_size_t),
        ("PriorityClass", wintypes.DWORD),
        ("SchedulingClass", wintypes.DWORD),
    ]


class _ContadoresEntradaSaida(ctypes.Structure):
    _fields_ = [
        ("ReadOperationCount", ctypes.c_ulonglong),
        ("WriteOperationCount", ctypes.c_ulonglong),
        ("OtherOperationCount", ctypes.c_ulonglong),
        ("ReadTransferCount", ctypes.c_ulonglong),
        ("WriteTransferCount", ctypes.c_ulonglong),
        ("OtherTransferCount", ctypes.c_ulonglong),
    ]


class _InformacaoEstendidaLimiteJob(ctypes.Structure):
    _fields_ = [
        ("BasicLimitInformation", _InformacaoBasicaLimiteJob),
        ("IoInfo", _ContadoresEntradaSaida),
        ("ProcessMemoryLimit", ctypes.c_size_t),
        ("JobMemoryLimit", ctypes.c_size_t),
        ("PeakProcessMemoryUsed", ctypes.c_size_t),
        ("PeakJobMemoryUsed", ctypes.c_size_t),
    ]


class WrapperInicializacaoTests(SimpleTestCase):
    def test_existe_comando_operacional_unico_em_powershell(self):
        self.assertTrue(
            SCRIPT_INICIALIZACAO.is_file(),
            "scripts/iniciar_servidor.ps1 deve ser a entrada operacional única",
        )

    def test_informa_urls_e_propaga_falha_do_django(self):
        ambiente = os.environ.copy()
        ambiente["DJANGO_SETTINGS_MODULE"] = "configuracao.inexistente"

        resultado = subprocess.run(
            [
                "powershell.exe",
                "-NoProfile",
                "-ExecutionPolicy",
                "Bypass",
                "-File",
                str(SCRIPT_INICIALIZACAO),
                "-Porta",
                str(ServidorRedeLocalTests._porta_disponivel()),
            ],
            cwd=settings.DIRETORIO_TESTES,
            env=ambiente,
            capture_output=True,
            timeout=15,
        )
        saida = resultado.stdout.decode("utf-8")

        self.assertNotEqual(resultado.returncode, 0)
        self.assertIn("Servidor local: http://127.0.0.1:", saida)
        self.assertIn("Rede local: http://", saida)
        self.assertIn("Verificação de saúde: http://127.0.0.1:", saida)
        self.assertNotIn("Ã", saida)

    def test_contrato_usa_venv_raiz_bind_e_nao_executa_administracao(self):
        script = SCRIPT_INICIALIZACAO.read_text(encoding="utf-8")

        self.assertIn('"0.0.0.0"', script)
        self.assertIn("[int]$Porta = 8000", script)
        self.assertIn('".venv\\Scripts\\python.exe"', script)
        self.assertIn("Push-Location -LiteralPath $raizProjeto", script)
        self.assertIn('manage.py runserver "${Endereco}:$Porta" --noreload', script)
        self.assertIn("exit $LASTEXITCODE", script)
        self.assertNotIn("migrate", script)
        self.assertNotIn("reinicializar_dados", script)


class ServidorRedeLocalTests(SimpleTestCase):
    TEMPO_LIMITE_INICIALIZACAO = 15

    def test_wrapper_inicia_django_real_e_serve_saude_pagina_e_css_local(self):
        diretorio = settings.DIRETORIO_TESTES / f"rede-local-{uuid4().hex}"
        diretorio.mkdir()
        self.addCleanup(shutil.rmtree, diretorio)
        try:
            ambiente = os.environ.copy()
            ambiente.update(
                {
                    "DJANGO_SETTINGS_MODULE": (
                        "restaurante.testes_suporte.configuracao_servidor"
                    ),
                    "RESTAURANTE_TESTE_BANCO": str(
                        diretorio / "restaurante.sqlite3"
                    ),
                    "RESTAURANTE_TESTE_LOG": str(diretorio / "servidor.jsonl"),
                }
            )
            subprocess.run(
                [sys.executable, "manage.py", "migrate", "--noinput"],
                cwd=RAIZ_PROJETO,
                env=ambiente,
                check=True,
                capture_output=True,
                text=True,
                timeout=30,
            )
            porta = self._porta_disponivel()
            saida = diretorio / "stdout.log"
            erros = diretorio / "stderr.log"
            with (
                saida.open("w", encoding="utf-8") as arquivo_saida,
                erros.open("w", encoding="utf-8") as arquivo_erros,
            ):
                processo = self._iniciar_arvore(
                    [
                        "powershell.exe",
                        "-NoProfile",
                        "-ExecutionPolicy",
                        "Bypass",
                        "-File",
                        str(SCRIPT_INICIALIZACAO),
                        "-Porta",
                        str(porta),
                    ],
                    cwd=diretorio,
                    env=ambiente,
                    stdout=arquivo_saida,
                    stderr=arquivo_erros,
                    creationflags=subprocess.CREATE_NEW_PROCESS_GROUP,
                )
            base = f"http://127.0.0.1:{porta}"
            saude = self._aguardar_http(processo, f"{base}/saude/", saida, erros)
            self.assertEqual(saude, b'{"status": "ok"}')

            pagina = self._obter(f"{base}/").decode("utf-8")
            self.assertIn('/static/interface_web/css/base.css', pagina)
            css = self._obter(f"{base}/static/interface_web/css/base.css")
            self.assertIn(b"body", css)
            javascript = self._obter(
                f"{base}/static/interface_web/js/atualizacao_periodica.mjs"
            )
            self.assertIn(b"fetch", javascript)
            for recurso in (css, javascript):
                self.assertNotIn(b"https://", recurso)
                self.assertNotIn(b"http://", recurso)
                self.assertNotIn(b"//cdn", recurso)

            ipv4_lan = self._ipv4_lan()
            requisicao_lan = Request(
                f"{base}/saude/",
                headers={"Host": f"{ipv4_lan}:{porta}"},
            )
            with urlopen(requisicao_lan, timeout=2) as resposta_lan:
                self.assertEqual(resposta_lan.status, 200)
        finally:
            if "processo" in locals():
                self._encerrar_arvore(processo)

    def test_fallback_de_cleanup_encerra_wrapper_e_django(self):
        diretorio = settings.DIRETORIO_TESTES / f"rede-local-{uuid4().hex}"
        diretorio.mkdir()
        self.addCleanup(shutil.rmtree, diretorio)
        ambiente = os.environ.copy()
        ambiente.update(
            {
                "DJANGO_SETTINGS_MODULE": (
                    "restaurante.testes_suporte.configuracao_servidor"
                ),
                "RESTAURANTE_TESTE_BANCO": str(
                    diretorio / "restaurante.sqlite3"
                ),
                "RESTAURANTE_TESTE_LOG": str(diretorio / "servidor.jsonl"),
            }
        )
        porta = self._porta_disponivel()
        saida = diretorio / "stdout.log"
        erros = diretorio / "stderr.log"
        try:
            with (
                saida.open("w", encoding="utf-8") as arquivo_saida,
                erros.open("w", encoding="utf-8") as arquivo_erros,
            ):
                processo = self._iniciar_arvore(
                    [
                        "powershell.exe",
                        "-NoProfile",
                        "-ExecutionPolicy",
                        "Bypass",
                        "-File",
                        str(SCRIPT_INICIALIZACAO),
                        "-Porta",
                        str(porta),
                    ],
                    cwd=diretorio,
                    env=ambiente,
                    stdout=arquivo_saida,
                    stderr=arquivo_erros,
                )
            base = f"http://127.0.0.1:{porta}"
            self._aguardar_http(processo, f"{base}/saude/", saida, erros)

            self._encerrar_arvore(processo, forcar_fallback=True)

            self.assertIsNotNone(processo.poll())
            with self.assertRaises(URLError):
                self._obter(f"{base}/saude/")
        finally:
            if "processo" in locals():
                self._encerrar_arvore(processo)

    @staticmethod
    def _porta_disponivel():
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as servidor:
            servidor.bind(("127.0.0.1", 0))
            return servidor.getsockname()[1]

    @staticmethod
    def _ipv4_lan():
        enderecos = socket.gethostbyname_ex(socket.gethostname())[2]
        for endereco in enderecos:
            if not endereco.startswith(("127.", "169.254.")):
                return endereco
        raise AssertionError("Nenhum endereço IPv4 de LAN foi encontrado")

    def _aguardar_http(self, processo, url, saida, erros):
        limite = time.monotonic() + self.TEMPO_LIMITE_INICIALIZACAO
        while time.monotonic() < limite:
            if processo.poll() is not None:
                self.fail(
                    "Servidor terminou antes de responder. "
                    f"stdout: {saida.read_text(encoding='utf-8', errors='replace')} "
                    f"stderr: {erros.read_text(encoding='utf-8', errors='replace')}"
                )
            try:
                return self._obter(url)
            except URLError:
                time.sleep(0.05)
        self.fail(
            f"Timeout aguardando {url}. "
            f"stdout: {saida.read_text(encoding='utf-8', errors='replace')} "
            f"stderr: {erros.read_text(encoding='utf-8', errors='replace')}"
        )

    @staticmethod
    def _obter(url):
        with urlopen(url, timeout=2) as resposta:
            if resposta.status != 200:
                raise AssertionError(f"{url} respondeu HTTP {resposta.status}")
            return resposta.read()

    @staticmethod
    def _iniciar_arvore(comando, **argumentos_popen):
        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel32.CreateJobObjectW.argtypes = [wintypes.LPVOID, wintypes.LPCWSTR]
        kernel32.CreateJobObjectW.restype = wintypes.HANDLE
        kernel32.SetInformationJobObject.argtypes = [
            wintypes.HANDLE,
            ctypes.c_int,
            wintypes.LPVOID,
            wintypes.DWORD,
        ]
        kernel32.SetInformationJobObject.restype = wintypes.BOOL
        kernel32.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
        kernel32.OpenProcess.restype = wintypes.HANDLE
        kernel32.AssignProcessToJobObject.argtypes = [wintypes.HANDLE, wintypes.HANDLE]
        kernel32.AssignProcessToJobObject.restype = wintypes.BOOL
        kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
        kernel32.CloseHandle.restype = wintypes.BOOL

        handle_job = kernel32.CreateJobObjectW(None, None)
        if not handle_job:
            raise ctypes.WinError(ctypes.get_last_error())
        informacao = _InformacaoEstendidaLimiteJob()
        informacao.BasicLimitInformation.LimitFlags = (
            LIMITE_ENCERRAR_AO_FECHAR_JOB
        )
        if not kernel32.SetInformationJobObject(
            handle_job,
            INFORMACAO_ESTENDIDA_LIMITE_JOB,
            ctypes.byref(informacao),
            ctypes.sizeof(informacao),
        ):
            erro = ctypes.WinError(ctypes.get_last_error())
            kernel32.CloseHandle(handle_job)
            raise erro

        comando_iniciador = [
            sys.executable,
            str(
                RAIZ_PROJETO
                / "restaurante"
                / "testes_suporte"
                / "iniciador_processo.py"
            ),
            *comando,
        ]
        try:
            processo = subprocess.Popen(
                comando_iniciador,
                stdin=subprocess.PIPE,
                **argumentos_popen,
            )
        except BaseException:
            kernel32.CloseHandle(handle_job)
            raise
        handle_processo = kernel32.OpenProcess(
            PROCESS_SET_QUOTA | PROCESS_TERMINATE,
            False,
            processo.pid,
        )
        if not handle_processo:
            erro = ctypes.WinError(ctypes.get_last_error())
            processo.kill()
            processo.wait(timeout=10)
            kernel32.CloseHandle(handle_job)
            raise erro
        try:
            if not kernel32.AssignProcessToJobObject(handle_job, handle_processo):
                erro = ctypes.WinError(ctypes.get_last_error())
                processo.kill()
                processo.wait(timeout=10)
                kernel32.CloseHandle(handle_job)
                raise erro
        finally:
            kernel32.CloseHandle(handle_processo)
        processo.handle_job_restaurante = handle_job
        try:
            processo.stdin.write(b"iniciar\n")
            processo.stdin.flush()
            processo.stdin.close()
        except BaseException:
            kernel32.CloseHandle(handle_job)
            processo.handle_job_restaurante = None
            processo.wait(timeout=10)
            raise
        return processo

    @staticmethod
    def _encerrar_arvore(processo, *, forcar_fallback=False):
        if processo.poll() is None and not forcar_fallback:
            try:
                processo.send_signal(signal.CTRL_BREAK_EVENT)
                processo.wait(timeout=10)
            except (OSError, subprocess.TimeoutExpired):
                pass

        handle_job = getattr(processo, "handle_job_restaurante", None)
        if handle_job:
            kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
            kernel32.TerminateJobObject.argtypes = [wintypes.HANDLE, wintypes.UINT]
            kernel32.TerminateJobObject.restype = wintypes.BOOL
            kernel32.WaitForSingleObject.argtypes = [wintypes.HANDLE, wintypes.DWORD]
            kernel32.WaitForSingleObject.restype = wintypes.DWORD
            kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
            kernel32.CloseHandle.restype = wintypes.BOOL
            if not kernel32.TerminateJobObject(handle_job, 1):
                raise ctypes.WinError(ctypes.get_last_error())
            resultado_espera = kernel32.WaitForSingleObject(handle_job, 10_000)
            if resultado_espera != 0:
                raise TimeoutError(
                    "Timeout aguardando encerramento da árvore de processos"
                )
            if not kernel32.CloseHandle(handle_job):
                raise ctypes.WinError(ctypes.get_last_error())
            processo.handle_job_restaurante = None
        try:
            processo.wait(timeout=10)
        except subprocess.TimeoutExpired:
            processo.kill()
            processo.wait(timeout=10)


class RecursosLocaisInterfaceTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.garcom = UsuarioOperacional.objects.create(
            nome="Garçom LAN",
            papel=UsuarioOperacional.Papel.GARCOM,
        )
        Produto.objects.create(nome="Produto local", preco_centavos=100)

    def test_paginas_operacionais_referenciam_somente_assets_locais(self):
        pagina_inicial = self.client.get("/")
        self.client.post("/usuarios/selecionar/", {"usuario_id": self.garcom.pk})
        pagina_operacional = self.client.get("/garcom/")

        referencias = []
        for resposta in (pagina_inicial, pagina_operacional):
            html = resposta.content.decode("utf-8")
            self.assertEqual(resposta.status_code, 200)
            self.assertNotRegex(html, r"(?:src|href)=[\"']https?://")
            self.assertNotRegex(html, r"(?:src|href)=[\"']//")
            referencias.extend(re.findall(r'(?:src|href)="([^"]+)"', html))

        self.assertIn("/static/interface_web/css/base.css", referencias)
        self.assertIn(
            "/static/interface_web/js/atualizacao_periodica.mjs",
            referencias,
        )
        for referencia in referencias:
            if referencia.startswith("/static/"):
                self.assertTrue(referencia.startswith("/static/interface_web/"))


class DocumentacaoRedeLocalTests(SimpleTestCase):
    def test_readme_documenta_operacao_lan_segura_e_linux_futuro(self):
        readme = (RAIZ_PROJETO / "README.md").read_text(encoding="utf-8")

        termos_obrigatorios = (
            r".\scripts\iniciar_servidor.ps1",
            "0.0.0.0:8000",
            "http://<IPv4-do-servidor>:8000/",
            "ipconfig",
            "New-NetFirewallRule",
            "-Profile Private",
            "-RemoteAddress LocalSubnet",
            "-LocalPort 8000",
            "reserva DHCP",
            ".local/dados/",
            ".local/backups/",
            ".local/logs/",
            "Invoke-RestMethod",
            "/saude/",
            "port forwarding",
            "UPnP",
            "rede local confiável",
            ".venv/bin/python manage.py runserver 0.0.0.0:8000 --noreload",
            "CDN",
        )
        for termo in termos_obrigatorios:
            with self.subTest(termo=termo):
                self.assertIn(termo, readme)
