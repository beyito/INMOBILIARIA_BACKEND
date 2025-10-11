from django.db import models
from django.conf import settings

User = settings.AUTH_USER_MODEL

class Cita(models.Model):
    ESTADOS = (
        ("PENDIENTE", "PENDIENTE"),
        ("CONFIRMADA", "CONFIRMADA"),
        ("CANCELADA", "CANCELADA"),
        ("REALIZADA", "REALIZADA"),
        ("REPROGRAMADA", "REPROGRAMADA"),
    )

    titulo = models.CharField(max_length=200)
    descripcion = models.TextField(blank=True, null=True)

    fecha_cita = models.DateField()
    hora_inicio = models.TimeField()
    hora_fin = models.TimeField()

    estado = models.CharField(max_length=20, choices=ESTADOS, default="CONFIRMADA")

    cliente = models.ForeignKey(User, on_delete=models.CASCADE, related_name="citas_como_cliente")
    agente = models.ForeignKey(User, on_delete=models.CASCADE, related_name="citas_como_agente")
    creado_por = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name="citas_creadas")

    creado_en = models.DateTimeField(auto_now_add=True)
    actualizado_en = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-fecha_cita", "hora_inicio"]
        indexes = [
            models.Index(fields=["agente", "fecha_cita"]),
            models.Index(fields=["cliente", "fecha_cita"]),
            models.Index(fields=["fecha_cita", "hora_inicio", "hora_fin"]),
        ]

    def __str__(self):
        return f"{self.titulo} ({self.fecha_cita} {self.hora_inicio}-{self.hora_fin})"
