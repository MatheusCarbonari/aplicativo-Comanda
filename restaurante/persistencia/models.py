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
