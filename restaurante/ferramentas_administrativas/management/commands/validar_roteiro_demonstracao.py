import json
import os
import re
import shutil
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help = "Executa separadamente o roteiro integrado de demonstração."

    def add_arguments(self, parser):
        parser.add_argument("--arquivo-relatorio", type=Path)
        parser.add_argument("--modo-teste", action="store_true")

    def handle(self, *args, **options):
        modo_teste = options["modo_teste"] and settings.EM_EXECUCAO_TESTES
        if options["modo_teste"] and not settings.EM_EXECUCAO_TESTES:
            raise CommandError("--modo-teste só pode ser usado pela suíte de testes.")

        relatorio = Path(
            options["arquivo_relatorio"] or self._caminho_relatorio()
        ).resolve()
        relatorio.parent.mkdir(parents=True, exist_ok=True)
        settings.DIRETORIO_TESTES.mkdir(parents=True, exist_ok=True)
        diretorio = settings.DIRETORIO_TESTES / f"roteiro-cenario-{uuid4().hex}"
        diretorio.mkdir()
        try:
            ambiente = os.environ.copy()
            ambiente.update(
                {
                    "DJANGO_SETTINGS_MODULE": (
                        "restaurante.testes_suporte.configuracao_roteiro"
                    ),
                    "RESTAURANTE_ROTEIRO_BANCO": str(
                        diretorio / "cenario.sqlite3"
                    ),
                    "RESTAURANTE_ROTEIRO_LOG": str(diretorio / "cenario.jsonl"),
                    "PYTHONIOENCODING": "utf-8",
                    "PYTHONUTF8": "1",
                }
            )
            comando = [
                sys.executable,
                "-m",
                "restaurante.testes_suporte.processo_roteiro_demonstracao",
                "--arquivo-relatorio",
                str(relatorio),
            ]
            if modo_teste:
                comando.append("--modo-teste")
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
                    "O roteiro excedeu o limite de 300 segundos."
                ) from erro
            if resultado.returncode != 0:
                diagnostico = (resultado.stderr or "").strip() or (
                    resultado.stdout or ""
                ).strip()
                raise CommandError(f"O roteiro de demonstração falhou: {diagnostico}")

            if modo_teste:
                self._registrar_validacoes_nao_executadas(relatorio)
            else:
                self._coordenar_validacoes_existentes(relatorio, ambiente)
        finally:
            shutil.rmtree(diretorio)

        self.stdout.write(resultado.stdout.rstrip())
        self.stdout.write(self.style.SUCCESS(f"Relatório criado em {relatorio}"))

    def _registrar_validacoes_nao_executadas(self, relatorio: Path) -> None:
        conteudo = json.loads(relatorio.read_text(encoding="utf-8"))
        conteudo["comunicacao"] = {
            "resultado": "não executada no modo de teste"
        }
        conteudo["operacoes_administrativas"] = {
            "resultado": "não executadas no modo de teste"
        }
        relatorio.write_text(
            json.dumps(conteudo, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def _coordenar_validacoes_existentes(
        self, relatorio: Path, ambiente: dict[str, str]
    ) -> None:
        ambiente = ambiente.copy()
        ambiente.pop("RESTAURANTE_ROTEIRO_BANCO", None)
        ambiente.pop("RESTAURANTE_ROTEIRO_LOG", None)
        ambiente["DJANGO_SETTINGS_MODULE"] = (
            "restaurante.infraestrutura.configuracao"
        )
        conteudo = json.loads(relatorio.read_text(encoding="utf-8"))
        verificacoes = {
            "backup_seguro": (
                "restaurante.ferramentas_administrativas.test_backup_sqlite"
            ),
            "backup_diario": (
                "restaurante.ferramentas_administrativas.test_backup_diario"
            ),
            "backup_pre_migracao": (
                "restaurante.ferramentas_administrativas.test_migracao_com_backup"
            ),
            "restauracao": (
                "restaurante.ferramentas_administrativas.test_restauracao_backup"
            ),
            "reinicializacao": (
                "restaurante.ferramentas_administrativas."
                "test_reinicializacao_desenvolvimento"
            ),
            "durabilidade": (
                "restaurante.aplicacao.test_durabilidade_encerramento_abrupto"
            ),
        }
        resultados_administrativos = {}
        try:
            comunicacao = self._executar_etapa(
                [
                    "node",
                    "--test",
                    "restaurante/interface_web/js_tests/"
                    "atualizacao_periodica.test.mjs",
                ],
                ambiente,
                "comunicação",
            )
            conteudo["comunicacao"] = {
                "resultado": "aprovado",
                "suite_reutilizada": (
                    "atualizacao_periodica.test.mjs (Ticket 21)"
                ),
                "cenarios": [
                    "perda de comunicação preserva o último estado",
                    "envio sem resposta produz resultado incerto sem retry",
                    "recuperação consulta o estado persistido",
                    "não existe fila offline",
                ],
                **comunicacao,
            }
            for nome, modulo in verificacoes.items():
                resultados_administrativos[nome] = {
                    "resultado": "aprovado",
                    "suite_publica": modulo,
                    **self._executar_etapa(
                        [
                            sys.executable,
                            "manage.py",
                            "test",
                            modulo,
                            "--verbosity=1",
                        ],
                        ambiente,
                        nome,
                    ),
                }
            conteudo["operacoes_administrativas"] = {
                "resultado": "aprovado",
                "verificacoes": resultados_administrativos,
            }
        except CommandError as erro:
            conteudo["falhas"].append(str(erro))
            relatorio.write_text(
                json.dumps(conteudo, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            raise
        relatorio.write_text(
            json.dumps(conteudo, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    @staticmethod
    def _executar_etapa(
        comando: list[str], ambiente: dict[str, str], nome: str
    ) -> dict[str, object]:
        try:
            resultado = subprocess.run(
                comando,
                cwd=settings.BASE_DIR,
                env=ambiente,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=300,
            )
        except subprocess.TimeoutExpired as erro:
            raise CommandError(
                f"A etapa obrigatória {nome} excedeu 300 segundos."
            ) from erro
        if resultado.returncode != 0:
            diagnostico = (resultado.stderr or resultado.stdout).strip()
            raise CommandError(
                f"A etapa obrigatória {nome} falhou: {diagnostico}"
            )
        saida = "\n".join((resultado.stdout, resultado.stderr))
        quantidade = None
        correspondencia = re.search(
            r"(?:Ran|tests?)\s+(\d+)", saida, re.IGNORECASE
        )
        if correspondencia:
            quantidade = int(correspondencia.group(1))
        return {"testes": quantidade}

    @staticmethod
    def _caminho_relatorio() -> Path:
        instante = datetime.now(UTC).strftime("%Y%m%dT%H%M%S%fZ")
        return settings.BASE_DIR / ".local" / "relatorios" / (
            f"roteiro-demonstracao-{instante}.json"
        )
