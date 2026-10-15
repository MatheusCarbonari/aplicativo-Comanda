from dataclasses import asdict, dataclass

from restaurante.aplicacao.idempotencia import executar_idempotente
from restaurante.aplicacao.registrar_primeiro_lancamento import (
    ComandaNaoEncontrada,
    ProdutoNaoEncontrado,
)
from restaurante.aplicacao.usuarios_operacionais import (
    buscar_garcom,
    normalizar_identificador_usuario,
)
from restaurante.dominio.lancamentos import (
    calcular_total_atendimento,
    validar_quantidade,
)
from restaurante.persistencia.models import (
    Atendimento,
    ComandaFisica,
    Lancamento,
    Produto,
)


class AtendimentoAbertoNaoEncontrado(Exception):
    pass


OPERACAO_REGISTRAR_LANCAMENTO_ADICIONAL = (
    "REGISTRAR_LANCAMENTO_ADICIONAL"
)


@dataclass(frozen=True)
class ResultadoLancamentoAdicional:
    atendimento_id: int
    lancamento_id: int
    comanda: str
    produto: str
    quantidade: int
    preco_unitario_centavos: int
    autor: str
    total_centavos: int


def registrar_lancamento_adicional(
    usuario_operacional_id: object,
    identificador_comanda: str,
    produto_id: object,
    quantidade: object,
    chave_idempotencia: object,
) -> ResultadoLancamentoAdicional:
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
        atendimento = Atendimento.objects.filter(
            comanda=comanda,
            estado=Atendimento.Estado.ABERTO,
        ).first()
        if atendimento is None:
            raise AtendimentoAbertoNaoEncontrado

        lancamento = Lancamento.objects.create(
            atendimento=atendimento,
            produto=produto,
            quantidade=quantidade_validada,
            preco_unitario_centavos=produto.preco_centavos,
            autor=usuario,
        )
        total_centavos = calcular_total_atendimento(
            atendimento.lancamentos.values_list(
                "quantidade",
                "preco_unitario_centavos",
            )
        )
        return asdict(
            ResultadoLancamentoAdicional(
                atendimento_id=atendimento.pk,
                lancamento_id=lancamento.pk,
                comanda=comanda.identificador,
                produto=produto.nome,
                quantidade=lancamento.quantidade,
                preco_unitario_centavos=lancamento.preco_unitario_centavos,
                autor=usuario.nome,
                total_centavos=total_centavos,
            )
        )

    resultado = executar_idempotente(
        chave=chave_idempotencia,
        operacao=OPERACAO_REGISTRAR_LANCAMENTO_ADICIONAL,
        conteudo=conteudo,
        executar=executar,
    )
    return ResultadoLancamentoAdicional(**resultado)
