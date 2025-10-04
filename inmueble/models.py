from django.db import models
from usuario.models import Usuario

# Create your models here.

class TipoInmuebleModel(models.Model):
    nombre = models.CharField(max_length=50, unique=True)
    descripcion = models.CharField(max_length=150, blank=True, null=True)
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return self.nombre

    class Meta:
        db_table = "tipo_inmueble"


class InmuebleModel(models.Model):
    agente = models.ForeignKey(Usuario, on_delete=models.CASCADE, related_name="inmueble_agente")
    cliente = models.ForeignKey(Usuario, on_delete=models.CASCADE, related_name="inmueble_cliente")
    tipo_inmueble = models.ForeignKey(TipoInmuebleModel, on_delete=models.SET_NULL, null=True, blank=True)
    titulo = models.CharField(max_length=100, blank=True, null=True)
    descripcion = models.CharField(max_length=300, blank=True, null=True)
    direccion = models.CharField(max_length=150, blank=True, null=True)
    ciudad = models.CharField(max_length=150, blank=True, null=True)
    zona = models.CharField(max_length=150, blank=True, null=True)
    superficie = models.DecimalField(max_digits=10, decimal_places=2)
    dormitorios = models.IntegerField(default=0)
    baños = models.IntegerField(default=0)
    precio = models.DecimalField(max_digits=12, decimal_places=2)
    tipo_operacion = models.CharField(max_length=20, choices=[
        ('venta', 'Venta'),
        ('alquiler', 'Alquiler'),
        ('anticretico', 'Anticrético'),
    ])
    estado = models.CharField(max_length=30, choices=[
        ('pendiente', 'Pendiente'),
        ('aprobado', 'Aprobado'),
        ('rechazado', 'Rechazado'),
    ], default='pendiente', null=True, blank=True)
    latitud = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    longitud = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    is_active = models.BooleanField(default=True)
    def __str__(self):
        return f"{self.titulo or 'Inmueble sin título'} - {self.tipo_operacion} ({self.estado})"
    
    class Meta:
        db_table = "inmueble"



class CambioInmuebleModel(models.Model):
    agente = models.ForeignKey(Usuario, on_delete=models.CASCADE, related_name="cambio_inmueble_agente")
    titulo = models.CharField(max_length=100, blank=True, null=True)
    descripcion = models.CharField(max_length=300, blank=True, null=True)
    direccion = models.CharField(max_length=150, blank=True, null=True)
    ciudad = models.CharField(max_length=150, blank=True, null=True)
    zona = models.CharField(max_length=150, blank=True, null=True)
    superficie = models.DecimalField(max_digits=10, decimal_places=2, blank=True, null=True)
    dormitorios = models.IntegerField(blank=True, null=True)
    baños = models.IntegerField(blank=True, null=True)
    precio = models.DecimalField(max_digits=12, decimal_places=2, blank=True, null=True)
    tipo_operacion = models.CharField(max_length=20, choices=[
        ('venta', 'Venta'),
        ('alquiler', 'Alquiler'),
        ('anticretico', 'Anticrético'),
    ], blank=True, null=True)
    estado = models.CharField(max_length=30, choices=[
        ('pendiente', 'Pendiente'),
        ('aprobado', 'Aprobado'),
        ('rechazado', 'Rechazado'),
    ],default='pendiente', blank=True, null=True)
    latitud = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    longitud = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    fecha_solicitud = models.DateField(auto_now_add=True)
    fecha_revision = models.DateField(blank=True, null=True)
    def __str__(self):
        return f"{self.titulo or 'Inmueble sin título'} - {self.tipo_operacion} ({self.estado})"
    
    class Meta:
        db_table = "cambio_inmueble"