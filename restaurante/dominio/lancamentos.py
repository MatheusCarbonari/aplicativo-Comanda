from collections.abc import Iterable
from dataclasses import dataclass


class QuantidadeInvalida(ValueError):
    pass


@dataclass(frozen=True)
class LancamentoParaConsolidacao:
    produto_id: int
    produto: str
    quantidade: int
    preco_unitario_centavos: int


@dataclass(frozen=True)
class LancamentoConsolidado:
    produto: str
    quantidade: int
    preco_unitario_centavos: int
    subtotal_centavos: int


def validar_quantidade(valor: object) -> int:
    if isinstance(valor, bool) or not isinstance(valor, (int, str)):
        raise QuantidadeInvalida
    try:
        quantidade = int(valor)
    except ValueError as erro:
        raise QuantidadeInvalida from erro
    if quantidade <= 0:
        raise QuantidadeInvalida
    return quantidade


def calcular_total_atendimento(
    lancamentos: Iterable[tuple[int, int]],
) -> int:
    return sum(
        quantidade * preco_unitario_centavos
        for quantidade, preco_unitario_centavos in lancamentos
    )


def consolidar_lancamentos(
    lancamentos: Iterable[LancamentoParaConsolidacao],
) -> tuple[LancamentoConsolidado, ...]:
    grupos: dict[tuple[int, int], LancamentoConsolidado] = {}
    for lancamento in lancamentos:
        chave = (lancamento.produto_id, lancamento.preco_unitario_centavos)
        quantidade = lancamento.quantidade
        if chave in grupos:
            quantidade += grupos[chave].quantidade
        grupos[chave] = LancamentoConsolidado(
            produto=lancamento.produto,
            quantidade=quantidade,
            preco_unitario_centavos=lancamento.preco_unitario_centavos,
            subtotal_centavos=(
                quantidade * lancamento.preco_unitario_centavos
            ),
        )
    return tuple(grupos.values())
