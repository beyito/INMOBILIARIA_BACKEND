from django.db import models
from django.conf import settings
# Q y F se usan en constraints (validaciones a nivel BD) y consultas:
# - Q: construir condiciones lógicas (AND/OR/NOT).
# - F: referenciar otros campos de la MISMA fila (p. ej. hora_fin > hora_inicio).
from django.db.models import Q, F


# -----------------------------------------------------------------------------
# Mixin reutilizable para auditoría (fechas de creación y actualización)
# -----------------------------------------------------------------------------
class TimeStampedModel(models.Model):
    # auto_now_add: setea la fecha/hora automáticamente cuando se CREA el registro.
    created_at = models.DateTimeField(auto_now_add=True)
    # auto_now: actualiza la fecha/hora automáticamente en CADA guardado.
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        # abstract=True: no crea una tabla propia; solo inyecta estos campos
        # en las clases hijas que hereden de este mixin.
        abstract = True


# -----------------------------------------------------------------------------
# Catálogo de tipos de trámite (cada cita debe tener uno)
# -----------------------------------------------------------------------------
class TipoTramite(TimeStampedModel):
    """
    Catálogo de tipos de trámite para una cita (ej.: 'Visita a inmueble',
    'Firma de contrato', 'Tasación', etc.).
    """
    # CharField: texto corto con límite, unique=True impide nombres duplicados.
    nombre = models.CharField(max_length=80, unique=True)
    # TextField: texto largo; blank=True lo vuelve opcional en formularios/admin.
    descripcion = models.TextField(blank=True)
    # Bandera para activar/desactivar sin borrar. default=True lo activa por defecto.
    is_activo = models.BooleanField(default=True)

    class Meta:
        # Nombre explícito de la tabla en BD (evita depender del nombre del app/clase).
        db_table = "cita_tipo_tramite"
        # Orden por defecto al listar (alfabético por nombre).
        ordering = ["nombre"]

    # Representación legible en el admin/shell.
    def __str__(self):
        return self.nombre


# -----------------------------------------------------------------------------
# Disponibilidad recurrente del agente (franjas horarias)
# -----------------------------------------------------------------------------
class DisponibilidadAgente(TimeStampedModel):
    """
    Franja horaria recurrente en la que un agente acepta citas.
    """

    # Definimos constantes enteras 0..6 para los días (más eficiente que strings).
    LUNES, MARTES, MIERCOLES, JUEVES, VIERNES, SABADO, DOMINGO = range(7)

    # choices: mapea el valor guardado (0..6) a una etiqueta legible en formularios/admin.
    DIAS_SEMANA = (
        (LUNES, "Lunes"),
        (MARTES, "Martes"),
        (MIERCOLES, "Miércoles"),
        (JUEVES, "Jueves"),
        (VIERNES, "Viernes"),
        (SABADO, "Sábado"),
        (DOMINGO, "Domingo"),
    )

    # ForeignKey al modelo de usuario configurado; related_name define el acceso inverso.
    # on_delete=models.CASCADE: si se borra el agente, se borran sus disponibilidades.
    agente = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="disponibilidades_agente",
    )
    # Día de semana según las choices anteriores (entero pequeño positivo).
    dia_semana = models.PositiveSmallIntegerField(choices=DIAS_SEMANA)
    # Hora de inicio de la franja (solo tiempo, sin fecha).
    hora_inicio = models.TimeField()
    # Hora de fin de la franja (debe ser > hora_inicio; lo forzamos con un constraint).
    hora_fin = models.TimeField()

    # Ventana de vigencia opcional: desde/cuándo aplica esta franja.
    valido_desde = models.DateField(blank=True, null=True)
    # … y hasta cuándo; blank/null la vuelven opcional en formularios y BD.
    valido_hasta = models.DateField(blank=True, null=True)

    # Activa/inactiva la franja sin borrarla.
    is_activo = models.BooleanField(default=True)

    class Meta:
        # Nombre estable de la tabla.
        db_table = "cita_disponibilidad_agente"
        # Orden por defecto: primero agente, luego día, luego hora de inicio.
        ordering = ["agente", "dia_semana", "hora_inicio"]
        # Índice compuesto (B-tree) para acelerar búsquedas por (agente, día).
        indexes = [
            models.Index(fields=["agente", "dia_semana"]),
        ]
        # Constraints (validaciones a nivel BD)
        constraints = [
            # Check: exige que hora_fin sea estrictamente mayor que hora_inicio.
            models.CheckConstraint(
                check=Q(hora_fin__gt=F("hora_inicio")),
                name="disp_hora_fin_gt_inicio",
            ),
        ]
        # unique_together: evita duplicar EXACTAMENTE la misma franja para el mismo día.
        unique_together = (("agente", "dia_semana", "hora_inicio", "hora_fin"),)

    def __str__(self):
        # get_dia_semana_display(): convierte el entero a su etiqueta (Lunes, Martes, …).
        return f"{self.get_dia_semana_display()} {self.hora_inicio}-{self.hora_fin} ({self.agente})"


