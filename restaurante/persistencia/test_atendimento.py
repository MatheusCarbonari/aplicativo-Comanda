from django.db import IntegrityError, transaction
from django.test import TestCase

from restaurante.persistencia.models import Atendimento, ComandaFisica


class AtendimentoPersistenciaTests(TestCase):
    def test_relacao_comanda_atendimento_e_persistida_no_sqlite(self):
        comanda = ComandaFisica.objects.create(identificador="001")

        atendimento = Atendimento.objects.create(
            comanda=comanda,
            estado=Atendimento.Estado.ENCERRADO,
        )

        atendimento.refresh_from_db()
        self.assertEqual(atendimento.comanda_id, comanda.pk)
        self.assertEqual(atendimento.estado, Atendimento.Estado.ENCERRADO)
        self.assertEqual(comanda.atendimentos.get(), atendimento)

    def test_sqlite_impede_dois_atendimentos_abertos_na_mesma_comanda(self):
        comanda = ComandaFisica.objects.create(identificador="001")
        Atendimento.objects.create(
            comanda=comanda,
            estado=Atendimento.Estado.ENCERRADO,
        )
        Atendimento.objects.create(
            comanda=comanda,
            estado=Atendimento.Estado.ENCERRADO,
        )
        Atendimento.objects.create(comanda=comanda)

        with self.assertRaises(IntegrityError), transaction.atomic():
            Atendimento.objects.create(comanda=comanda)

        self.assertEqual(comanda.atendimentos.count(), 3)
