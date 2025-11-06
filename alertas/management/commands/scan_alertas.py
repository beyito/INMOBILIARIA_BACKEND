from django.core.management.base import BaseCommand
from alertas.services import scan_and_send_alerts

class Command(BaseCommand):
    help = "Escanea y envía alertas de pago/fin de contrato"

    def handle(self, *args, **kwargs):
        res = scan_and_send_alerts()
        self.stdout.write(self.style.SUCCESS(f"Envíos: {res}"))
