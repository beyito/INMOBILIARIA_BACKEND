# ventas/models.py
from django.db import models
from usuario.models import Usuario
from inmueble.models import InmuebleModel
from contrato.models import Contrato

class VentaInmueble(models.Model):
    comprador = models.ForeignKey(Usuario, on_delete=models.CASCADE)
    inmueble = models.ForeignKey(InmuebleModel, on_delete=models.CASCADE)

    metodo_pago = models.CharField(
        max_length=20,
        choices=[
            ("stripe", "Stripe"),
            ("paypal", "PayPal"),
            ("efectivo", "Efectivo"),
        ]
    )

    monto = models.DecimalField(max_digits=12, decimal_places=2)

    estado_pago = models.CharField(
        max_length=20,
        choices=[
            ("pendiente", "Pendiente"),
            ("pagado", "Pagado"),
            ("fallido", "Fallido"),
        ],
        default="pendiente"
    )

    transaccion_id = models.CharField(max_length=200, null=True, blank=True)
    fecha = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Venta #{self.id} - Inmueble {self.inmueble.titulo}"

class AlquilerInmueble(models.Model):
    arrendatario = models.ForeignKey(Usuario, on_delete=models.CASCADE)
    inmueble = models.ForeignKey(InmuebleModel, on_delete=models.CASCADE)

    metodo_pago = models.CharField(
        max_length=20,
        choices=[
            ("stripe", "Stripe"),
            ("paypal", "PayPal"),
            ("efectivo", "Efectivo"),
        ]
    )

    monto_mensual = models.DecimalField(max_digits=12, decimal_places=2)

    estado_pago = models.CharField(
        max_length=20,
        choices=[
            ("pendiente", "Pendiente"),
            ("pagado", "Pagado"),
            ("atrasado", "Atrasado"),
        ],
        default="pendiente"
    )

    transaccion_id = models.CharField(max_length=200, null=True, blank=True)

    contrato = models.ForeignKey(Contrato, on_delete=models.CASCADE, null=True, blank=True)

    fecha_registro = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Alquiler #{self.id} - Inmueble {self.inmueble.titulo}"

