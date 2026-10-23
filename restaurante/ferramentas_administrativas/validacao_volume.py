import math
import sqlite3
import threading
import time
from concurrent.futures import ThreadPoolExecutor, wait
from dataclasses import dataclass, field
from statistics import median

from django.db import close_old_connections

from restaurante.aplicacao.consultar_estado_comanda import (
    consultar_estado_comanda,
)
from restaurante.aplicacao.contencao_persistencia import (
    PersistenciaTemporariamenteIndisponivel,
    observar_contencoes,
)
from restaurante.aplicacao.fechar_atendimento import (
    AtendimentoJaEncerrado,
    AtendimentoNaoEncontrado,
    RevisaoFechamentoDesatualizada,
    fechar_atendimento,
)
from restaurante.aplicacao.registrar_lancamento_adicional import (
    AtendimentoAbertoNaoEncontrado,
    registrar_lancamento_adicional,
)
from restaurante.aplicacao.registrar_primeiro_lancamento import (
    ComandaNaoEncontrada,
    ProdutoNaoEncontrado,
)
from restaurante.aplicacao.usuarios_operacionais import (
    PapelNaoPermitido,
    UsuarioOperacionalInvalido,
)
from restaurante.dominio.lancamentos import QuantidadeInvalida
from restaurante.aplicacao.revisao_fechamento import calcular_revisao_fechamento
from restaurante.persistencia.models import Atendimento, Lancamento


META_PRATICA_SEGUNDOS = 1.0
ERROS_DOMINIO = (
    AtendimentoAbertoNaoEncontrado,
    AtendimentoJaEncerrado,
    AtendimentoNaoEncontrado,
    ComandaNaoEncontrada,
    PapelNaoPermitido,
    ProdutoNaoEncontrado,
    QuantidadeInvalida,
    RevisaoFechamentoDesatualizada,
    UsuarioOperacionalInvalido,
)


class InvarianteViolada(Exception):
    pass


@dataclass
class ContadorContencao:
    sqlite_busy: int = 0
    sqlite_locked: int = 0
    retries: int = 0
    _exclusao: threading.Lock = field(default_factory=threading.Lock)

    def registrar(self, erro) -> None:
        causa = erro.__cause__
        codigo = getattr(causa, "sqlite_errorcode", None)
        mensagem = str(erro).lower()
        nome = (
            "sqlite_locked"
            if (
                isinstance(codigo, int)
                and (codigo & 0xFF) == sqlite3.SQLITE_LOCKED
            )
            or "table is locked" in mensagem
            else "sqlite_busy"
        )
        with self._exclusao:
            setattr(self, nome, getattr(self, nome) + 1)
            self.retries += 1

    def resumo(self) -> dict[str, int]:
        with self._exclusao:
            return {
                "sqlite_busy": self.sqlite_busy,
                "sqlite_locked": self.sqlite_locked,
                "retries": self.retries,
            }


@dataclass
class _Medicoes:
    tempos_ms: list[float] = field(default_factory=list)
    concluida: int = 0
    erro_dominio: int = 0
    contencao_recuperada: int = 0
    contencao_persistente: int = 0


