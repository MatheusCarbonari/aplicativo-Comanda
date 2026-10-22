"""Processo auxiliar da verificação de durabilidade contra SQLite real."""

import argparse
import json
import os
import sys
from dataclasses import asdict, is_dataclass
from io import StringIO
from pathlib import Path


def _configurar_django(caminho_banco: Path, caminho_log: Path) -> None:
    os.environ.setdefault(
        "DJANGO_SETTINGS_MODULE",
        "restaurante.infraestrutura.configuracao",
    )
    from restaurante.infraestrutura import configuracao

    configuracao.DATABASES["default"]["NAME"] = caminho_banco
    configuracao.LOGGING["handlers"]["arquivo_estruturado"]["filename"] = (
        caminho_log
    )

    import django

    django.setup()


def _emitir(payload: dict[str, object]) -> None:
    print(json.dumps(payload, ensure_ascii=False), flush=True)


def _aguardar_comando() -> str:
    return sys.stdin.readline().strip()


def _preparar() -> None:
    from django.core.management import call_command

    from restaurante.persistencia.models import Produto, UsuarioOperacional

    call_command(
        "migrate",
        interactive=False,
        verbosity=0,
        stdout=StringIO(),
        stderr=StringIO(),
    )
    call_command(
        "carregar_dados_iniciais",
        stdout=StringIO(),
        stderr=StringIO(),
    )
    garcom = UsuarioOperacional.objects.get(nome="Garçom 1")
    caixa = UsuarioOperacional.objects.get(nome="Caixa 1")
    produto = Produto.objects.get(nome="Café")
    _emitir(
        {
            "garcom_id": garcom.pk,
            "caixa_id": caixa.pk,
            "produto_id": produto.pk,
        }
    )


def _executar_operacao(argumentos: argparse.Namespace) -> None:
    from django.db import connection, transaction

    from restaurante.aplicacao.cancelar_lancamento import cancelar_lancamento
    from restaurante.aplicacao.fechar_atendimento import fechar_atendimento
    from restaurante.aplicacao.registrar_lancamento_adicional import (
        registrar_lancamento_adicional,
    )
    from restaurante.aplicacao.registrar_primeiro_lancamento import (
        registrar_primeiro_lancamento,
    )
    from restaurante.persistencia.sqlite_duravel import (
        observar_pragmas,
        validar_pragmas,
    )

    pragmas = observar_pragmas(connection)
    validar_pragmas(
        journal_mode=pragmas["journal_mode"],
        synchronous=pragmas["synchronous"],
        caminho_banco=connection.settings_dict["NAME"],
    )

    with transaction.atomic():
        if argumentos.operacao == "primeiro_lancamento":
            resultado = registrar_primeiro_lancamento(
                usuario_operacional_id=argumentos.usuario_id,
                identificador_comanda=argumentos.comanda,
                produto_id=argumentos.produto_id,
                quantidade=1,
                chave_idempotencia=argumentos.chave,
            )
        elif argumentos.operacao == "lancamento_adicional":
            resultado = registrar_lancamento_adicional(
                usuario_operacional_id=argumentos.usuario_id,
                identificador_comanda=argumentos.comanda,
                produto_id=argumentos.produto_id,
                quantidade=1,
                chave_idempotencia=argumentos.chave,
            )
        elif argumentos.operacao == "cancelamento":
            resultado = cancelar_lancamento(
                usuario_operacional_id=argumentos.usuario_id,
                lancamento_id=argumentos.lancamento_id,
                motivo=argumentos.motivo,
                descricao=argumentos.descricao,
                chave_idempotencia=argumentos.chave,
            )
        elif argumentos.operacao == "fechamento":
            resultado = fechar_atendimento(
                usuario_operacional_id=argumentos.usuario_id,
                atendimento_id=argumentos.atendimento_id,
                revisao_apresentada=argumentos.revisao,
                chave_idempotencia=argumentos.chave,
            )
        else:
            raise ValueError(f"Operação não suportada: {argumentos.operacao}")
        if argumentos.ponto == "antes_commit":
            _emitir({"sinal": "antes_commit", **pragmas})
            _aguardar_comando()

    _emitir({"sinal": "depois_commit", **pragmas})
    if _aguardar_comando() == "entregar":
        _emitir(
            {
                "resultado": (
                    asdict(resultado) if is_dataclass(resultado) else resultado
                )
            }
        )


