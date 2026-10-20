from datetime import UTC, datetime

from restaurante.aplicacao.idempotencia import calcular_hash_conteudo
from restaurante.persistencia.models import Atendimento


def calcular_revisao_fechamento(atendimento: Atendimento) -> str:
    """Representa o estado persistido relevante ao resumo de fechamento."""
    lancamentos = (
        atendimento.lancamentos.select_related(
            "produto",
            "autor",
            "cancelamento__autor",
        )
        .order_by("horario", "pk")
    )
    conteudo_lancamentos = []
    for lancamento in lancamentos:
        cancelamento = getattr(lancamento, "cancelamento", None)
        conteudo_lancamentos.append(
            {
                "id": lancamento.pk,
                "produto_id": lancamento.produto_id,
                "produto": lancamento.produto.nome,
                "quantidade": lancamento.quantidade,
                "preco_unitario_centavos": (
                    lancamento.preco_unitario_centavos
                ),
                "autor_id": lancamento.autor_id,
                "autor": lancamento.autor.nome,
                "horario": _normalizar_horario(lancamento.horario),
                "cancelamento": (
                    None
                    if cancelamento is None
                    else {
                        "id": cancelamento.pk,
                        "motivo": cancelamento.motivo,
                        "descricao": cancelamento.descricao,
                        "autor_id": cancelamento.autor_id,
                        "autor": cancelamento.autor.nome,
                        "horario": _normalizar_horario(
                            cancelamento.horario
                        ),
                    }
                ),
            }
        )

    return calcular_hash_conteudo(
        {
            "atendimento_id": atendimento.pk,
            "comanda_id": atendimento.comanda_id,
            "estado": atendimento.estado,
            "lancamentos": conteudo_lancamentos,
        }
    )


def _normalizar_horario(valor: datetime) -> str:
    return valor.astimezone(UTC).isoformat()
