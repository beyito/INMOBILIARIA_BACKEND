# alertas/services.py

from django.utils import timezone
from datetime import timedelta
# Asegúrate de que Contrato, AlertaModel, Usuario, e Inmueble estén importados o accesibles
# Asumimos que los siguientes modelos y funciones están disponibles en el ámbito global del proyecto
from contrato.models import Contrato 
from .models import AlertaModel 
from .utils import enviar_notificacion_push 
# from .utils import enviar_notificacion_push # <- Asume que está accesible en el mismo ámbito

# Importamos logger si lo vas a usar aquí
import logging
logger = logging.getLogger(__name__)


def ejecutar_generacion_alertas_diaria():
    """
    Función de servicio que ejecuta la lógica de detección y generación de alertas
    (Alquiler y Anticrético) basándose en la fecha de hoy.
    
    Esta función es llamada por el Cron Job o al inicio de una sesión/pestaña (solución temporal).
    La lógica de prevención de duplicados diarios está incluida.
    """
    hoy = timezone.now().date()
    alquiler_alertas = 0
    anticretico_alertas = 0

    # 1. PROCESAR CONTRATOS DE ALQUILER (Recordatorio de Pago Mensual)
    
    # Usamos select_related('agente', 'inmueble') para optimizar la consulta
    alquileres_activos = Contrato.objects.filter(
        tipo_contrato='alquiler', 
        estado='activo',
        fecha_inicio__isnull=False,
        fecha_fin__isnull=False # Asumimos que todos tienen fecha_fin
    ).select_related('agente', 'inmueble') 
    
    for contrato in alquileres_activos:
        fecha_inicio = contrato.fecha_inicio
        fecha_fin = contrato.fecha_fin
        fecha_pago_base = contrato.fecha_inicio.day
        
        # Validación de Rango (Vigencia del Contrato)
        if hoy < fecha_inicio or hoy > fecha_fin:
            continue
            
        # 1.1 Condición de Disparo: Si hoy es el día de pago
        if hoy.day == fecha_pago_base:
            
            # --- EVITAR DUPLICADOS (Chequeo Mes/Año + Día de Creación) ---
            alerta_existente_hoy = AlertaModel.objects.filter(
                contrato=contrato, 
                tipo_alerta='pago_alquiler',
                mes_obligacion=hoy.month,
                año_obligacion=hoy.year,
                fecha_programada__date=hoy # Solo verifica las creadas HOY
            ).exists()
            
            if not alerta_existente_hoy:
                
                # CREACIÓN DE ALERTA
                mensaje_alquiler = (
                    f"📆 PAGO ALQUILER HOY: El pago de alquiler del inmueble "
                    f"'{contrato.inmueble.titulo}' (ID: {contrato.inmueble.id}) vence "
                    f"el día de HOY, {hoy.strftime('%d/%m/%Y')}."
                )
                
                alerta = AlertaModel.objects.create(
                    contrato=contrato,
                    usuario_receptor=contrato.agente,
                    tipo_alerta='pago_alquiler',
                    fecha_programada=timezone.now(),
                    mensaje=mensaje_alquiler,
                    mes_obligacion=hoy.month,
                    año_obligacion=hoy.year
                )
                
                # ENVÍO
                # Asumo que enviar_notificacion_push está accesible en el contexto global
                enviar_notificacion_push(alerta) 
                alquiler_alertas += 1

    # 2. PROCESAR CONTRATOS DE ANTICRÉTICO (Recordatorio de Finalización)
    fecha_recordatorio_anticretico = hoy + timedelta(days=90) 
    
    anticreticos_activos = Contrato.objects.filter(
        tipo_contrato='anticretico', 
        estado='activo',
        fecha_fin__isnull=False
    ).select_related('agente', 'inmueble') # Añadimos inmueble para el mensaje
    
    for contrato in anticreticos_activos:
        # Solo si la fecha de fin cae DENTRO de los próximos 90 días
        if contrato.fecha_fin == fecha_recordatorio_anticretico:
            
            # Verificar si la alerta ya fue enviada (prevención de duplicados de por vida)
            alerta_existente = AlertaModel.objects.filter(
                contrato=contrato, 
                tipo_alerta='vencimiento_anticretico',
            ).exists()
            
            if not alerta_existente:
                
                dias_restantes = (contrato.fecha_fin - hoy).days

                mensaje_anticretico = (
                    f"🔔 VENCIMIENTO PRÓXIMO (90 días): El contrato de anticrético "
                    f"del inmueble '{contrato.inmueble.titulo}' (ID: {contrato.inmueble.id}) "
                    f"finaliza en {dias_restantes} días ({contrato.fecha_fin.strftime('%d/%m/%Y')})."
                )
                
                alerta = AlertaModel.objects.create(
                    contrato=contrato,
                    usuario_receptor=contrato.agente,
                    tipo_alerta='vencimiento_anticretico',
                    fecha_programada=timezone.now(),
                    mensaje=mensaje_anticretico
                )
                enviar_notificacion_push(alerta)
                anticretico_alertas += 1
                
    logger.info(f"Servicio Alertas ejecutado. Alquiler: {alquiler_alertas}, Anticrético: {anticretico_alertas}")
    return alquiler_alertas, anticretico_alertas