from dataclasses import asdict, dataclass

from django.db import IntegrityError, transaction

from restaurante.aplicacao.contencao_persistencia import (
    executar_com_retry_de_contencao,
)
from restaurante.aplicacao.idempotencia import executar_idempotente
from restaurante.aplicacao.usuarios_operacionais import (
    buscar_garcom,
    normalizar_identificador_usuario,
)
from restaurante.dominio.lancamentos import calcular_total_atendimento
from restaurante.persistencia.conflitos_sqlite import (
    e_conflito_de_cancelamento,
)
from restaurante.persistencia.models import (
    Atendimento,
    CancelamentoLancamento,
    Lancamento,
)


class LancamentoNaoEncontrado(Exception):
    pass


class AtendimentoEncerrado(Exception):
    pass


class LancamentoJaCancelado(Exception):
    pass


class MotivoCancelamentoInvalido(ValueError):
    pass


class DescricaoCancelamentoInvalida(ValueError):
    pass


OPERACAO_CANCELAR_LANCAMENTO = "CANCELAR_LANCAMENTO"


@dataclass(frozen=True)
class ResultadoCancelamentoLancamento:
    cancelamento_id: int
    lancamento_id: int
    atendimento_id: int
    motivo: str
    descricao: str
    autor: str
    horario: str
    total_centavos: int


def cancelar_lancamento(
    usuario_operacional_id: object,
    lancamento_id: object,
    motivo: object,
    descricao: object,
    chave_idempotencia: object,
) -> ResultadoCancelamentoLancamento:
    chave_usuario = normalizar_identificador_usuario(usuario_operacional_id)
    chave_lancamento = _normalizar_lancamento(lancamento_id)
    motivo_validado = _validar_motivo(motivo)
    descricao_validada = _validar_descricao(motivo_validado, descricao)
    conteudo = {
        "usuario_operacional_id": chave_usuario,
        "lancamento_id": chave_lancamento,
        "motivo": motivo_validado,
        "descricao": descricao_validada,
    }

    def executar() -> dict[str, object]:
        usuario = buscar_garcom(chave_usuario)
        lancamento = (
            Lancamento.objects.select_related("atendimento")
            .filter(pk=chave_lancamento)
            .first()
        )
        if lancamento is None:
            raise LancamentoNaoEncontrado
        if lancamento.atendimento.estado != Atendimento.Estado.ABERTO:
            raise AtendimentoEncerrado
        if CancelamentoLancamento.objects.filter(
            lancamento=lancamento
        ).exists():
            raise LancamentoJaCancelado

        try:
            with transaction.atomic():
                cancelamento = CancelamentoLancamento.objects.create(
                    lancamento=lancamento,
                    motivo=motivo_validado,
                    descricao=descricao_validada,
                    autor=usuario,
                )
        except IntegrityError as erro:
            if not e_conflito_de_cancelamento(erro):
                raise
            raise LancamentoJaCancelado from erro
        total_centavos = calcular_total_atendimento(
            lancamento.atendimento.lancamentos.validos().values_list(
                "quantidade", "preco_unitario_centavos"
            )
        )
        return asdict(
            ResultadoCancelamentoLancamento(
                cancelamento_id=cancelamento.pk,
                lancamento_id=lancamento.pk,
                atendimento_id=lancamento.atendimento_id,
                motivo=cancelamento.motivo,
                descricao=cancelamento.descricao,
                autor=usuario.nome,
                horario=cancelamento.horario.isoformat(),
                total_centavos=total_centavos,
            )
        )

    resultado = executar_com_retry_de_contencao(
        lambda: executar_idempotente(
            chave=chave_idempotencia,
            operacao=OPERACAO_CANCELAR_LANCAMENTO,
            conteudo=conteudo,
            executar=executar,
        )
    )
    return ResultadoCancelamentoLancamento(**resultado)


def _normalizar_lancamento(lancamento_id: object) -> int:
    try:
        return int(lancamento_id)
    except (TypeError, ValueError) as erro:
        raise LancamentoNaoEncontrado from erro


def _validar_motivo(motivo: object) -> str:
    if motivo not in CancelamentoLancamento.Motivo.values:
        raise MotivoCancelamentoInvalido
    return str(motivo)


def _validar_descricao(motivo: str, descricao: object) -> str:
    if descricao is None:
        descricao_validada = ""
    elif isinstance(descricao, str):
        descricao_validada = descricao.strip()
    else:
        raise DescricaoCancelamentoInvalida
    if (
        motivo == CancelamentoLancamento.Motivo.OUTRO
        and not descricao_validada
    ):
        raise DescricaoCancelamentoInvalida
    return descricao_validada
