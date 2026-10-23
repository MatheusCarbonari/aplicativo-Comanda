"""Validação de layout via protocolo público do Chrome DevTools."""

import base64
import json
import os
import secrets
import shutil
import socket
import struct
import subprocess
import time
from pathlib import Path
from urllib.error import URLError
from urllib.parse import quote, urlsplit
from urllib.request import Request, urlopen


class FalhaChrome(RuntimeError):
    pass


def _ler_exato(conexao: socket.socket, quantidade: int) -> bytes:
    partes = []
    restante = quantidade
    while restante:
        parte = conexao.recv(restante)
        if not parte:
            raise FalhaChrome("Chrome encerrou a conexão de diagnóstico.")
        partes.append(parte)
        restante -= len(parte)
    return b"".join(partes)


class _CanalDevTools:
    def __init__(self, endereco: str):
        partes = urlsplit(endereco)
        self._conexao = socket.create_connection(
            (partes.hostname, partes.port), timeout=10
        )
        chave = base64.b64encode(secrets.token_bytes(16)).decode("ascii")
        requisicao = (
            f"GET {partes.path} HTTP/1.1\r\n"
            f"Host: {partes.hostname}:{partes.port}\r\n"
            "Upgrade: websocket\r\nConnection: Upgrade\r\n"
            f"Sec-WebSocket-Key: {chave}\r\n"
            "Sec-WebSocket-Version: 13\r\n\r\n"
        )
        self._conexao.sendall(requisicao.encode("ascii"))
        resposta = b""
        while b"\r\n\r\n" not in resposta:
            resposta += self._conexao.recv(4096)
        if not resposta.startswith(b"HTTP/1.1 101"):
            raise FalhaChrome("Chrome recusou a conexão DevTools.")
        self._proximo_id = 1

    def close(self) -> None:
        self._conexao.close()

    def _enviar(self, conteudo: bytes) -> None:
        mascara = secrets.token_bytes(4)
        mascarado = bytes(
            valor ^ mascara[indice % 4]
            for indice, valor in enumerate(conteudo)
        )
        cabecalho = bytearray([0x81])
        tamanho = len(conteudo)
        if tamanho < 126:
            cabecalho.append(0x80 | tamanho)
        elif tamanho < 65536:
            cabecalho.append(0x80 | 126)
            cabecalho.extend(struct.pack("!H", tamanho))
        else:
            cabecalho.append(0x80 | 127)
            cabecalho.extend(struct.pack("!Q", tamanho))
        self._conexao.sendall(bytes(cabecalho) + mascara + mascarado)

    def _receber(self) -> dict[str, object]:
        primeiro, segundo = _ler_exato(self._conexao, 2)
        codigo = primeiro & 0x0F
        tamanho = segundo & 0x7F
        if tamanho == 126:
            tamanho = struct.unpack("!H", _ler_exato(self._conexao, 2))[0]
        elif tamanho == 127:
            tamanho = struct.unpack("!Q", _ler_exato(self._conexao, 8))[0]
        mascara = _ler_exato(self._conexao, 4) if segundo & 0x80 else None
        conteudo = _ler_exato(self._conexao, tamanho)
        if mascara:
            conteudo = bytes(
                valor ^ mascara[indice % 4]
                for indice, valor in enumerate(conteudo)
            )
        if codigo == 0x9:
            return self._receber()
        if codigo == 0x8:
            raise FalhaChrome("Chrome encerrou o canal DevTools.")
        return json.loads(conteudo.decode("utf-8"))

    def chamar(self, metodo: str, parametros=None) -> dict[str, object]:
        identificador = self._proximo_id
        self._proximo_id += 1
        mensagem = {"id": identificador, "method": metodo}
        if parametros is not None:
            mensagem["params"] = parametros
        self._enviar(json.dumps(mensagem).encode("utf-8"))
        while True:
            resposta = self._receber()
            if resposta.get("id") != identificador:
                continue
            if "error" in resposta:
                raise FalhaChrome(
                    f"Chrome recusou {metodo}: {resposta['error']}."
                )
            return resposta.get("result", {})


def _porta_livre() -> int:
    with socket.socket() as servidor:
        servidor.bind(("127.0.0.1", 0))
        return servidor.getsockname()[1]


def _encerrar_arvore(processo: subprocess.Popen) -> None:
    if processo.poll() is not None:
        return
    if os.name == "nt":
        subprocess.run(
            ["taskkill", "/PID", str(processo.pid), "/T", "/F"],
            capture_output=True,
            timeout=10,
            check=False,
        )
    else:
        processo.kill()
    try:
        processo.wait(timeout=10)
    except subprocess.TimeoutExpired:
        processo.kill()
        processo.wait(timeout=10)


