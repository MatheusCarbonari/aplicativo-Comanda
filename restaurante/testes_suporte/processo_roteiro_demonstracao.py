"""Executa o roteiro HTTP em processo e banco isolados."""

import argparse
import json
import os
import re
import shutil
import sqlite3
from datetime import UTC, datetime
from pathlib import Path


class FalhaRoteiro(Exception):
    pass


def _exigir(condicao: bool, mensagem: str) -> None:
    if not condicao:
        raise FalhaRoteiro(mensagem)


def _extrair(html: str, padrao: str, descricao: str) -> str:
    resultado = re.search(padrao, html, re.DOTALL)
    if resultado is None:
        raise FalhaRoteiro(f"Não foi possível localizar {descricao} no HTML.")
    return resultado.group(1)


def _html(resposta) -> str:
    return resposta.content.decode(resposta.charset or "utf-8")


def _extrair_usuario(html: str, nome: str) -> str:
    for formulario in re.findall(
        r'<form[^>]+action="/usuarios/selecionar/"[^>]*>.*?</form>',
        html,
        re.DOTALL,
    ):
        if nome in formulario:
            return _extrair(
                formulario,
                r'name="usuario_id" value="(\d+)"',
                f"identificador de {nome}",
            )
    raise FalhaRoteiro(f"Não foi possível localizar {nome} no HTML.")


def _selecionar_usuario(cliente, nome: str, destino: str) -> None:
    cliente.post("/usuarios/trocar/")
    identificador = _extrair_usuario(_html(cliente.get("/")), nome)
    resposta = cliente.post(
        "/usuarios/selecionar/", {"usuario_id": identificador}
    )
    _exigir(
        resposta.status_code == 302 and resposta.url == destino,
        f"Seleção de {nome} falhou.",
    )


def _extrair_produto(html: str, nome_procurado: str) -> str:
    for identificador, nome in re.findall(
        r'<option value="(\d+)">\s*([^<]+?)\s*</option>', html
    ):
        if nome == nome_procurado:
            return identificador
    raise FalhaRoteiro(
        f"Não foi possível localizar Produto {nome_procurado} no HTML."
    )


def _consultar_garcom(cliente) -> str:
    resposta = cliente.get("/comandas/consultar/", {"identificador": "001"})
    _exigir(resposta.status_code == 200, "Consulta do Garçom falhou.")
    return _html(resposta)


def _registrar_adicional(
    cliente,
    html_consulta: str,
    produto: str,
    quantidade: int,
    chave: str | None = None,
):
    resposta = cliente.post(
        "/lancamentos/adicional/",
        {
            "identificador_comanda": "001",
            "produto_id": _extrair_produto(html_consulta, produto),
            "quantidade": str(quantidade),
            "chave_idempotencia": chave
            or _extrair(
                html_consulta,
                r'name="chave_idempotencia" value="([^"]+)"',
                "chave do Lançamento adicional",
            ),
        },
    )
    _exigir(
        resposta.status_code == 200
        and "Lançamento registrado" in _html(resposta),
        f"Lançamento adicional de {produto} falhou.",
    )
    return resposta


