from django.db import models


class ComandaFisica(models.Model):
    identificador = models.CharField(max_length=20, unique=True)


class Produto(models.Model):
    nome = models.CharField(max_length=120, unique=True)
    preco_centavos = models.PositiveIntegerField()


class UsuarioOperacional(models.Model):
    class Papel(models.TextChoices):
        GARCOM = "GARCOM", "Garçom"
        CAIXA = "CAIXA", "Caixa"

    nome = models.CharField(max_length=120, unique=True)
    papel = models.CharField(max_length=10, choices=Papel.choices)


class Atendimento(models.Model):
    class Estado(models.TextChoices):
        ABERTO = "ABERTO", "Aberto"
        ENCERRADO = "ENCERRADO", "Encerrado"

    comanda = models.ForeignKey(
        ComandaFisica,
        on_delete=models.PROTECT,
        related_name="atendimentos",
    )
    estado = models.CharField(
        max_length=10,
        choices=Estado.choices,
        default=Estado.ABERTO,
    )

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["comanda"],
                condition=models.Q(estado="ABERTO"),
                name="atendimento_aberto_unico_por_comanda",
            )
        ]
