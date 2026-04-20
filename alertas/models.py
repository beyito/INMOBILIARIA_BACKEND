# alertas/models.py

from django.db import models
from django.utils import timezone
from usuario.models import Usuario 
from contrato.models import Contrato

class AlertaModel(models.Model):
    # Tipos de Alerta definidos por la lógica de negocio
    TIPO_ALERTA_CHOICES = [
        ('pago_alquiler', 'Recordatorio de Pago de Alquiler'),
        ('vencimiento_anticretico', 'Vencimiento de Contrato Anticrético'),
        ('pago_vencido', 'Pago Vencido (Mora)'),
        ('aviso_admin', 'Aviso Inmediato del Administrador'),
    ]
    
    # MODIFICACIÓN EN ESTADOS DE ENVÍO
    ESTADO_ENVIO_CHOICES = [
        ('pendiente', 'Pendiente de Enviar'),
        ('enviado', 'Enviado'),
        ('fallido', 'Fallo de Envío'),
    ]
    
    # NUEVOS ESTADOS DE VISTO/NO VISTO (Seguimiento para el receptor)
    ESTADO_VISTO_CHOICES = [
        ('no_visto', 'No Visto'),
        ('visto', 'Visto'),
        ('descartado', 'Descartado/Archivado'),
    ]

    contrato = models.ForeignKey(
        Contrato, on_delete=models.CASCADE, related_name='alertas',
        null=True, blank=True, # Permitir NULL para Avisos Admin generales
        verbose_name="Contrato Asociado"
    )
    # Usuario a quien va dirigido (Agente, Propietario o Inquilino)
    usuario_receptor = models.ForeignKey(
        Usuario, on_delete=models.SET_NULL, null=True, blank=True,
        verbose_name="Usuario Receptor"
    )
    
    tipo_alerta = models.CharField(max_length=50, choices=TIPO_ALERTA_CHOICES)
    estado_envio = models.CharField(
        max_length=20, 
        choices=ESTADO_ENVIO_CHOICES, 
        default='pendiente',
        verbose_name="Estado de Envío (Técnico)"
    )
    
    # CAMPO DE SEGUIMIENTO (NUEVO)
    estado_visto = models.CharField(
        max_length=20, 
        choices=ESTADO_VISTO_CHOICES, 
        default='no_visto',
        verbose_name="Estado de Lectura (Usuario)"
    )
    
    # Contenido de la alerta
    mensaje = models.TextField()
    
    # Fechas de control
    fecha_programada = models.DateTimeField(verbose_name="Fecha de Ejecución Programada")
    fecha_envio = models.DateTimeField(null=True, blank=True, verbose_name="Fecha Real de Envío")
    
    # Para morosidad o pagos (registra el mes y año de la obligación)
    mes_obligacion = models.IntegerField(null=True, blank=True)
    año_obligacion = models.IntegerField(null=True, blank=True)
    
    class Meta:
        # Aseguramos un nombre de tabla único para evitar el conflicto
        db_table = 'alerta_registro' 
        verbose_name = 'Alerta'
        verbose_name_plural = 'Alertas'

    # 🟢 FUNCIÓN __str__ CORRECTAMENTE INDENTADA Y CON MANEJO DE NULL
    def __str__(self):
        # Maneja caso de que el contrato sea nulo (para 'aviso_admin')
        contrato_id = self.contrato.id if self.contrato else "AVISO_G"
        receptor_nombre = self.usuario_receptor.nombre if self.usuario_receptor else "N/A"
        
        return f"[{contrato_id}] {self.get_tipo_alerta_display()} a {receptor_nombre}"