from django.db import DatabaseError
from django.http import HttpRequest
from django.utils.deprecation import MiddlewareMixin

from .logging_estruturado import registrar_excecao


class RegistrarFalhasMiddleware(MiddlewareMixin):
    def process_exception(
        self,
        request: HttpRequest,
        exception: Exception,
    ) -> None:
        evento = (
            "falha_banco"
            if isinstance(exception, DatabaseError)
            else "erro_inesperado_http"
        )
        registrar_excecao(
            evento,
            exception,
            method=request.method,
            path=request.path,
        )
        return None
