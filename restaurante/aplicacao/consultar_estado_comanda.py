from dataclasses import dataclass
from enum import StrEnum

from restaurante.aplicacao.usuarios_operacionais import (
    PapelNaoPermitido,
    UsuarioOperacionalInvalido,
)
from restaurante.persistencia.models import (
    Atendimento,
    ComandaFisica,
    UsuarioOperacional,
)


class EstadoComanda(StrEnum):
    DISPONIVEL = "DISPONIVEL"
    EM_ATENDIMENTO = "EM_ATENDIMENTO"
    NAO_ENCONTRADA = "NAO_ENCONTRADA"


@dataclass(frozen=True)
class ResultadoConsultaComanda:
    estado: EstadoComanda
    identificador: str | None = None


def consultar_estado_comanda(
    usuario_operacional_id: object,
    identificador: str,
) -> ResultadoConsultaComanda:
    try:
        usuario_id = int(usuario_operacional_id)
    except (TypeError, ValueError) as erro:
        raise UsuarioOperacionalInvalido from erro

    usuario = UsuarioOperacional.objects.filter(pk=usuario_id).first()
    if usuario is None:
        raise UsuarioOperacionalInvalido
    if usuario.papel not in {
        UsuarioOperacional.Papel.GARCOM,
        UsuarioOperacional.Papel.CAIXA,
    }:
        raise PapelNaoPermitido

    comanda = ComandaFisica.objects.filter(identificador=identificador).first()
    if comanda is None:
        return ResultadoConsultaComanda(EstadoComanda.NAO_ENCONTRADA)

    atendimento_aberto = Atendimento.objects.filter(
        comanda=comanda,
        estado=Atendimento.Estado.ABERTO,
    ).exists()
    estado = (
        EstadoComanda.EM_ATENDIMENTO
        if atendimento_aberto
        else EstadoComanda.DISPONIVEL
    )
    return ResultadoConsultaComanda(estado, comanda.identificador)
