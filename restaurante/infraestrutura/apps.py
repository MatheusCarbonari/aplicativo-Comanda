from django.apps import AppConfig

from .ciclo_vida import iniciar_ciclo_vida_aplicacao


class InfraestruturaConfig(AppConfig):
    name = "restaurante.infraestrutura"
    verbose_name = "Infraestrutura"

    def ready(self) -> None:
        iniciar_ciclo_vida_aplicacao()
