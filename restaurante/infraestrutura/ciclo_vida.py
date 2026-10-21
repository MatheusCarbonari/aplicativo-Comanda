import atexit
import os
import sys

from .logging_estruturado import registrar_evento


_ciclo_operacional_ativo = False


def e_processo_operacional() -> bool:
    if os.environ.get("RESTAURANTE_PROCESSO_OPERACIONAL") == "1":
        return True
    if len(sys.argv) < 2 or sys.argv[1] != "runserver":
        return False
    if "--noreload" in sys.argv:
        return True
    return os.environ.get("RUN_MAIN") == "true"


def registrar_encerramento_aplicacao() -> None:
    global _ciclo_operacional_ativo
    if not _ciclo_operacional_ativo:
        return
    _ciclo_operacional_ativo = False
    registrar_evento("aplicacao_encerrada")


def iniciar_ciclo_vida_aplicacao() -> None:
    global _ciclo_operacional_ativo
    if not e_processo_operacional() or _ciclo_operacional_ativo:
        return
    _ciclo_operacional_ativo = True
    registrar_evento("aplicacao_iniciada")
    atexit.register(registrar_encerramento_aplicacao)
