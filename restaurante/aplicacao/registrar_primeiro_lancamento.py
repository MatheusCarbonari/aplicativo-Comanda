from dataclasses import dataclass

from django.db import IntegrityError, transaction

from restaurante.aplicacao.usuarios_operacionais import (
    buscar_garcom,
)
from restaurante.dominio.lancamentos import (
    QuantidadeInvalida,
    validar_quantidade,
)
from restaurante.persistencia.models import (
    Atendimento,
    ComandaFisica,
    Lancamento,
    Produto,
)


class ComandaNaoEncontrada(Exception):
    pass


class ProdutoNaoEncontrado(Exception):
    pass


class ComandaEmAtendimento(Exception):
    pass


@dataclass(frozen=True)
class ResultadoPrimeiroLancamento:
    atendimento_id: int
    lancamento_id: int
    comanda: str
    produto: str
    quantidade: int
    preco_unitario_centavos: int


def registrar_primeiro_lancamento(
    usuario_operacional_id: object,
    identificador_comanda: str,
    produto_id: object,
    quantidade: object,
) -> ResultadoPrimeiroLancamento:
    usuario = buscar_garcom(usuario_operacional_id)
    comanda = ComandaFisica.objects.filter(
        identificador=identificador_comanda
    ).first()
    if comanda is None:
        raise ComandaNaoEncontrada

    try:
        chave_produto = int(produto_id)
    except (TypeError, ValueError) as erro:
        raise ProdutoNaoEncontrado from erro
    produto = Produto.objects.filter(pk=chave_produto).first()
    if produto is None:
        raise ProdutoNaoEncontrado

    quantidade_validada = validar_quantidade(quantidade)
    if Atendimento.objects.filter(
        comanda=comanda,
        estado=Atendimento.Estado.ABERTO,
    ).exists():
        raise ComandaEmAtendimento

    with transaction.atomic():
        try:
            atendimento = Atendimento.objects.create(comanda=comanda)
        except IntegrityError as erro:
            raise ComandaEmAtendimento from erro
        lancamento = Lancamento.objects.create(
            atendimento=atendimento,
            produto=produto,
            quantidade=quantidade_validada,
            preco_unitario_centavos=produto.preco_centavos,
            autor=usuario,
        )

    return ResultadoPrimeiroLancamento(
        atendimento_id=atendimento.pk,
        lancamento_id=lancamento.pk,
        comanda=comanda.identificador,
        produto=produto.nome,
        quantidade=lancamento.quantidade,
        preco_unitario_centavos=lancamento.preco_unitario_centavos,
    )
