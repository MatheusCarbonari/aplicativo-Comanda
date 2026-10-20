from django.db import migrations, models
from django.utils import timezone


CRIAR_TRIGGER = """
CREATE TRIGGER lancamento_somente_atendimento_aberto
BEFORE INSERT ON persistencia_lancamento
FOR EACH ROW
WHEN (
    SELECT estado
    FROM persistencia_atendimento
    WHERE id = NEW.atendimento_id
) <> 'ABERTO'
BEGIN
    SELECT RAISE(ABORT, 'lancamento_atendimento_encerrado');
END;
"""

REMOVER_TRIGGER = (
    "DROP TRIGGER IF EXISTS lancamento_somente_atendimento_aberto;"
)


def preencher_abertura_historica(apps, schema_editor):
    Atendimento = apps.get_model("persistencia", "Atendimento")
    Lancamento = apps.get_model("persistencia", "Lancamento")
    instante_migracao = timezone.now()
    atendimentos = list(Atendimento.objects.all())
    for atendimento in atendimentos:
        primeiro_lancamento = (
            Lancamento.objects.filter(atendimento_id=atendimento.pk)
            .order_by("horario", "pk")
            .first()
        )
        atendimento.aberto_em = (
            primeiro_lancamento.horario
            if primeiro_lancamento is not None
            else instante_migracao
        )
    Atendimento.objects.bulk_update(atendimentos, ["aberto_em"])


class Migration(migrations.Migration):
    dependencies = [
        (
            "persistencia",
            "0007_lancamento_somente_atendimento_aberto",
        ),
    ]

    operations = [
        migrations.RunSQL(
            sql=REMOVER_TRIGGER,
            reverse_sql=CRIAR_TRIGGER,
        ),
        migrations.AddField(
            model_name="atendimento",
            name="aberto_em",
            field=models.DateTimeField(null=True),
        ),
        migrations.RunPython(
            preencher_abertura_historica,
            reverse_code=migrations.RunPython.noop,
        ),
        migrations.AlterField(
            model_name="atendimento",
            name="aberto_em",
            field=models.DateTimeField(auto_now_add=True),
        ),
        migrations.RunSQL(
            sql=CRIAR_TRIGGER,
            reverse_sql=REMOVER_TRIGGER,
        ),
    ]