def _executar_fluxo(cliente) -> tuple[list[str], dict[str, str]]:
    etapas: list[str] = []
    _selecionar_usuario(cliente, "Garçom 1", "/garcom/")
    etapas.append("Garçom selecionado")

    html = _consultar_garcom(cliente)
    _exigir(
        "Comanda disponível" in html,
        "Consulta da Comanda disponível falhou.",
    )
    etapas.append("Comanda disponível consultada")

    pagina_garcom = _html(cliente.get("/garcom/"))
    resposta = cliente.post(
        "/lancamentos/primeiro/",
        {
            "identificador_comanda": "001",
            "produto_id": _extrair_produto(pagina_garcom, "Água mineral"),
            "quantidade": "2",
            "chave_idempotencia": _extrair(
                pagina_garcom,
                r'name="chave_idempotencia" value="([^"]+)"',
                "chave do primeiro Lançamento",
            ),
        },
    )
    _exigir(
        resposta.status_code == 200
        and "Lançamento registrado" in _html(resposta),
        "Primeiro Lançamento falhou.",
    )
    etapas.append("Primeiro Lançamento registrado")

    html = _consultar_garcom(cliente)
    _registrar_adicional(cliente, html, "Água mineral", 1)
    html = _consultar_garcom(cliente)
    _registrar_adicional(cliente, html, "Refrigerante", 2)
    etapas.append("Lançamentos adicionais registrados")

    _selecionar_usuario(cliente, "Garçom 2", "/garcom/")
    etapas.append("Outro Garçom selecionado")
    html = _consultar_garcom(cliente)
    _registrar_adicional(cliente, html, "Pizza", 1)
    html = _consultar_garcom(cliente)
    artigo_refrigerante = next(
        (
            artigo
            for artigo in re.findall(r"<article>.*?</article>", html, re.DOTALL)
            if "<strong>Refrigerante</strong>" in artigo
        ),
        None,
    )
    _exigir(
        artigo_refrigerante is not None,
        "Lançamento a cancelar não apareceu.",
    )
    resposta = cliente.post(
        "/lancamentos/cancelar/",
        {
            "lancamento_id": _extrair(
                artigo_refrigerante,
                r'name="lancamento_id" value="(\d+)"',
                "Lançamento Refrigerante",
            ),
            "chave_idempotencia": _extrair(
                artigo_refrigerante,
                r'name="chave_idempotencia" value="([^"]+)"',
                "chave do cancelamento",
            ),
            "motivo": "DUPLICADO",
            "descricao": "",
        },
    )
    _exigir(
        resposta.status_code == 200
        and "Lançamento cancelado" in _html(resposta),
        "Cancelamento falhou.",
    )
    etapas.append("Lançamento cancelado")

    _selecionar_usuario(cliente, "Caixa 1", "/caixa/")
    resposta = cliente.get(
        "/caixa/comandas/consultar/", {"identificador": "001"}
    )
    html_caixa = _html(resposta)
    _exigir(
        resposta.status_code == 200
        and "Água mineral | qtd 3" in html_caixa
        and "Pizza | qtd 1" in html_caixa
        and "Total atual: R$ 60,00" in html_caixa
        and "Lançamentos cancelados" in html_caixa
        and "Garçom 1" in html_caixa
        and "Garçom 2" in html_caixa,
        "Consolidação do Caixa não corresponde ao histórico esperado.",
    )
    etapas.append("Caixa consultou consolidação")
    url_fechamento = _extrair(
        html_caixa,
        r'href="(/caixa/atendimentos/\d+/fechar/)"',
        "ação de Fechamento",
    )
    atendimento_anterior = _extrair(
        url_fechamento, r"/atendimentos/(\d+)/", "Atendimento"
    )
    html_confirmacao = _html(cliente.get(url_fechamento))
    revisao_antiga = _extrair(
        html_confirmacao,
        r'name="revisao" value="([^"]+)"',
        "revisão",
    )
    chave_fechamento_antiga = _extrair(
        html_confirmacao,
        r'name="chave_idempotencia" value="([^"]+)"',
        "chave do Fechamento",
    )

    _selecionar_usuario(cliente, "Garçom 1", "/garcom/")
    html = _consultar_garcom(cliente)
    chave_resposta_perdida = "roteiro-resposta-perdida-cafe"
    primeira_resposta = _registrar_adicional(
        cliente, html, "Café", 1, chave_resposta_perdida
    )
    resposta_repetida = _registrar_adicional(
        cliente, html, "Café", 1, chave_resposta_perdida
    )
    _exigir(
        _html(primeira_resposta) == _html(resposta_repetida),
        "Replay idempotente não recuperou o mesmo resultado.",
    )

    _selecionar_usuario(cliente, "Caixa 1", "/caixa/")
    resposta = cliente.post(
        url_fechamento,
        {
            "revisao": revisao_antiga,
            "chave_idempotencia": chave_fechamento_antiga,
        },
    )
    html_confirmacao = _html(resposta)
    _exigir(
        resposta.status_code == 409
        and "mudou desde a conferência" in html_confirmacao
        and "Total atual: R$ 66,00" in html_confirmacao,
        "Mudança posterior não exigiu nova confirmação.",
    )
    etapas.append("Mudança posterior exigiu nova confirmação")
    resposta = cliente.post(
        url_fechamento,
        {
            "revisao": _extrair(
                html_confirmacao,
                r'name="revisao" value="([^"]+)"',
                "nova revisão",
            ),
            "chave_idempotencia": _extrair(
                html_confirmacao,
                r'name="chave_idempotencia" value="([^"]+)"',
                "nova chave do Fechamento",
            ),
        },
    )
    _exigir(
        resposta.status_code == 302 and "resumo-final" in resposta.url,
        "Fechamento confirmado falhou.",
    )
    url_resumo = resposta.url
    etapas.append("Atendimento fechado")
    html_resumo = _html(cliente.get(url_resumo))
    _exigir(
        "Total final: R$ 66,00" in html_resumo
        and "Lançamentos cancelados" in html_resumo
        and "Refrigerante" in html_resumo,
        "Resumo final não preservou total e histórico.",
    )
    etapas.append("Resumo final consultado")

    disponivel = _html(
        cliente.get(
            "/caixa/comandas/consultar/", {"identificador": "001"}
        )
    )
    _exigir("Comanda disponível" in disponivel, "Comanda não foi liberada.")
    _selecionar_usuario(cliente, "Garçom 1", "/garcom/")
    pagina_garcom = _html(cliente.get("/garcom/"))
    resposta = cliente.post(
        "/lancamentos/primeiro/",
        {
            "identificador_comanda": "001",
            "produto_id": _extrair_produto(pagina_garcom, "Sobremesa"),
            "quantidade": "1",
            "chave_idempotencia": _extrair(
                pagina_garcom,
                r'name="chave_idempotencia" value="([^"]+)"',
                "chave da reutilização",
            ),
        },
    )
    _exigir(resposta.status_code == 200, "Reutilização da Comanda falhou.")
    html_novo = _consultar_garcom(cliente)
    _exigir(
        "Total atual: <strong>R$ 15,00</strong>" in html_novo
        and "<strong>Sobremesa</strong>" in html_novo
        and '<section id="historico-cancelamentos"' not in html_novo
        and "<strong>Pizza</strong>" not in html_novo,
        "Novo Atendimento misturou o histórico anterior.",
    )
    _selecionar_usuario(cliente, "Caixa 1", "/caixa/")
    html_resumo_antigo = _html(cliente.get(url_resumo))
    _exigir(
        f"Atendimento {atendimento_anterior}" in html_resumo_antigo
        and "Total final: R$ 66,00" in html_resumo_antigo,
        "Resumo encerrado deixou de estar disponível.",
    )
    etapas.append("Comanda reutilizada sem misturar históricos")
    return etapas, {
        "consulta_garcom": html_novo,
        "confirmacao_caixa": html_confirmacao,
        "resumo_final": html_resumo,
    }


