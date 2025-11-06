from django.db import models
from django.utils import timezone
from contrato.models import Contrato
from usuario.models import Grupo, Usuario 

ALERTA_TIPO = [
    ('alquiler_cuota', 'Cuota mensual de alquiler'),
    ('fin_contrato',   'Fin de contrato (anticrético/alquiler)'),
    ('custom',         'Alerta manual'),
]

ALERTA_ESTADO = [
    ('pendiente', 'Pendiente'),
    ('enviado',   'Enviado'),
    ('vencido',   'Vencido'),
]

class AlertConfig(models.Model):
    """
    Preferencias por contrato para ventanas de aviso.
    """
    contrato = models.OneToOneField(Contrato, on_delete=models.CASCADE, related_name='alert_config')
    dias_recordatorio = models.JSONField(default=list, blank=True)  # p.ej. [30,15,7,3,1]
    canal_email = models.BooleanField(default=True)
    canal_push = models.BooleanField(default=True)
    activo = models.BooleanField(default=True)
    creado = models.DateTimeField(auto_now_add=True)
    actualizado = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'alerta_config'

    def __str__(self):
        return f"AlertConfig contrato #{self.contrato_id}"

class Alerta(models.Model):
    """
    Instancias de alertas. Para alquiler: 1 por cuota. Para anticrético: 1 por fin.
    Para 'custom': creada por usuario.
    """
    contrato = models.ForeignKey(Contrato, on_delete=models.CASCADE, related_name='alertas', null=True, blank=True)
    tipo = models.CharField(max_length=20, choices=ALERTA_TIPO, default='custom')
    titulo = models.CharField(max_length=120)
    descripcion = models.TextField(blank=True, null=True)
    due_date = models.DateField()         # fecha objetivo (vencimiento o fin)
    periodo_index = models.PositiveIntegerField(null=True, blank=True)  # # de cuota (alquiler)
    estado = models.CharField(max_length=10, choices=ALERTA_ESTADO, default='pendiente')
    creado = models.DateTimeField(auto_now_add=True)
    actualizado = models.DateTimeField(auto_now=True)
    grupos_destino = models.ManyToManyField(Grupo, blank=True, related_name='alertas')
    usuarios_destino = models.ManyToManyField(Usuario, blank=True, related_name='alertas_directas')

    class Meta:
        db_table = 'alerta'
        indexes = [
            models.Index(fields=['due_date']),
            models.Index(fields=['tipo', 'estado']),
        ]

    def __str__(self):
        return f"[{self.tipo}] {self.titulo} ({self.due_date})"

class AlertLog(models.Model):
    alerta = models.ForeignKey('Alerta', on_delete=models.CASCADE, related_name='logs')
    canal = models.CharField(max_length=10, choices=[('email','email'),('push','push')])

    # uno de los dos (según el tipo)
    periodo_index = models.IntegerField(null=True, blank=True)  # alquiler mensual: 0,1,2,...
    days_before   = models.IntegerField(null=True, blank=True)  # anticrético: 7,3,1,0

    fecha_envio = models.DateField(auto_now_add=True)

    class Meta:
        constraints = [
            # evita re-enviar el mismo periodo/canal el mismo día
            models.UniqueConstraint(
                fields=['alerta','canal','fecha_envio','periodo_index'],
                name='uniq_alerta_periodo_canal_dia',
                condition=models.Q(periodo_index__isnull=False)
            ),
            models.UniqueConstraint(
                fields=['alerta','canal','fecha_envio','days_before'],
                name='uniq_alerta_daysbefore_canal_dia',
                condition=models.Q(days_before__isnull=False)
            ),
        ]
# alerta/models.py (Añadir al final del archivo)

from usuario.models import Usuario # Asegúrate de importar el modelo Usuario

class AlertaLectura(models.Model):
    """
    Rastrea qué usuarios han marcado una alerta como 'vista'.
    """
    alerta = models.ForeignKey(Alerta, on_delete=models.CASCADE)
    usuario = models.ForeignKey(Usuario, on_delete=models.CASCADE)
    fecha_vista = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'alerta_lectura'
        # Crucial: Un usuario solo puede tener una entrada por alerta
        unique_together = ('alerta', 'usuario')

    def __str__(self):
        return f"Alerta {self.alerta_id} vista por {self.usuario.username}"