import hashlib
import json
from collections.abc import Callable, Mapping
from typing import TypeAlias

from django.db import IntegrityError, transaction

from restaurante.persistencia.models import RegistroIdempotencia


ResultadoIdempotente: TypeAlias = dict[str, object]


class ConflitoIdempotencia(Exception):
    pass


class ChaveIdempotenciaInvalida(ValueError):
    pass


def calcular_hash_conteudo(conteudo: Mapping[str, object]) -> str:
    representacao = json.dumps(
        conteudo,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    )
    return hashlib.sha256(representacao.encode("utf-8")).hexdigest()


def executar_idempotente(
    *,
    chave: object,
    operacao: str,
    conteudo: Mapping[str, object],
    executar: Callable[[], ResultadoIdempotente],
) -> ResultadoIdempotente:
    chave_validada = _validar_chave(chave)
    hash_conteudo = calcular_hash_conteudo(conteudo)
    existente = RegistroIdempotencia.objects.filter(
        chave=chave_validada
    ).first()
    if existente is not None:
        return _resultado_compativel(existente, operacao, hash_conteudo)

    try:
        with transaction.atomic():
            registro = RegistroIdempotencia.objects.create(
                chave=chave_validada,
                operacao=operacao,
                hash_conteudo=hash_conteudo,
                resultado={},
            )
            resultado = executar()
            registro.resultado = resultado
            registro.save(update_fields=["resultado"])
            return resultado
    except IntegrityError as erro:
        if not _e_conflito_de_chave(erro):
            raise

    vencedor = RegistroIdempotencia.objects.filter(
        chave=chave_validada
    ).first()
    if vencedor is None:
        raise RuntimeError(
            "A chave idempotente concorrente não foi encontrada após o rollback."
        )
    return _resultado_compativel(vencedor, operacao, hash_conteudo)


def _validar_chave(chave: object) -> str:
    if not isinstance(chave, str) or not chave.strip() or len(chave) > 255:
        raise ChaveIdempotenciaInvalida
    return chave


def _resultado_compativel(
    registro: RegistroIdempotencia,
    operacao: str,
    hash_conteudo: str,
) -> ResultadoIdempotente:
    if registro.operacao != operacao or registro.hash_conteudo != hash_conteudo:
        raise ConflitoIdempotencia
    return registro.resultado


def _e_conflito_de_chave(erro: IntegrityError) -> bool:
    mensagem = str(erro)
    return (
        "UNIQUE constraint failed" in mensagem
        and "persistencia_registroidempotencia.chave" in mensagem
    )