def _localizar_navegador() -> Path:
    candidatos = [
        Path(os.environ.get("PROGRAMFILES", ""))
        / "Google/Chrome/Application/chrome.exe",
        Path(os.environ.get("PROGRAMFILES(X86)", ""))
        / "Google/Chrome/Application/chrome.exe",
    ]
    executavel = next((item for item in candidatos if item.is_file()), None)
    if executavel is None:
        encontrado = shutil.which("chrome") or shutil.which("google-chrome")
        executavel = Path(encontrado) if encontrado else None
    if executavel is None:
        raise FalhaRoteiro("Google Chrome não está disponível para a validação.")
    return executavel


def _preparar_html_visual(html: str, css: Path) -> str:
    html = re.sub(
        r'<link rel="stylesheet" href="[^"]+">',
        f'<link rel="stylesheet" href="{css.as_uri()}">',
        html,
    )
    html = re.sub(r'<script type="module"[^>]*></script>', "", html)
    return html


def _validar_responsividade(
    paginas: dict[str, str], diretorio: Path
) -> dict[str, object]:
    from restaurante.testes_suporte.chrome_responsivo import (
        FalhaChrome,
        validar_paginas_responsivas,
    )

    navegador = _localizar_navegador()
    css = (
        Path(__file__).resolve().parents[1]
        / "interface_web/static/interface_web/css/base.css"
    ).resolve()
    arquivos = {}
    for nome, conteudo in paginas.items():
        arquivo = diretorio / f"{nome}.html"
        arquivo.write_text(_preparar_html_visual(conteudo, css), encoding="utf-8")
        arquivos[nome] = arquivo
    try:
        versao, medicoes, encerramento = validar_paginas_responsivas(
            navegador=navegador,
            paginas=arquivos,
            diretorio_perfil=diretorio / "perfil-chrome",
        )
    except FalhaChrome as erro:
        raise FalhaRoteiro(str(erro)) from erro
    for medicao in medicoes:
        _exigir(
            not medicao["overflow_horizontal"]
            and medicao["largura"]
            == int(str(medicao["dimensao_solicitada"]).split("x")[0])
            and medicao["altura"]
            == int(str(medicao["dimensao_solicitada"]).split("x")[1])
            and (
                medicao["controles_verificados"] > 0
                or medicao["tela"] == "resumo_final"
            )
            and medicao["controles_inoperaveis"] == 0,
            f"A tela não está operável: {medicao}.",
        )
    edge = Path(os.environ.get("PROGRAMFILES(X86)", "")) / (
        "Microsoft/Edge/Application/msedge.exe"
    )
    return {
        "resultado": "aprovado",
        "navegador": versao,
        "engine": "Chromium",
        "dimensoes": ["390x844", "1366x768"],
        "medicoes": medicoes,
        "encerramento": encerramento,
        "edge": (
            "disponível, não automatizado"
            if edge.is_file()
            else "não disponível, não automatizado"
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--arquivo-relatorio", type=Path, required=True)
    parser.add_argument("--modo-teste", action="store_true")
    argumentos = parser.parse_args()

    os.environ.setdefault(
        "DJANGO_SETTINGS_MODULE",
        "restaurante.testes_suporte.configuracao_roteiro",
    )
    import django

    django.setup()

    from django.core.management import call_command
    from django.db import connection
    from django.test import Client

    from restaurante.persistencia.sqlite_duravel import observar_pragmas

    call_command("migrate", interactive=False, verbosity=0)
    call_command("carregar_dados_iniciais", verbosity=0)

    etapas, paginas = _executar_fluxo(Client())
    pragmas = observar_pragmas(connection)
    with connection.cursor() as cursor:
        cursor.execute("PRAGMA integrity_check")
        integridade = cursor.fetchone()[0]
    _exigir(integridade == "ok", "PRAGMA integrity_check não retornou ok.")

    relatorio = {
        "executado_em": datetime.now(UTC).isoformat(),
        "sqlite": {
            "journal_mode": pragmas["journal_mode"],
            "synchronous": (
                "FULL" if pragmas["synchronous"] == 2 else pragmas["synchronous"]
            ),
            "integrity_check": integridade,
            "versao": sqlite3.sqlite_version,
        },
        "fluxo_web": {"resultado": "aprovado", "etapas": etapas},
        "idempotencia": {
            "resultado": "aprovado",
            "evidencia": (
                "reenvio da mesma chave retornou o resultado sem duplicação"
            ),
        },
        "reutilizacao_comanda": {
            "resultado": "aprovado",
            "evidencia": (
                "novo Atendimento sem histórico do Atendimento encerrado"
            ),
        },
        "responsividade": (
            {"resultado": "não executada no modo de teste"}
            if argumentos.modo_teste
            else _validar_responsividade(
                paginas,
                Path(os.environ["RESTAURANTE_ROTEIRO_BANCO"]).parent,
            )
        ),
        "leitor_fisico": {
            "resultado": "manual",
            "automatizado": False,
            "roteiro": "README.md#validação-manual-com-leitor-físico",
        },
        "falhas": [],
    }
    argumentos.arquivo_relatorio.write_text(
        json.dumps(relatorio, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"Fluxo HTTP aprovado: {len(etapas)} etapas.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