def executar_operacoes_concorrentes(
    *,
    dispositivos: int,
    semente: int,
    garcom_id: int,
    caixa_id: int,
    produto_id: int,
    atendimentos: list[tuple[int, str]],
) -> dict[str, object]:
    barreira = threading.Barrier(dispositivos, timeout=15)
    exclusao = threading.Lock()
    medicoes = {
        "registro_lancamento": _Medicoes(),
        "consulta": _Medicoes(),
        "fechamento": _Medicoes(),
    }
    contador_contencao = ContadorContencao()
    lancamentos_confirmados: list[int] = []
    repeticao_idempotente: list[int] = []
    totais_confirmados: dict[int, int] = {}
    dispositivos_observados: set[int] = set()

    def medir(tipo, executar):
        inicio = time.perf_counter()
        ocorrencias_contencao = 0
        categoria = "concluida"

        def observar_operacao(erro):
            nonlocal ocorrencias_contencao
            ocorrencias_contencao += 1
            contador_contencao.registrar(erro)

        try:
            with observar_contencoes(observar_operacao):
                resultado = executar()
            if ocorrencias_contencao:
                categoria = "contencao_recuperada"
            return resultado
        except PersistenciaTemporariamenteIndisponivel:
            categoria = "contencao_persistente"
            return None
        except ERROS_DOMINIO:
            categoria = "erro_dominio"
            return None
        finally:
            duracao = (time.perf_counter() - inicio) * 1_000
            with exclusao:
                medicoes[tipo].tempos_ms.append(duracao)
                setattr(
                    medicoes[tipo],
                    categoria,
                    getattr(medicoes[tipo], categoria) + 1,
                )

    def executar_dispositivo(indice):
        close_old_connections()
        try:
            with exclusao:
                dispositivos_observados.add(threading.get_ident())
            barreira.wait()
            atendimento_id, identificador = atendimentos[indice]
            tipo = indice % 3
            if tipo == 0:
                chave = f"volume-{semente}-registro-{indice}"

                def registrar():
                    return registrar_lancamento_adicional(
                        garcom_id,
                        identificador,
                        produto_id,
                        1,
                        chave,
                    )

                resultado = medir("registro_lancamento", registrar)
                if resultado is not None:
                    with exclusao:
                        lancamentos_confirmados.append(resultado.lancamento_id)
                        totais_confirmados[resultado.atendimento_id] = (
                            resultado.total_centavos
                        )
                if indice == 0 and resultado is not None:
                    repetido = medir("registro_lancamento", registrar)
                    if repetido is not None:
                        with exclusao:
                            repeticao_idempotente.extend(
                                [resultado.lancamento_id, repetido.lancamento_id]
                            )
            elif tipo == 1:
                medir(
                    "consulta",
                    lambda: consultar_estado_comanda(garcom_id, identificador),
                )
            else:
                def fechar():
                    atendimento = Atendimento.objects.get(pk=atendimento_id)
                    revisao = calcular_revisao_fechamento(atendimento)
                    return fechar_atendimento(
                        caixa_id,
                        atendimento_id,
                        revisao,
                        f"volume-{semente}-fechamento-{indice}",
                    )

                medir("fechamento", fechar)
        finally:
            close_old_connections()

    with ThreadPoolExecutor(
        max_workers=dispositivos,
        thread_name_prefix="dispositivo-volume",
    ) as executor:
        futuros = [
            executor.submit(executar_dispositivo, indice)
            for indice in range(dispositivos)
        ]
        concluidos, pendentes = wait(futuros, timeout=60)
        if pendentes:
            for futuro in pendentes:
                futuro.cancel()
            raise TimeoutError("Workers excederam o limite de 60 segundos")
        for futuro in concluidos:
            futuro.result()

    medir(
        "fechamento",
        lambda: fechar_atendimento(
            caixa_id,
            -1,
            "0" * 64,
            f"volume-{semente}-fechamento-rejeitado",
        ),
    )

    if lancamentos_confirmados:
        encontrados = set(
            Lancamento.objects.filter(pk__in=lancamentos_confirmados).values_list(
                "pk", flat=True
            )
        )
        if encontrados != set(lancamentos_confirmados):
            raise AssertionError("Lancamento confirmado desapareceu")

    return {
        "operacoes": {
            nome: _resumir_medicoes(valores)
            for nome, valores in medicoes.items()
        },
        "contencao": contador_contencao.resumo(),
        "idempotencia": {
            "sem_duplicacao": (
                len(repeticao_idempotente) == 2
                and len(set(repeticao_idempotente)) == 1
            )
        },
        "lancamentos_confirmados": lancamentos_confirmados,
        "totais_confirmados": totais_confirmados,
        "dispositivos_observados": len(dispositivos_observados),
    }


