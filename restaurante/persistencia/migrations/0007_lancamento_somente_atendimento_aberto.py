from django.db import migrations


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


class Migration(migrations.Migration):
    dependencies = [
        (
            "persistencia",
            "0006_atendimento_fechado_em_atendimento_fechado_por",
        ),
    ]

    operations = [
        migrations.RunSQL(
            sql=CRIAR_TRIGGER,
            reverse_sql=REMOVER_TRIGGER,
        ),
    ]
