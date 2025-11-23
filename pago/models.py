# pago/models.py

from django.db import models
from django.utils import timezone
# Reemplaza con la ruta real de tus modelos
from contrato.models import Contrato 
from usuario.models import Usuario 
from decimal import Decimal

# --- CHOICES ---
METODO_PAGO_CHOICES = [
    ('stripe', 'Stripe (Pasarela)'),
    ('transferencia', 'Transferencia Bancaria'),
    ('qr_efectivo', 'QR (Vía Cajero/Efectivo)'), 
]

ESTADO_PAGO_CHOICES = [
    ('pendiente', 'Pendiente'),
    ('confirmado', 'Confirmado / Exitoso'),
    ('fallido', 'Fallido / Rechazado'),
    ('requiere_revision', 'Requiere Revisión (Manual/QR)'), 
]

# -------------------------------------------------------------
# 1. PAGO (Registro de Transacción Central)
# -------------------------------------------------------------
class Pago(models.Model):
    contrato = models.ForeignKey(Contrato, on_delete=models.CASCADE, related_name='pagos')
    cliente = models.ForeignKey(Usuario, on_delete=models.PROTECT, related_name='pagos_realizados') 
    monto_pagado = models.DecimalField(max_digits=12, decimal_places=2)
    
    fecha_pago = models.DateTimeField(default=timezone.now)
    metodo = models.CharField(max_length=20, choices=METODO_PAGO_CHOICES)
    estado = models.CharField(max_length=20, choices=ESTADO_PAGO_CHOICES, default='pendiente')
    
    referencia_transaccion = models.CharField(max_length=100, blank=True, null=True) 
    
    class Meta:
        db_table = 'pago_transaccion'
        verbose_name = 'Pago'
        ordering = ['-fecha_pago']

    def __str__(self):
        return f"Pago de {self.monto_pagado} vía {self.metodo} para Contrato #{self.contrato_id}"

# -------------------------------------------------------------
# 2. COMPROBANTE PAGO (Evidencia para Métodos Manuales/QR)
# -------------------------------------------------------------
class ComprobantePago(models.Model):
    pago = models.OneToOneField(Pago, on_delete=models.CASCADE, primary_key=True, related_name='comprobante')
    archivo_comprobante = models.FileField(upload_to='comprobantes_pago/', blank=True, null=True)
    fecha_registro = models.DateTimeField(default=timezone.now)
    usuario_registro = models.ForeignKey(Usuario, on_delete=models.SET_NULL, null=True, related_name='comprobantes_subidos') 
    observaciones = models.TextField(blank=True, null=True)

    class Meta:
        db_table = 'pago_comprobante'
        verbose_name = 'Comprobante de Pago'
        
    def __str__(self):
        return f"Comprobante para Pago #{self.pago_id}"