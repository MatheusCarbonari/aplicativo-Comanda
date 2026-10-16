from dataclasses import asdict, dataclass

from django.db import IntegrityError, OperationalError, transaction

from restaurante.aplicacao.idempotencia import executar_idempotente
from restaurante.aplicacao.usuarios_operacionais import (
    buscar_garcom,
    normalizar_identificador_usuario,
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
from restaurante.persistencia.conflitos_sqlite import (
    e_conflito_de_abertura,
    e_contencao_transitoria,
)


class ComandaNaoEncontrada(Exception):
    pass


class ProdutoNaoEncontrado(Exception):
    pass


class PersistenciaTemporariamenteIndisponivel(Exception):
    pass


OPERACAO_REGISTRAR_PRIMEIRO_LANCAMENTO = "REGISTRAR_PRIMEIRO_LANCAMENTO"
MAXIMO_TENTATIVAS_CONTENCAO = 2


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
    chave_idempotencia: object,
) -> ResultadoPrimeiroLancamento:
    chave_usuario = normalizar_identificador_usuario(usuario_operacional_id)
    try:
        chave_produto = int(produto_id)
    except (TypeError, ValueError) as erro:
        raise ProdutoNaoEncontrado from erro
    quantidade_validada = validar_quantidade(quantidade)
    conteudo = {
        "usuario_operacional_id": chave_usuario,
        "comanda": identificador_comanda,
        "produto_id": chave_produto,
        "quantidade": quantidade_validada,
    }
    def executar() -> dict[str, object]:
        usuario = buscar_garcom(chave_usuario)
        comanda = ComandaFisica.objects.filter(
            identificador=identificador_comanda
        ).first()
        if comanda is None:
            raise ComandaNaoEncontrada
        produto = Produto.objects.filter(pk=chave_produto).first()
        if produto is None:
            raise ProdutoNaoEncontrado
        try:
            with transaction.atomic():
                atendimento = Atendimento.objects.create(comanda=comanda)
        except IntegrityError as erro:
            if not e_conflito_de_abertura(erro):
                raise
            atendimento = Atendimento.objects.filter(
                comanda=comanda,
                estado=Atendimento.Estado.ABERTO,
            ).first()
            if atendimento is None:
                raise
        lancamento = Lancamento.objects.create(
            atendimento=atendimento,
            produto=produto,
            quantidade=quantidade_validada,
            preco_unitario_centavos=produto.preco_centavos,
            autor=usuario,
        )
        return asdict(
            ResultadoPrimeiroLancamento(
                atendimento_id=atendimento.pk,
                lancamento_id=lancamento.pk,
                comanda=comanda.identificador,
                produto=produto.nome,
                quantidade=lancamento.quantidade,
                preco_unitario_centavos=lancamento.preco_unitario_centavos,
            )
        )

    for tentativa in range(MAXIMO_TENTATIVAS_CONTENCAO):
        try:
            resultado = executar_idempotente(
                chave=chave_idempotencia,
                operacao=OPERACAO_REGISTRAR_PRIMEIRO_LANCAMENTO,
                conteudo=conteudo,
                executar=executar,
            )
            break
        except OperationalError as erro:
            if not e_contencao_transitoria(erro):
                raise
            if tentativa + 1 == MAXIMO_TENTATIVAS_CONTENCAO:
                raise PersistenciaTemporariamenteIndisponivel from erro
    return ResultadoPrimeiroLancamento(**resultado)
