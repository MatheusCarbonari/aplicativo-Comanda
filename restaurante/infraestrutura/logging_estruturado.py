import json
import logging
import traceback
from datetime import UTC, datetime


LOGGER_APLICACAO = logging.getLogger("restaurante")


class FormatadorJSON(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        registro = dict(getattr(record, "contexto_tecnico", {}))
        registro.update({
            "timestamp": datetime.fromtimestamp(
                record.created,
                tz=UTC,
            ).isoformat(),
            "level": record.levelname,
            "event": getattr(record, "evento", record.getMessage()),
        })
        if record.exc_info is not None:
            registro["traceback"] = "".join(
                traceback.format_tb(record.exc_info[2])
            ).strip()
        return json.dumps(
            registro,
            ensure_ascii=False,
            separators=(",", ":"),
        )


def registrar_evento(
    evento: str,
    *,
    nivel: int = logging.INFO,
    logger: logging.Logger = LOGGER_APLICACAO,
    exc_info: tuple[type[BaseException], BaseException, object] | None = None,
    **contexto_tecnico: object,
) -> None:
    try:
        logger.log(
            nivel,
            evento,
            exc_info=exc_info,
            extra={
                "evento": evento,
                "contexto_tecnico": contexto_tecnico,
            },
        )
    except Exception:
        return


def registrar_excecao(
    evento: str,
    erro: Exception,
    *,
    logger: logging.Logger = LOGGER_APLICACAO,
    **contexto_tecnico: object,
) -> None:
    registrar_evento(
        evento,
        nivel=logging.ERROR,
        logger=logger,
        exc_info=(type(erro), erro, erro.__traceback__),
        error_type=type(erro).__name__,
        **contexto_tecnico,
    )
