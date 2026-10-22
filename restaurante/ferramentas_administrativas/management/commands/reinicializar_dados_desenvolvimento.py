from uuid import uuid4

from django.conf import settings
from django.contrib.sessions.models import Session
from django.core.management import call_command
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from restaurante.infraestrutura.logging_estruturado import (
    registrar_evento,
    registrar_excecao,
)
from restaurante.persistencia.models import (
    Atendimento,
    CancelamentoLancamento,
    ComandaFisica,
    Lancamento,
    Produto,
    RegistroIdempotencia,
    UsuarioOperacional,
)


class Command(BaseCommand):
    help = "Recria com segurança a massa inicial exclusiva de desenvolvimento."

    def handle(self, *args, **options):
        reinicializacao_id = uuid4().hex
        if settings.DEBUG is not True:
            erro = CommandError(
                "Este comando é exclusivo do ambiente de desenvolvimento "
                "com DEBUG=True."
            )
            registrar_excecao(
                "reinicializacao_desenvolvimento_falhou",
                erro,
                reinicializacao_id=reinicializacao_id,
                etapa="ambiente",
            )
            raise erro

        registrar_evento(
            "reinicializacao_desenvolvimento_solicitada",
            reinicializacao_id=reinicializacao_id,
        )
        self.stdout.write(
            "ATENÇÃO: esta operação removerá Atendimentos, Lançamentos, "
            "Cancelamentos, registros de idempotência, sessões, Comandas, "
            "Produtos e Usuários operacionais. A massa inicial de "
            "desenvolvimento será recriada depois de um backup válido."
        )
        confirmacao = input("Digite REINICIALIZAR para continuar: ")
        if confirmacao != "REINICIALIZAR":
            erro = CommandError(
                "Confirmação recusada; nenhum dado foi alterado."
            )
            registrar_excecao(
                "reinicializacao_desenvolvimento_falhou",
                erro,
                reinicializacao_id=reinicializacao_id,
                etapa="confirmacao",
            )
            raise erro

        registrar_evento(
            "reinicializacao_desenvolvimento_confirmada",
            reinicializacao_id=reinicializacao_id,
        )
        registrar_evento(
            "reinicializacao_backup_iniciado",
            reinicializacao_id=reinicializacao_id,
        )
        try:
            call_command(
                "criar_backup",
                stdout=self.stdout,
                stderr=self.stderr,
            )
        except Exception as erro:
            registrar_excecao(
                "reinicializacao_desenvolvimento_falhou",
                erro,
                reinicializacao_id=reinicializacao_id,
                etapa="backup",
            )
            raise CommandError(
                "Falha no backup obrigatório; nenhum dado foi removido."
            ) from erro

        registrar_evento(
            "reinicializacao_backup_confirmado",
            reinicializacao_id=reinicializacao_id,
        )
        registrar_evento(
            "reinicializacao_limpeza_iniciada",
            reinicializacao_id=reinicializacao_id,
        )
        try:
            with transaction.atomic():
                CancelamentoLancamento.objects.all().delete()
                Lancamento.objects.all().delete()
                Atendimento.objects.all().delete()
                RegistroIdempotencia.objects.all().delete()
                Session.objects.all().delete()
                Produto.objects.all().delete()
                UsuarioOperacional.objects.all().delete()
                ComandaFisica.objects.all().delete()
                call_command(
                    "carregar_dados_iniciais",
                    stdout=self.stdout,
                    stderr=self.stderr,
                )
                transaction.on_commit(
                    lambda: registrar_evento(
                        "reinicializacao_massa_inicial_recriada",
                        reinicializacao_id=reinicializacao_id,
                    )
                )
                transaction.on_commit(
                    lambda: registrar_evento(
                        "reinicializacao_desenvolvimento_concluida",
                        reinicializacao_id=reinicializacao_id,
                    )
                )
        except Exception as erro:
            registrar_excecao(
                "reinicializacao_desenvolvimento_falhou",
                erro,
                reinicializacao_id=reinicializacao_id,
                etapa="recriacao",
            )
            raise CommandError(
                "Falha ao recriar a massa inicial; todas as alterações foram "
                "revertidas."
            ) from erro

        self.stdout.write(
            self.style.SUCCESS(
                "Reinicialização concluída com backup confirmado e massa "
                "inicial recriada."
            )
        )