def verificar_invariantes(
    conexao: sqlite3.Connection,
    *,
    totais_esperados: dict[int, int],
    lancamentos_confirmados: set[int],
    comandas_que_devem_estar_disponiveis: set[int] | None = None,
) -> dict[str, object]:
    duplicado = conexao.execute(
        "SELECT comanda_id FROM persistencia_atendimento "
        "WHERE estado = 'ABERTO' GROUP BY comanda_id HAVING COUNT(*) > 1 "
        "LIMIT 1"
    ).fetchone()
    if duplicado is not None:
        raise InvarianteViolada(
            f"Atendimento aberto duplicado para Comanda fisica {duplicado[0]}."
        )

    posterior = conexao.execute(
        "SELECT l.id FROM persistencia_lancamento l "
        "JOIN persistencia_atendimento a ON a.id = l.atendimento_id "
        "WHERE a.estado = 'ENCERRADO' AND a.fechado_em IS NOT NULL "
        "AND l.horario > a.fechado_em LIMIT 1"
    ).fetchone()
    if posterior is not None:
        raise InvarianteViolada(
            f"Lancamento {posterior[0]} associado depois do Fechamento."
        )

    if lancamentos_confirmados:
        marcadores = ",".join("?" for _ in lancamentos_confirmados)
        encontrados = {
            linha[0]
            for linha in conexao.execute(
                f"SELECT id FROM persistencia_lancamento WHERE id IN ({marcadores})",
                tuple(sorted(lancamentos_confirmados)),
            )
        }
        if encontrados != lancamentos_confirmados:
            raise InvarianteViolada("Lancamento confirmado desapareceu.")

    totais_persistidos = dict(
        conexao.execute(
            "SELECT a.id, COALESCE(SUM(CASE WHEN c.id IS NULL "
            "THEN l.quantidade * l.preco_unitario_centavos ELSE 0 END), 0) "
            "FROM persistencia_atendimento a "
            "LEFT JOIN persistencia_lancamento l ON l.atendimento_id = a.id "
            "LEFT JOIN persistencia_cancelamentolancamento c "
            "ON c.lancamento_id = l.id GROUP BY a.id"
        )
    )
    for atendimento_id, total_esperado in totais_esperados.items():
        total_persistido = totais_persistidos.get(atendimento_id)
        if total_persistido != total_esperado:
            raise InvarianteViolada(
                "Total incorreto no Atendimento "
                f"{atendimento_id}: esperado {total_esperado}, "
                f"persistido {total_persistido}."
            )

    chave_duplicada = conexao.execute(
        "SELECT chave FROM persistencia_registroidempotencia "
        "GROUP BY chave HAVING COUNT(*) > 1 LIMIT 1"
    ).fetchone()
    if chave_duplicada is not None:
        raise InvarianteViolada("Idempotencia gerou duplicacao.")

    comandas_disponiveis = comandas_que_devem_estar_disponiveis or set()
    if comandas_disponiveis:
        marcadores = ",".join("?" for _ in comandas_disponiveis)
        ainda_aberta = conexao.execute(
            "SELECT comanda_id FROM persistencia_atendimento "
            f"WHERE estado = 'ABERTO' AND comanda_id IN ({marcadores}) LIMIT 1",
            tuple(sorted(comandas_disponiveis)),
        ).fetchone()
        if ainda_aberta is not None:
            raise InvarianteViolada(
                f"Comanda fechada {ainda_aberta[0]} nao ficou disponivel."
            )

    integridade = conexao.execute("PRAGMA integrity_check").fetchone()
    if integridade != ("ok",):
        raise InvarianteViolada("Integridade SQLite invalida.")

    return {
        "resultado": "ok",
        "atendimentos_verificados": len(totais_esperados),
        "lancamentos_confirmados_verificados": len(lancamentos_confirmados),
        "integrity_check": "ok",
    }


def _resumir_medicoes(medicoes: _Medicoes) -> dict[str, object]:
    ordenados = sorted(medicoes.tempos_ms)
    if not ordenados:
        tempos = {"minimo": None, "mediana": None, "p95": None, "maximo": None}
    else:
        indice_p95 = max(0, math.ceil(len(ordenados) * 0.95) - 1)
        tempos = {
            "minimo": round(ordenados[0], 3),
            "mediana": round(median(ordenados), 3),
            "p95": round(ordenados[indice_p95], 3),
            "maximo": round(ordenados[-1], 3),
        }
    return {
        "quantidade": len(ordenados),
        "concluida": medicoes.concluida,
        "erro_dominio": medicoes.erro_dominio,
        "contencao_recuperada": medicoes.contencao_recuperada,
        "contencao_persistente": medicoes.contencao_persistente,
        "tempos_ms": tempos,
        "p95_em_relacao_a_meta_pratica": (
            None
            if tempos["p95"] is None
            else (
                "dentro_da_meta_pratica"
                if tempos["p95"] <= META_PRATICA_SEGUNDOS * 1_000
                else "acima_da_meta_pratica"
            )
        ),
    }