def _obter_json(url: str, *, metodo: str = "GET") -> dict[str, object]:
    with urlopen(Request(url, method=metodo), timeout=2) as resposta:
        return json.load(resposta)


def _aguardar_devtools(porta: int, processo: subprocess.Popen) -> dict[str, object]:
    limite = time.monotonic() + 15
    ultima_falha = None
    while time.monotonic() < limite:
        if processo.poll() is not None:
            break
        try:
            return _obter_json(f"http://127.0.0.1:{porta}/json/version")
        except (OSError, URLError, json.JSONDecodeError) as erro:
            ultima_falha = erro
            time.sleep(0.05)
    raise FalhaChrome(
        f"Chrome não abriu o DevTools em 15 segundos: {ultima_falha}."
    )


def _medir_pagina(
    porta: int, arquivo: Path, largura: int, altura: int
) -> dict[str, object]:
    alvo = _obter_json(
        f"http://127.0.0.1:{porta}/json/new?{quote(arquivo.as_uri(), safe=':/')}",
        metodo="PUT",
    )
    canal = _CanalDevTools(alvo["webSocketDebuggerUrl"])
    try:
        canal.chamar(
            "Emulation.setDeviceMetricsOverride",
            {
                "width": largura,
                "height": altura,
                "deviceScaleFactor": 1,
                "mobile": largura < 500,
            },
        )
        canal.chamar("Page.enable")
        canal.chamar("Page.navigate", {"url": arquivo.as_uri()})
        limite = time.monotonic() + 10
        while time.monotonic() < limite:
            estado = canal.chamar(
                "Runtime.evaluate",
                {"expression": "document.readyState", "returnByValue": True},
            )["result"].get("value")
            if estado == "complete":
                break
            time.sleep(0.05)
        else:
            raise FalhaChrome("A página não concluiu o carregamento em 10 segundos.")
        expressao = """
(() => {
  const controles = [...document.querySelectorAll('a, button, input:not([type=hidden]), select, textarea')]
    .filter((elemento) => getComputedStyle(elemento).display !== 'none');
  const fora = controles.filter((elemento) => {
    const caixa = elemento.getBoundingClientRect();
    return caixa.width <= 0 || caixa.height <= 0 || caixa.left < -1 || caixa.right > innerWidth + 1;
  });
  return {
    largura: innerWidth,
    altura: innerHeight,
    overflow_horizontal: document.documentElement.scrollWidth > document.documentElement.clientWidth + 1,
    controles_verificados: controles.length,
    controles_inoperaveis: fora.length
  };
})()
"""
        resultado = canal.chamar(
            "Runtime.evaluate",
            {"expression": expressao, "returnByValue": True},
        )
        return resultado["result"]["value"]
    finally:
        canal.close()


def validar_paginas_responsivas(
    *, navegador: Path, paginas: dict[str, Path], diretorio_perfil: Path
) -> tuple[str, list[dict[str, object]], dict[str, object]]:
    porta = _porta_livre()
    processo = subprocess.Popen(
        [
            str(navegador),
            "--headless=new",
            "--disable-gpu",
            "--disable-crash-reporter",
            f"--user-data-dir={diretorio_perfil}",
            f"--remote-debugging-port={porta}",
            "about:blank",
        ],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    try:
        informacoes = _aguardar_devtools(porta, processo)
        versao = str(informacoes["Browser"])
        medicoes = []
        for largura, altura in ((390, 844), (1366, 768)):
            for nome, arquivo in paginas.items():
                if processo.poll() is not None:
                    raise FalhaChrome(
                        "Chrome encerrou inesperadamente antes de concluir "
                        f"as medições (código {processo.returncode})."
                    )
                medicao = _medir_pagina(porta, arquivo, largura, altura)
                medicao.update(
                    {
                        "tela": nome,
                        "dimensao_solicitada": f"{largura}x{altura}",
                    }
                )
                medicoes.append(medicao)
        canal_navegador = _CanalDevTools(
            str(informacoes["webSocketDebuggerUrl"])
        )
        try:
            canal_navegador.chamar("Browser.close")
        finally:
            canal_navegador.close()
        try:
            codigo_saida = processo.wait(timeout=15)
        except subprocess.TimeoutExpired as erro:
            raise FalhaChrome(
                "Chrome não encerrou em 15 segundos após Browser.close."
            ) from erro
        if codigo_saida != 0:
            raise FalhaChrome(
                "Chrome encerrou com código inesperado depois das medições: "
                f"{codigo_saida}."
            )
        return versao, medicoes, {
            "modo": "Browser.close",
            "codigo_saida": codigo_saida,
            "resultado": "limpo",
        }
    finally:
        _encerrar_arvore(processo)
