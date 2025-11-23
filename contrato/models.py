# contrato/models.py
from django.db import models

# Create your models here.
from django.db import models
from usuario.models import Usuario
from inmueble.models import InmuebleModel as Inmueble

class Contrato(models.Model):
    TIPO_CONTRATO_CHOICES = [
        ('servicios', 'Contrato de Servicios Inmobiliarios'),
        ('venta', 'Contrato de Venta'),
        ('alquiler', 'Contrato de Alquiler'),
        ('anticretico', 'Contrato de Anticrético'),
    ]
    
    ESTADO_CHOICES = [
        ('activo', 'Activo'),
        ('finalizado', 'Finalizado'),
        ('cancelado', 'Cancelado'),
        ('pendiente', 'Pendiente'),
    ]

    # Relaciones foráneas
    agente = models.ForeignKey(Usuario, on_delete=models.CASCADE, related_name='contratos')
    inmueble = models.ForeignKey(Inmueble, on_delete=models.CASCADE, related_name='contratos')
    
    # Información básica del contrato
    tipo_contrato = models.CharField(max_length=20, choices=TIPO_CONTRATO_CHOICES)
    estado = models.CharField(max_length=20, choices=ESTADO_CHOICES, default='activo')
    
    # Información común a todos los contratos
    ciudad = models.CharField(max_length=100)
    fecha_contrato = models.DateField()
    fecha_creacion = models.DateTimeField(auto_now_add=True)
    fecha_actualizacion = models.DateTimeField(auto_now=True)
    
    # Partes del contrato (común a todos)
    parte_contratante_nombre = models.CharField(max_length=200)  # Cliente/Arrendador/Vendedor
    parte_contratante_ci = models.CharField(max_length=20)
    parte_contratante_domicilio = models.TextField(blank=True, null=True)
    
    parte_contratada_nombre = models.CharField(max_length=200)  # Inmobiliaria/Arrendatario/Comprador
    parte_contratada_ci = models.CharField(max_length=20, blank=True, null=True)
    parte_contratada_domicilio = models.TextField(blank=True, null=True)
    
    # Términos económicos (común a todos)
    monto = models.DecimalField(max_digits=12, decimal_places=2, blank=True, null=True)  # Precio/Renta/Comisión
    comision_porcentaje = models.DecimalField(max_digits=5, decimal_places=2, blank=True, null=True)
    comision_monto = models.DecimalField(max_digits=12, decimal_places=2, blank=True, null=True)
    
    # Plazos y vigencia
    vigencia_meses = models.IntegerField(blank=True, null=True)  # Para alquiler/anticrético
    vigencia_dias = models.IntegerField(blank=True, null=True)   # Para servicios
    fecha_inicio = models.DateField(blank=True, null=True)
    fecha_fin = models.DateField(blank=True, null=True)
    id_cliente = models.ForeignKey(
        Usuario, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True, 
        related_name='id_cliente_parte_contratante'
    )
    
    # Información adicional específica por tipo
    detalles_adicionales = models.JSONField(default=dict, blank=True)  # Para datos específicos de cada tipo
    
    # Metadata
    creado_por = models.ForeignKey(Usuario, on_delete=models.SET_NULL, null=True, related_name='contratos_creados')
    archivo_pdf = models.FileField(upload_to='contratos/', blank=True, null=True)
    
    class Meta:
        db_table = 'contratos'
        verbose_name = 'Contrato'
        verbose_name_plural = 'Contratos'
        ordering = ['-fecha_creacion']

    def __str__(self):
        return f"{self.get_tipo_contrato_display()} - {self.parte_contratante_nombre} - {self.inmueble}"

    def save(self, *args, **kwargs):
        # Lógica para calcular comisión si es necesario
        if self.monto and self.comision_porcentaje and not self.comision_monto:
            self.comision_monto = (self.monto * self.comision_porcentaje) / 100
        super().save(*args, **kwargs)