def _inspecionar(argumentos: argparse.Namespace) -> None:
    from django.db import connection

    from restaurante.aplicacao.revisao_fechamento import (
        calcular_revisao_fechamento,
    )
    from restaurante.persistencia.models import (
        Atendimento,
        CancelamentoLancamento,
        ComandaFisica,
        Lancamento,
        RegistroIdempotencia,
    )
    from restaurante.persistencia.sqlite_duravel import observar_pragmas

    comanda = ComandaFisica.objects.get(identificador=argumentos.comanda)
    atendimentos = [
        {
            "id": atendimento.pk,
            "estado": atendimento.estado,
            "fechado_por_id": atendimento.fechado_por_id,
            "fechado_em": (
                None
                if atendimento.fechado_em is None
                else atendimento.fechado_em.isoformat()
            ),
        }
        for atendimento in Atendimento.objects.filter(comanda=comanda).order_by(
            "pk"
        )
    ]
    lancamentos = list(
        Lancamento.objects.filter(atendimento__comanda=comanda)
        .order_by("pk")
        .values("id", "atendimento_id", "quantidade")
    )
    cancelamentos = list(
        CancelamentoLancamento.objects.filter(
            lancamento__atendimento__comanda=comanda
        )
        .order_by("pk")
        .values("id", "lancamento_id", "motivo")
    )
    idempotencias = list(
        RegistroIdempotencia.objects.order_by("pk").values(
            "chave",
            "operacao",
            "resultado",
        )
    )
    atendimento_atual = (
        Atendimento.objects.filter(comanda=comanda).order_by("-pk").first()
    )
    pragmas = observar_pragmas(connection)
    _emitir(
        {
            "atendimentos": atendimentos,
            "lancamentos": lancamentos,
            "lancamentos_validos": Lancamento.objects.filter(
                atendimento__comanda=comanda,
                cancelamento__isnull=True,
            ).count(),
            "cancelamentos": cancelamentos,
            "idempotencias": idempotencias,
            "comanda_disponivel": not Atendimento.objects.filter(
                comanda=comanda,
                estado=Atendimento.Estado.ABERTO,
            ).exists(),
            "atendimentos_abertos": Atendimento.objects.filter(
                comanda=comanda,
                estado=Atendimento.Estado.ABERTO,
            ).count(),
            "revisao": (
                None
                if atendimento_atual is None
                else calcular_revisao_fechamento(atendimento_atual)
            ),
            **pragmas,
        }
    )


def _criar_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    parser.add_argument("--banco", type=Path, required=True)
    parser.add_argument("--log", type=Path, required=True)
    subcomandos = parser.add_subparsers(dest="acao", required=True)
    subcomandos.add_parser("preparar")
    subcomandos.add_parser("travar")

    operar = subcomandos.add_parser("operar")
    operar.add_argument("--operacao", required=True)
    operar.add_argument(
        "--ponto",
        choices=("antes_commit", "depois_commit"),
        required=True,
    )
    operar.add_argument("--chave", required=True)
    operar.add_argument("--usuario-id", type=int, required=True)
    operar.add_argument("--produto-id", type=int)
    operar.add_argument("--comanda")
    operar.add_argument("--lancamento-id", type=int)
    operar.add_argument("--motivo")
    operar.add_argument("--descricao")
    operar.add_argument("--atendimento-id", type=int)
    operar.add_argument("--revisao")

    inspecionar = subcomandos.add_parser("inspecionar")
    inspecionar.add_argument("--comanda", required=True)
    return parser


def main() -> None:
    argumentos = _criar_parser().parse_args()
    _configurar_django(argumentos.banco, argumentos.log)
    if argumentos.acao == "preparar":
        _preparar()
    elif argumentos.acao == "travar":
        _aguardar_comando()
    elif argumentos.acao == "operar":
        _executar_operacao(argumentos)
    else:
        _inspecionar(argumentos)


if __name__ == "__main__":
    main()
