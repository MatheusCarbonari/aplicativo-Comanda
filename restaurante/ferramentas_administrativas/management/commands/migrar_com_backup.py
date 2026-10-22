from uuid import uuid4

from django.core.management import call_command
from django.core.management.base import CommandError
from django.core.management.commands.migrate import Command as MigrateCommand

from restaurante.infraestrutura.logging_estruturado import (
    registrar_evento,
    registrar_excecao,
)


class Command(MigrateCommand):
    help = "Cria um backup seguro antes de aplicar migrations."

    def handle(self, *args, **options):
        execucao_id = uuid4().hex
        registrar_evento(
            "migracao_com_backup_iniciada",
            execucao_id=execucao_id,
        )
        registrar_evento(
            "backup_pre_migracao_iniciado",
            execucao_id=execucao_id,
        )
        try:
            call_command(
                "criar_backup",
                finalidade="pre-migracao",
                stdout=self.stdout,
                stderr=self.stderr,
            )
        except Exception as erro:
            registrar_excecao(
                "backup_pre_migracao_falhou",
                erro,
                execucao_id=execucao_id,
            )
            raise CommandError(
                "Falha no backup pré-migração; nenhuma migration foi iniciada."
            ) from erro

        registrar_evento(
            "backup_pre_migracao_confirmado",
            execucao_id=execucao_id,
        )
        registrar_evento(
            "migracao_iniciada",
            execucao_id=execucao_id,
        )
        try:
            resultado = super().handle(*args, **options)
        except Exception as erro:
            registrar_excecao(
                "migracao_falhou",
                erro,
                execucao_id=execucao_id,
            )
            raise CommandError(
                "O backup pré-migração foi confirmado, mas a migration falhou."
            ) from erro

        registrar_evento(
            "migracao_concluida",
            execucao_id=execucao_id,
        )
        self.stdout.write(
            self.style.SUCCESS(
                "Backup pré-migração confirmado e migrations concluídas."
            )
        )
        return resultado
