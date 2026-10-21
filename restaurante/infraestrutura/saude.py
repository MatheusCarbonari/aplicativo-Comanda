from django.db import DatabaseError, connection
from django.http import HttpRequest, JsonResponse
from django.views.decorators.http import require_GET

from .logging_estruturado import registrar_excecao


@require_GET
def verificar_saude(request: HttpRequest) -> JsonResponse:
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
            cursor.fetchone()
    except DatabaseError as erro:
        registrar_excecao(
            "falha_banco",
            erro,
            operation="verificar_saude",
        )
        return JsonResponse({"status": "indisponivel"}, status=503)

    return JsonResponse({"status": "ok"})
