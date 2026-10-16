from dataclasses import asdict, dataclass

from django.utils import timezone

from restaurante.aplicacao.contencao_persistencia import (
    executar_com_retry_de_contencao,
)
from restaurante.aplicacao.idempotencia import executar_idempotente
from restaurante.aplicacao.usuarios_operacionais import (
    buscar_caixa,
    normalizar_identificador_usuario,
)
from restaurante.persistencia.models import Atendimento


OPERACAO_FECHAR_ATENDIMENTO = "FECHAR_ATENDIMENTO"


class AtendimentoNaoEncontrado(Exception):
    pass


class AtendimentoJaEncerrado(Exception):
    pass


@dataclass(frozen=True)
class ResultadoFechamentoAtendimento:
    atendimento_id: int
    comanda_identificador: str
    estado: str
    fechado_por: str
    fechado_em: str


def fechar_atendimento(
    usuario_operacional_id: object,
    atendimento_id: object,
    chave_idempotencia: object,
) -> ResultadoFechamentoAtendimento:
    chave_usuario = normalizar_identificador_usuario(usuario_operacional_id)
    chave_atendimento = _normalizar_atendimento(atendimento_id)
    conteudo = {
        "usuario_operacional_id": chave_usuario,
        "atendimento_id": chave_atendimento,
    }

    def executar() -> dict[str, object]:
        caixa = buscar_caixa(chave_usuario)
        atendimento = (
            Atendimento.objects.select_related("comanda")
            .filter(pk=chave_atendimento)
            .first()
        )
        if atendimento is None:
            raise AtendimentoNaoEncontrado
        if atendimento.estado != Atendimento.Estado.ABERTO:
            raise AtendimentoJaEncerrado

        fechado_em = timezone.now()
        atualizados = Atendimento.objects.filter(
            pk=atendimento.pk,
            estado=Atendimento.Estado.ABERTO,
        ).update(
            estado=Atendimento.Estado.ENCERRADO,
            fechado_por=caixa,
            fechado_em=fechado_em,
        )
        if atualizados != 1:
            raise AtendimentoJaEncerrado

        return asdict(
            ResultadoFechamentoAtendimento(
                atendimento_id=atendimento.pk,
                comanda_identificador=atendimento.comanda.identificador,
                estado=Atendimento.Estado.ENCERRADO,
                fechado_por=caixa.nome,
                fechado_em=fechado_em.isoformat(),
            )
        )

    resultado = executar_com_retry_de_contencao(
        lambda: executar_idempotente(
            chave=chave_idempotencia,
            operacao=OPERACAO_FECHAR_ATENDIMENTO,
            conteudo=conteudo,
            executar=executar,
        )
    )
    return ResultadoFechamentoAtendimento(**resultado)


def _normalizar_atendimento(atendimento_id: object) -> int:
    try:
        return int(atendimento_id)
    except (TypeError, ValueError) as erro:
        raise AtendimentoNaoEncontrado from erro
