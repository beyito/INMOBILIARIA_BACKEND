from django.db.models.signals import post_save
from django.dispatch import receiver
from dateutil.relativedelta import relativedelta
from datetime import date, datetime # Necesitamos datetime para la conversión
from contrato.models import Contrato
from .models import Alerta, AlertConfig

# Función auxiliar para convertir cadena YYYY-MM-DD a objeto date
def _get_safe_date(value):
    if isinstance(value, date):
        return value
    if isinstance(value, str):
        try:
            return datetime.strptime(value, '%Y-%m-%d').date()
        except (ValueError, TypeError):
            return None
    return None


@receiver(post_save, sender=Contrato)
def crear_alertas_por_contrato(sender, instance: Contrato, created, **kwargs):
    """
    Genera alertas de cuotas (alquiler) o fin de contrato (anticrético).
    Usa una verificación de tipo robusta y convierte las fechas si son strings.
    """
    if not created:
        return

    # 1. Configuración por defecto
    AlertConfig.objects.get_or_create(
        contrato=instance,
        defaults={'dias_recordatorio': [30,15,7,3,1], 'canal_email': True, 'canal_push': True, 'activo': True}
    )

    # Lectura y conversión robusta de valores:
    tipo = getattr(instance, 'tipo_contrato', None)
    
    # Usar _get_safe_date para manejar strings y None
    fi   = _get_safe_date(getattr(instance, 'fecha_inicio', None))
    fin  = _get_safe_date(getattr(instance, 'fecha_fin', None))
    
    meses = getattr(instance, 'vigencia_meses', 0) or 0

    # 2. Lógica de Alquiler: Chequeo robusto de tipo
    if tipo and 'alquiler' in tipo.lower() and fi and meses > 0:
        # Crear 1 alerta por cuota mensual
        for i in range(1, meses + 1):
            due = fi + relativedelta(months=+i)
            Alerta.objects.create(
                contrato=instance,
                tipo='alquiler_cuota',
                titulo=f"Pago Alquiler {due.strftime('%B').capitalize()}",
                descripcion=f"Cuota #{i} del contrato #{instance.id}",
                due_date=due,
                periodo_index=i,
            )

    # 3. Lógica de Anticrético: Chequeo robusto de tipo
    if tipo and 'anticrético' in tipo.lower() and fin:
        # Crear alerta de fin de contrato
        Alerta.objects.create(
            contrato=instance,
            tipo='fin_contrato',
            titulo="Recordatorio Fin de Contrato",
            descripcion=f"Fin del contrato #{instance.id}",
            due_date=fin,
        )