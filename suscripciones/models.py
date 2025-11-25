# suscripciones/models.py
from django.db import models
from django.utils import timezone
from datetime import timedelta
from usuario.models import Usuario

class Plan(models.Model):
    nombre = models.CharField(max_length=50)
    precio = models.DecimalField(max_digits=10, decimal_places=2)
    descripcion = models.TextField()
    limite_inmuebles = models.IntegerField()
    limite_usuarios = models.IntegerField(default=1)
    permite_alertas = models.BooleanField(default=False)
    permite_destacados = models.BooleanField(default=False)
    permite_reportes = models.BooleanField(default=False)
    duracion_dias = models.IntegerField(default=30)
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return f"{self.nombre} - ${self.precio}"

class Suscripcion(models.Model):
    ESTADOS = [
        ('activa', 'Activa'),
        ('vencida', 'Vencida'),
        ('cancelada', 'Cancelada'),
        ('pendiente', 'Pendiente de Pago'),
    ]

    usuario = models.OneToOneField(Usuario, on_delete=models.CASCADE, related_name='suscripcion')
    plan = models.ForeignKey(Plan, on_delete=models.PROTECT, related_name='suscripciones')
    
    fecha_inicio = models.DateTimeField(auto_now_add=True)
    fecha_fin = models.DateTimeField(null=True, blank=True) # Permitir null al inicio
    
    estado = models.CharField(max_length=20, choices=ESTADOS, default='pendiente')
    
    # 🆕 NUEVO CAMPO PARA STRIPE
    stripe_session_id = models.CharField(max_length=200, blank=True, null=True) 
    
    def calcular_fecha_fin(self):
        if not self.fecha_inicio:
            self.fecha_inicio = timezone.now()
        return self.fecha_inicio + timedelta(days=self.plan.duracion_dias)
    
    @property
    def esta_activa(self):
        # Si no tiene fecha fin, no está activa
        if not self.fecha_fin: return False
        return self.estado == 'activa' and self.fecha_fin > timezone.now()