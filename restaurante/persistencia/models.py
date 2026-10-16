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


class LancamentoQuerySet(models.QuerySet):
    def validos(self):
        return self.filter(cancelamento__isnull=True)


class Lancamento(models.Model):
    objects = LancamentoQuerySet.as_manager()

    atendimento = models.ForeignKey(
        Atendimento,
        on_delete=models.PROTECT,
        related_name="lancamentos",
    )
    produto = models.ForeignKey(
        Produto,
        on_delete=models.PROTECT,
        related_name="lancamentos",
    )
    quantidade = models.PositiveIntegerField()
    preco_unitario_centavos = models.PositiveIntegerField()
    autor = models.ForeignKey(
        UsuarioOperacional,
        on_delete=models.PROTECT,
        related_name="lancamentos_realizados",
    )
    horario = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=models.Q(quantidade__gt=0),
                name="lancamento_quantidade_positiva",
            )
        ]


class CancelamentoLancamento(models.Model):
    class Motivo(models.TextChoices):
        DUPLICADO = "DUPLICADO", "Duplicado"
        PRODUTO_INCORRETO = "PRODUTO_INCORRETO", "Produto incorreto"
        QUANTIDADE_INCORRETA = (
            "QUANTIDADE_INCORRETA",
            "Quantidade incorreta",
        )
        DESISTENCIA = "DESISTENCIA", "Desistência"
        OUTRO = "OUTRO", "Outro"

    lancamento = models.OneToOneField(
        Lancamento,
        on_delete=models.PROTECT,
        related_name="cancelamento",
    )
    motivo = models.CharField(max_length=24, choices=Motivo.choices)
    descricao = models.TextField(blank=True)
    autor = models.ForeignKey(
        UsuarioOperacional,
        on_delete=models.PROTECT,
        related_name="cancelamentos_realizados",
    )
    horario = models.DateTimeField(auto_now_add=True)


class RegistroIdempotencia(models.Model):
    chave = models.CharField(max_length=255, unique=True)
    operacao = models.CharField(max_length=80)
    hash_conteudo = models.CharField(max_length=64)
    resultado = models.JSONField()
    criado_em = models.DateTimeField(auto_now_add=True)
