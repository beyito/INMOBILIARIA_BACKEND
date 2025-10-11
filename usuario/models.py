# usuario/models.py
from django.db import models

from django.contrib.auth.models import AbstractUser
from django.utils import timezone
import datetime
import random
import string

# --------------------------
# Modelo de Grupo
# --------------------------
class Grupo(models.Model):
    nombre = models.CharField(max_length=50, unique=True)
    descripcion = models.TextField(blank=True, null=True)
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return self.nombre
    class Meta:
        db_table = "grupo" 

# --------------------------
# Modelo de Usuario
# --------------------------
class Usuario(AbstractUser):
    # Datos básicos
    nombre = models.CharField(max_length=100)
    correo = models.EmailField(unique=True)

    # Grupo al que pertenece
    grupo = models.ForeignKey(Grupo, on_delete=models.CASCADE, related_name="usuarios", null=True, blank=True)

    # Campos opcionales
    ci = models.CharField(max_length=20, blank=True, null=True)
    telefono = models.CharField(max_length=20, blank=True, null=True)
    ubicacion = models.CharField(max_length=200, blank=True, null=True)
    fecha_nacimiento = models.DateField(blank=True, null=True)
    # Flags mínimos
    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)  # Para poder entrar al admin si quieres

    def __str__(self):
        return self.nombre
    class Meta:
        db_table = "usuario"

# --------------------------
# Modelo de Componente
# --------------------------
class Componente(models.Model):
    nombre = models.CharField(max_length=100)   # Ej: "Propiedad, Contrato"
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return f"{self.nombre}"
    class Meta:
        db_table = "componente"

# --------------------------
# Privilegios (permisos de grupo sobre componente)
# --------------------------
class Privilegio(models.Model):
    grupo = models.ForeignKey(Grupo, on_delete=models.CASCADE, related_name="privilegios")
    componente = models.ForeignKey(Componente, on_delete=models.CASCADE, related_name="privilegios")

    puede_leer = models.BooleanField(default=False)
    puede_crear = models.BooleanField(default=False)
    puede_actualizar = models.BooleanField(default=False)
    puede_eliminar = models.BooleanField(default=False)
    puede_activar = models.BooleanField(default=False)

    class Meta:
        unique_together = ("grupo", "componente")

    def __str__(self):
        return f"{self.grupo.nombre} -> {self.componente.nombre}"
    class Meta:
        db_table = "privilegio"

 
def generate_code(length=6):
    """Genera un código alfanumérico aleatorio tipo 'AFG423'"""
    return ''.join(random.choices(string.ascii_uppercase + string.digits, k=length))

class PasswordResetCode(models.Model):
    user = models.ForeignKey(Usuario, on_delete=models.CASCADE, related_name='reset_codes')
    code = models.CharField(max_length=6)
    created_at = models.DateTimeField(auto_now_add=True)
    is_used = models.BooleanField(default=False)
    is_verified = models.BooleanField(default=False) 
    expires_at = models.DateTimeField()

    def save(self, *args, **kwargs):
        if not self.code:
            self.code = generate_code()
        if not self.expires_at:
            self.expires_at = timezone.now() + datetime.timedelta(minutes=15)  # código válido 15 min
        super().save(*args, **kwargs)

    def is_valid(self):
        return not self.is_used and timezone.now() <= self.expires_at
    
class SolicitudAgente(models.Model):
    ESTADO_CHOICES = [
        ('pendiente', 'Pendiente'),
        ('aceptado', 'Aceptado'),
        ('rechazado', 'Rechazado'),
    ]

    idSolicitud = models.AutoField(primary_key=True)
    # Datos del agente solicitante
    nombre = models.CharField(max_length=100)
    correo = models.EmailField(unique=True)
    telefono = models.CharField(max_length=20)
    numero_licencia = models.CharField(max_length=50, unique=True)
    experiencia = models.IntegerField(default=0)
    ci = models.CharField(max_length=20, unique = True)
    estado = models.CharField(max_length=20, choices=ESTADO_CHOICES, default='pendiente')
    fecha_solicitud = models.DateTimeField(auto_now_add=True)
    
    # Relación con Usuario (nullable, se llena al aprobar)
    idUsuario = models.OneToOneField(
        Usuario,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        db_column="idUsuario"
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "solicitud_agente"

    def __str__(self):
        return f"{self.nombre} - {self.estado}"