# -----------------------------------------------------------------------------
# Cita (el AGENTE administra y crea sus propias citas)
# -----------------------------------------------------------------------------
class Cita(TimeStampedModel):
    """
    Cita administrada por el AGENTE.
    Regla de negocio: la cita solo puede ser creada/gestionada por el mismo agente
    (creado_por == agente). Además, cada cita tiene un tipo de trámite.
    """

    # Constantes para el estado (evitan "magic strings" repetidos).
    ESTADO_PENDIENTE = "PENDIENTE"
    ESTADO_CONFIRMADA = "CONFIRMADA"
    ESTADO_REPROGRAMADA = "REPROGRAMADA"
    ESTADO_CANCELADA = "CANCELADA"
    ESTADO_COMPLETADA = "COMPLETADA"
    ESTADO_NO_SHOW = "NO_SHOW"

    # choices de estado: lo que se guarda y la etiqueta mostrada.
    ESTADOS = (
        (ESTADO_PENDIENTE, "Pendiente"),
        (ESTADO_CONFIRMADA, "Confirmada"),
        (ESTADO_REPROGRAMADA, "Reprogramada"),
        (ESTADO_CANCELADA, "Cancelada"),
        (ESTADO_COMPLETADA, "Completa"),
        (ESTADO_NO_SHOW, "No se presentó"),
    )

    # ---------- Datos descriptivos ----------
    # Título corto de la cita (máx. 120 chars).
    titulo = models.CharField(max_length=120)
    # Detalle opcional de la cita.
    descripcion = models.TextField(blank=True)

    # ---------- Fecha y horas ----------
    # Fecha del día de la cita (sin hora).
    fecha_cita = models.DateField()
    # Hora de inicio (sin fecha).
    hora_inicio = models.TimeField()
    # Hora de fin (debe ser > inicio; se valida por constraint abajo).
    hora_fin = models.TimeField()

    # Estado actual de la cita; default=Pendiente.
    estado = models.CharField(max_length=12, choices=ESTADOS, default=ESTADO_PENDIENTE)

    # ---------- Relaciones ----------
    # Cliente relacionado (usuario que asistirá como cliente).
    cliente = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,         # si se borra el cliente, se borran sus citas
        related_name="citas_como_cliente" # acceso inverso: user.citas_como_cliente.all()
    )
    # Agente propietario de la agenda (quien atiende y administra).
    agente = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,         # si se borra el agente, caen sus citas
        related_name="citas_como_agente"  # acceso inverso: user.citas_como_agente.all()
    )

    # Usuario que creó la cita. Regla: DEBE ser el mismo agente (constraint abajo).
    creado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="citas_creadas"      # acceso inverso: user.citas_creadas.all()
    )

    # Tipo de trámite de la cita. PROTECT evita borrar un trámite si hay citas que lo usan.
    tramite = models.ForeignKey(
        "cita.TipoTramite",
        on_delete=models.PROTECT,
        related_name="citas"              # acceso inverso: tipotramite.citas.all()
    )

    # (Opcional) Para enlazar un inmueble específico más adelante:
    # inmueble = models.ForeignKey(
    #     "inmueble.Inmueble",
    #     on_delete=models.SET_NULL,       # si se borra el inmueble, la cita queda con NULL
    #     blank=True, null=True,
    #     related_name="citas"
    # )

    class Meta:
        # Nombre explícito de la tabla.
        db_table = "cita_cita"
        # Orden por defecto: primero las citas más recientes y más tarde en el día.
        ordering = ["-fecha_cita", "-hora_inicio"]
        # Índices para acelerar consultas típicas del calendario/dashboard.
        indexes = [
            models.Index(fields=["agente", "fecha_cita"]),
            models.Index(fields=["cliente", "fecha_cita"]),
            models.Index(fields=["fecha_cita", "hora_inicio"]),
            models.Index(fields=["tramite", "fecha_cita"]),
        ]
        constraints = [
            models.CheckConstraint(
                check=Q(hora_fin__gt=F("hora_inicio")),
                name="cita_hora_fin_gt_inicio",
            ),
            models.CheckConstraint(
                check=Q(creado_por=F("agente")),
                name="cita_creado_por_es_agente",
            ),
        ]
        unique_together = (("agente", "fecha_cita", "hora_inicio"),)

    def __str__(self):
        # Texto útil para listados/logs/admin.
        return f"{self.titulo} · {self.fecha_cita} {self.hora_inicio}-{self.hora_fin} · {self.agente} · {self.tramite}"
