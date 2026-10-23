"""Processo isolado usado pelo comando de validacao de volume."""

import argparse
import json
import os
import platform
import sqlite3
import sys
from datetime import UTC, datetime
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--lancamentos", type=int, required=True)
    parser.add_argument("--dispositivos", type=int, required=True)
    parser.add_argument("--semente", type=int, required=True)
    parser.add_argument("--arquivo-relatorio", type=Path, required=True)
    argumentos = parser.parse_args()

    os.environ.setdefault(
        "DJANGO_SETTINGS_MODULE",
        "restaurante.testes_suporte.configuracao_volume",
    )
    import django

    django.setup()

    from django import get_version as versao_django
    from django.core.management import call_command
    from django.db import connection

    from restaurante.persistencia.models import (
        Atendimento,
        ComandaFisica,
        Lancamento,
        Produto,
        UsuarioOperacional,
    )
    from restaurante.persistencia.sqlite_duravel import observar_pragmas
    from restaurante.ferramentas_administrativas.validacao_volume import (
        META_PRATICA_SEGUNDOS,
        executar_operacoes_concorrentes,
        verificar_invariantes,
    )

    call_command("migrate", interactive=False, verbosity=0)
    garcom = UsuarioOperacional.objects.create(
        nome="Garcom volume",
        papel=UsuarioOperacional.Papel.GARCOM,
    )
    caixa = UsuarioOperacional.objects.create(
        nome="Caixa volume",
        papel=UsuarioOperacional.Papel.CAIXA,
    )
    produto = Produto.objects.create(nome="Produto volume", preco_centavos=137)
    comandas = ComandaFisica.objects.bulk_create(
        [
            ComandaFisica(identificador=f"VOLUME-{indice:03d}")
            for indice in range(argumentos.dispositivos)
        ]
    )
    atendimentos = Atendimento.objects.bulk_create(
        [Atendimento(comanda=comanda) for comanda in comandas]
    )
    totais_esperados = {atendimento.pk: 0 for atendimento in atendimentos}
    lancamentos_preparados = []
    for indice in range(argumentos.lancamentos):
        atendimento = atendimentos[indice % len(atendimentos)]
        lancamentos_preparados.append(
            Lancamento(
                atendimento=atendimento,
                produto=produto,
                quantidade=1,
                preco_unitario_centavos=produto.preco_centavos,
                autor=garcom,
            )
        )
        totais_esperados[atendimento.pk] += produto.preco_centavos
    Lancamento.objects.bulk_create(
        lancamentos_preparados,
        batch_size=1_000,
    )

    resultado_operacoes = executar_operacoes_concorrentes(
        dispositivos=argumentos.dispositivos,
        semente=argumentos.semente,
        garcom_id=garcom.pk,
        caixa_id=caixa.pk,
        produto_id=produto.pk,
        atendimentos=[
            (atendimento.pk, atendimento.comanda.identificador)
            for atendimento in atendimentos
        ],
    )
    if not resultado_operacoes["idempotencia"]["sem_duplicacao"]:
        raise RuntimeError("A verificacao idempotente nao foi concluida sem duplicacao")
    for nome, medicao in resultado_operacoes["operacoes"].items():
        if medicao["concluida"] + medicao["contencao_recuperada"] == 0:
            raise RuntimeError(f"Nenhuma operacao {nome} foi concluida")
    totais_esperados.update(resultado_operacoes["totais_confirmados"])

    pragmas = observar_pragmas(connection)
    with connection.cursor() as cursor:
        cursor.execute("PRAGMA integrity_check")
        integridade = cursor.fetchone()[0]
    if integridade != "ok":
        raise RuntimeError("PRAGMA integrity_check nao retornou ok")

    atendimentos_fechados = set(
        Atendimento.objects.filter(estado=Atendimento.Estado.ENCERRADO).values_list(
            "comanda_id", flat=True
        )
    )
    invariantes = verificar_invariantes(
        connection.connection,
        totais_esperados=totais_esperados,
        lancamentos_confirmados=set(
            resultado_operacoes["lancamentos_confirmados"]
        ),
        comandas_que_devem_estar_disponiveis=atendimentos_fechados,
    )

    relatorio = {
        "executado_em": datetime.now(UTC).isoformat(),
        "ambiente": {
            "sistema_operacional": platform.platform(),
            "python": platform.python_version(),
            "django": versao_django(),
            "sqlite": sqlite3.sqlite_version,
        },
        "sqlite": {
            "journal_mode": pragmas["journal_mode"],
            "synchronous": (
                "FULL"
                if pragmas["synchronous"] == 2
                else pragmas["synchronous"]
            ),
            "integrity_check": integridade,
        },
        "cenario": {
            "semente": argumentos.semente,
            "lancamentos_persistidos": Lancamento.objects.count(),
            "dispositivos_simulados": argumentos.dispositivos,
            "dispositivos_observados": resultado_operacoes[
                "dispositivos_observados"
            ],
        },
        "operacoes": resultado_operacoes["operacoes"],
        "contencao": resultado_operacoes["contencao"],
        "idempotencia": resultado_operacoes["idempotencia"],
        "meta_pratica_segundos": META_PRATICA_SEGUNDOS,
        "invariantes": invariantes,
    }
    argumentos.arquivo_relatorio.write_text(
        json.dumps(relatorio, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(
        f"Cenario concluido: {relatorio['cenario']['lancamentos_persistidos']} "
        "Lancamentos persistidos."
    )
    print(
        f"Dispositivos simulados: {argumentos.dispositivos}; "
        f"SQLite: {pragmas['journal_mode']}/FULL."
    )
    for nome, medicao in relatorio["operacoes"].items():
        print(
            f"{nome}: {medicao['quantidade']} operacoes; "
            f"p95={medicao['tempos_ms']['p95']} ms; "
            f"resultado={medicao['p95_em_relacao_a_meta_pratica']}."
        )
    print(
        "Contencoes: "
        f"SQLITE_BUSY={relatorio['contencao']['sqlite_busy']}, "
        f"SQLITE_LOCKED={relatorio['contencao']['sqlite_locked']}, "
        f"retries={relatorio['contencao']['retries']}."
    )
    print(f"Invariantes: {invariantes['resultado']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
