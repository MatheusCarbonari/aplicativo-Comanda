from django.core.management.base import BaseCommand
from django.db import transaction

from restaurante.persistencia.models import ComandaFisica, Produto, UsuarioOperacional


COMANDAS_INICIAIS = tuple(f"{numero:03d}" for numero in range(1, 21))

USUARIOS_INICIAIS = (
    ("Garçom 1", UsuarioOperacional.Papel.GARCOM),
    ("Garçom 2", UsuarioOperacional.Papel.GARCOM),
    ("Caixa 1", UsuarioOperacional.Papel.CAIXA),
)

PRODUTOS_INICIAIS = (
    ("Água mineral", 500),
    ("Refrigerante", 750),
    ("Suco", 900),
    ("Cerveja", 1200),
    ("Batata frita", 2000),
    ("Hambúrguer", 2800),
    ("Pizza", 4500),
    ("Salada", 1800),
    ("Sobremesa", 1500),
    ("Café", 600),
)


class Command(BaseCommand):
    help = "Cria somente os dados de demonstração que ainda não existem."

    @transaction.atomic
    def handle(self, *args, **options):
        comandas_criadas = 0
        usuarios_criados = 0
        produtos_criados = 0

        for identificador in COMANDAS_INICIAIS:
            _, criado = ComandaFisica.objects.get_or_create(
                identificador=identificador,
            )
            comandas_criadas += int(criado)

        for nome, papel in USUARIOS_INICIAIS:
            _, criado = UsuarioOperacional.objects.get_or_create(
                nome=nome,
                defaults={"papel": papel},
            )
            usuarios_criados += int(criado)

        for nome, preco_centavos in PRODUTOS_INICIAIS:
            _, criado = Produto.objects.get_or_create(
                nome=nome,
                defaults={"preco_centavos": preco_centavos},
            )
            produtos_criados += int(criado)

        self.stdout.write(
            self.style.SUCCESS(
                "Carga inicial concluída: "
                f"{comandas_criadas} comandas, "
                f"{usuarios_criados} usuários e "
                f"{produtos_criados} produtos criados."
            )
        )
