import os
import shutil
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help = "Executa separadamente a validação de volume e concorrência."

    def add_arguments(self, parser):
        parser.add_argument("--lancamentos", type=int, default=10_000)
        parser.add_argument("--dispositivos", type=int, default=10)
        parser.add_argument("--semente", type=int, default=30)
        parser.add_argument("--arquivo-relatorio", type=Path)
        parser.add_argument("--modo-teste", action="store_true")

    def handle(self, *args, **options):
        lancamentos = options["lancamentos"]
        dispositivos = options["dispositivos"]
        modo_teste = options["modo_teste"] and settings.EM_EXECUCAO_TESTES
        if options["modo_teste"] and not settings.EM_EXECUCAO_TESTES:
            raise CommandError("--modo-teste só pode ser usado pela suíte de testes.")
        if lancamentos < 1 or (not modo_teste and lancamentos < 10_000):
            raise CommandError(
                "A execução normal exige pelo menos 10.000 Lançamentos."
            )
        if not 1 <= dispositivos <= 10:
            raise CommandError(
                "A quantidade de dispositivos deve ficar entre 1 e 10."
            )

        relatorio = options["arquivo_relatorio"] or self._caminho_relatorio()
        relatorio = Path(relatorio).resolve()
        relatorio.parent.mkdir(parents=True, exist_ok=True)
        settings.DIRETORIO_TESTES.mkdir(parents=True, exist_ok=True)

        diretorio = settings.DIRETORIO_TESTES / f"volume-cenario-{uuid4().hex}"
        diretorio.mkdir()
        try:
            ambiente = os.environ.copy()
            ambiente.update(
                {
                    "DJANGO_SETTINGS_MODULE": (
                        "restaurante.testes_suporte.configuracao_volume"
                    ),
                    "RESTAURANTE_VOLUME_BANCO": str(
                        diretorio / "cenario.sqlite3"
                    ),
                    "RESTAURANTE_VOLUME_LOG": str(diretorio / "cenario.jsonl"),
                }
            )
            comando = [
                sys.executable,
                "-m",
                "restaurante.testes_suporte.processo_volume_concorrencia",
                "--lancamentos",
                str(lancamentos),
                "--dispositivos",
                str(dispositivos),
                "--semente",
                str(options["semente"]),
                "--arquivo-relatorio",
                str(relatorio),
            ]
            try:
                resultado = subprocess.run(
                    comando,
                    cwd=settings.BASE_DIR,
                    env=ambiente,
                    capture_output=True,
                    text=True,
                    encoding="utf-8",
                    timeout=300,
                )
            except subprocess.TimeoutExpired as erro:
                raise CommandError(
                    "A validação excedeu o limite de 300 segundos."
                ) from erro
            if resultado.returncode != 0:
                diagnostico = resultado.stderr.strip() or resultado.stdout.strip()
                raise CommandError(
                    "A validação de volume e concorrência falhou: "
                    f"{diagnostico}"
                )
        finally:
            shutil.rmtree(diretorio)

        self.stdout.write(resultado.stdout.rstrip())
        self.stdout.write(self.style.SUCCESS(f"Relatório criado em {relatorio}"))

    @staticmethod
    def _caminho_relatorio() -> Path:
        instante = datetime.now(UTC).strftime("%Y%m%dT%H%M%S%fZ")
        return settings.BASE_DIR / ".local" / "relatorios" / (
            f"volume-concorrencia-{instante}.json"
        )

