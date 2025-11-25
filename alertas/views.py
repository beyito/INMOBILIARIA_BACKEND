# alertas/views.py
from rest_framework.response import Response
from rest_framework import status
from datetime import timedelta
from django.db.models import Q
from django.utils import timezone
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated, IsAdminUser
from rest_framework.response import Response
from rest_framework import status
from django.shortcuts import get_object_or_404
from contrato.models import Contrato # Tu modelo de Contrato
from usuario.models import Usuario # Tu modelo de Usuario
from .models import AlertaModel
from .utils import enviar_notificacion_push 
from .serializers import AlertaSerializer
from .services import ejecutar_generacion_alertas_diaria
import logging
logger = logging.getLogger(__name__)

from suscripciones.models import Suscripcion
# =========================================================
# 🎯 CRON JOB: GENERADOR DE ALERTAS DIARIO (CORREGIDO)
# =========================================================

@api_view(['POST'])
# NOTA: En producción, esta ruta debe ser accedida solo internamente o por un servicio de Cron Job.
def cron_generar_alertas(request):
    """
    Ejecuta el proceso de detección y generación de alertas DIARIAMENTE.
    
    1. ALQUILER: Envía recordatorio el día exacto de la fecha de pago (fecha_inicio.day).
    2. ANTICRÉTICO: Envía recordatorio 90 días antes del vencimiento (una sola vez).
    """
    hoy = timezone.now().date()
    alquiler_alertas = 0
    anticretico_alertas = 0

    # 1. PROCESAR CONTRATOS DE ALQUILER (Recordatorio de Pago Mensual)
    
    # Filtramos contratos activos cuya fecha de inicio no es nula
    alquileres_activos = Contrato.objects.filter(
        tipo_contrato='alquiler', 
        estado='activo',
        fecha_inicio__isnull=False
    ).select_related('agente')
    
    for contrato in alquileres_activos:
        fecha_inicio = contrato.fecha_inicio # Ya es un objeto date si es models.DateField
        fecha_fin = contrato.fecha_fin       # Ya es un objeto date si es models.DateField  
        fecha_pago_base = contrato.fecha_inicio.day
        if hoy < fecha_inicio:
            # print(f"Contrato {contrato.id} no ha iniciado.")
            continue
        
        if hoy > fecha_fin:
            # print(f"Contrato {contrato.id} ya finalizó.")
            continue
        # LÓGICA CORREGIDA: Si hoy es el día de pago del contrato
        if hoy.day == fecha_pago_base:
            
            # --- EVITAR DUPLICADOS EN EL MISMO DÍA (Cron Job podría correr dos veces) ---
            # Verificamos si ya existe una alerta para este contrato, para el mes/año actual, 
            # y que haya sido programada/enviada hoy.
            alerta_existente_hoy = AlertaModel.objects.filter(
                contrato=contrato, 
                tipo_alerta='pago_alquiler',
                mes_obligacion=hoy.month, # Usamos el mes actual como obligación
                año_obligacion=hoy.year,
            ).filter(
                # Importante: Solo verificamos alertas creadas/programadas hoy
                fecha_programada__date=hoy 
            ).exists()
            
            if not alerta_existente_hoy:
                # El recordatorio es para el Agente (quien debe cobrar)
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
                # Enviar y contabilizar
                enviar_notificacion_push(alerta)
                alquiler_alertas += 1

    # 2. PROCESAR CONTRATOS DE ANTICRÉTICO (Recordatorio de Finalización - Lógica se mantiene)
    # Notificar al agente 90 días antes de la fecha de fin (para negociar).
    fecha_recordatorio_anticretico = hoy + timedelta(days=90) 
    
    anticreticos_activos = Contrato.objects.filter(
        tipo_contrato='anticretico', 
        estado='activo',
        fecha_fin__isnull=False
    ).select_related('agente')
    
    for contrato in anticreticos_activos:
        # Solo si la fecha de fin cae DENTRO de los próximos 90 días
        if contrato.fecha_fin == fecha_recordatorio_anticretico:
            
            # 2.1 Verificar si la alerta ya fue enviada (solo se envía 1 vez)
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
                
    # Respuesta final del Cron Job
    logger.info(f"Cron Job finalizado. Alquiler: {alquiler_alertas}, Anticrético: {anticretico_alertas}")
    return Response({
        "status": 1, 
        "error": 0,
        "message": f"Proceso de alertas ejecutado. Alquiler: {alquiler_alertas}, Anticrético: {anticretico_alertas}."
    }, status=status.HTTP_200_OK)


# =========================================================
# 📢 NUEVA FUNCIÓN: AVISO INMEDIATO PARA ADMINISTRADOR
# =========================================================
# alertas/views.py (función aviso_inmediato_admin, CORREGIDA)

@api_view(['POST'])
#@permission_classes([IsAuthenticated, IsAdminUser])
def aviso_inmediato_admin(request):
    """
    Permite al administrador enviar un aviso inmediato a grupos específicos de usuarios,
    filtrando por el NOMBRE del grupo.
    """
    # =======================================================
    # 🔒 CANDADO SAAS: AVISOS MASIVOS
    # =======================================================
    usuario = request.user
    if not (usuario.is_staff or usuario.is_superuser):
        try:
            sub = usuario.suscripcion
            if not sub.esta_activa:
                 return Response({"error": "Tu suscripción ha vencido."}, status=403)
            
            # Verificamos si el plan tiene habilitado el módulo de alertas/comunicaciones
            if not sub.plan.permite_alertas:
                 return Response({
                     "error": "Tu plan actual no permite el envío de avisos masivos. Actualiza a PRO."
                 }, status=403)

        except Suscripcion.DoesNotExist:
             return Response({"error": "Necesitas una suscripción para enviar avisos."}, status=403)
    # =======================================================
    data = request.data
    # Los nombres de grupo vienen del frontend: ['cliente', 'agente', 'administrador']
    titulo_ingresado = data.get('titulo', '').strip()
    grupos_target = data.get('grupos', [])
    mensaje_cuerpo = data.get('mensaje')

    
    titulo_final = titulo_ingresado if titulo_ingresado else 'AVISO URGENTE'
    # ... (Validación de mensaje y grupos_target se mantiene igual)
    

    # Convertimos los nombres de grupo de frontend a minúsculas para un filtro robusto
    target_groups = [g.lower() for g in grupos_target if g.lower() in ['cliente', 'agente', 'administrador']]
    
    if not target_groups:
        return Response({
            "status": 0,
            "error": 1,
            "message": "Grupos inválidos. Use uno o más de: propietario, inquilino, agente, administrador."
        }, status=status.HTTP_400_BAD_REQUEST)

    # 1. CORRECCIÓN: FILTRAMOS POR EL NOMBRE DEL GRUPO ASIGNADO (grupo__nombre__in)
    usuarios_a_notificar = Usuario.objects.filter(
        grupo__nombre__in=target_groups, 
        is_active=True
    )
    
    alertas_enviadas = 0
    mensaje_completo = f"**{titulo_final.upper()}**: {mensaje_cuerpo}"
    
    # 2. Iterar y enviar la notificación a cada usuario
    for usuario in usuarios_a_notificar:
        # ... (El resto de la lógica de creación de alerta y envío se mantiene igual)
        
        # Se asume la existencia de un Contrato nulo para avisos generales
        # Se requiere que en AlertaModel se haya añadido 'aviso_admin'
        
        # Simplemente crearemos la alerta y la enviaremos
        try:
             alerta = AlertaModel.objects.create(
                contrato=None, 
                usuario_receptor=usuario,
                tipo_alerta='aviso_admin', 
                fecha_programada=timezone.now(),
                mensaje=mensaje_completo,
            )
             # Asumo que esta función está definida correctamente
             from .utils import enviar_notificacion_push 
             enviar_notificacion_push(alerta)
             alertas_enviadas += 1
        except Exception as e:
            # Manejar error si el usuario no tiene correo o token, pero continuar
            print(f"Error al enviar aviso a {usuario.username}: {e}")
            continue

    return Response({
        "status": 1, 
        "error": 0,
        "message": f"Aviso inmediato enviado exitosamente. Total de usuarios notificados: {alertas_enviadas}.",
        "detalles": f"Grupos objetivo: {', '.join(target_groups)}"
    }, status=status.HTTP_200_OK)

# ... (otras vistas como listar_mis_alertas)
@api_view(['PATCH'])
#@requiere_permiso("Alerta", "actualizar")
def marcar_estado_alerta(request, alerta_id):
    """
    Permite al usuario (Agente/Cliente) cambiar el estado de lectura (estado_visto)
    de una alerta a 'visto' o 'descartado'.

    Requiere en el body: {"estado_visto": "visto" | "descartado"}
    """
    USUARIO_AUTENTICADO = request.user
    NUEVO_ESTADO = request.data.get('estado_visto', '').lower()
    
    ESTADOS_VALIDOS = ['visto', 'descartado']

    if NUEVO_ESTADO not in ESTADOS_VALIDOS:
        return Response({
            "status": 0, "error": 1,
            "message": f"Estado de lectura inválido. Use uno de: {ESTADOS_VALIDOS}"
        }, status=status.HTTP_400_BAD_REQUEST)

    try:
        # 1. Buscar la alerta y asegurarse de que pertenece al usuario autenticado
        alerta = get_object_or_404(
            AlertaModel, 
            id=alerta_id, 
            usuario_receptor=USUARIO_AUTENTICADO
        )
        
        # 2. Actualizar el estado
        alerta.estado_visto = NUEVO_ESTADO
        alerta.save()

        # 3. Respuesta de éxito
        return Response({
            "status": 1, "error": 0,
            "message": f"Alerta {alerta_id} marcada como '{NUEVO_ESTADO}' correctamente.",
            "values": AlertaSerializer(alerta).data
        }, status=status.HTTP_200_OK)

    except AlertaModel.DoesNotExist:
        return Response({
            "status": 0, "error": 1,
            "message": "Alerta no encontrada o no pertenece al usuario."
        }, status=status.HTTP_404_NOT_FOUND)
    
    except Exception as e:
        return Response({
            "status": 0, "error": 1,
            "message": f"Error al procesar la solicitud: {str(e)}"
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    # alertas/views.py (Añadir esta función)

@api_view(['GET'])
# Asumo que la protección se hace en la capa superior (Admin/Agente)
# Si es para el cliente/agente logueado, basta con IsAuthenticated
def listar_mis_alertas(request):
    """
    Lista las alertas asociadas al usuario autenticado (Agente/Cliente)
    para la vista de Notificaciones del frontend.
    """
    if not request.user.is_authenticated:
        return Response({
            "status": 0,
            "error": 1,
            "message": "Usuario no autenticado."
        }, status=status.HTTP_401_UNAUTHORIZED)
    # =======================================================
    # 🔒 CANDADO SAAS: VISUALIZACIÓN DE ALERTAS
    # =======================================================
    # Solo aplicamos restricción si es Agente (los clientes/inquilinos siempre deberían ver sus avisos)
    if request.user.grupo and request.user.grupo.nombre.lower() == 'agente':
        if not (request.user.is_staff or request.user.is_superuser):
            try:
                sub = request.user.suscripcion
                if not sub.esta_activa:
                     # Opción A: Error
                     return Response({"message": "Suscripción vencida. Paga para ver tus alertas."}, status=403)
                     # Opción B (Más suave): Retornar lista vacía con mensaje
                     # return Response({"values": {"alertas": []}, "message": "Renueva tu plan"}, status=200)
                
                if not sub.plan.permite_alertas:
                     return Response({"message": "Tu plan no incluye el módulo de alertas."}, status=403)

            except Suscripcion.DoesNotExist:
                 return Response({"message": "Sin suscripción activa."}, status=403)
    # =======================================================
    try:
        # Esto ejecuta el chequeo de "ya corrió hoy" y genera las alertas si es necesario.
        ejecutar_generacion_alertas_diaria()
    except Exception as e:
        logger.error(f"Fallo al generar alertas durante el listado: {e}")
        # El proceso de listado debe continuar.
    # Filtrar solo las alertas destinadas al usuario logueado
    alertas = AlertaModel.objects.filter(
        usuario_receptor=request.user
    ).order_by('-fecha_programada')
    
    serializer = AlertaSerializer(alertas, many=True)
    
    return Response({
        "status": 1, 
        "error": 0,
        "message": f"LISTADO DE ALERTAS PARA {request.user.nombre}",
        "values": {"alertas": serializer.data}
    }, status=status.HTTP_200_OK)

@api_view(['GET'])
#@requiere_permiso("Alerta", "leer") # Solo usuarios con permiso de lectura en Alertas (Admin)
@permission_classes([IsAuthenticated])
def listar_alertas_admin(request):
    """
    Lista TODAS las alertas del sistema (para el Dashboard del Administrador).
    Permite filtros opcionales:
    ?estado=pendiente | enviado | fallido
    ?tipo=pago_alquiler | aviso_admin
    """
    estado_filtro = request.GET.get('estado')
    tipo_filtro = request.GET.get('tipo')
    
    # Base Query: Obtener todas las alertas
    # Usamos select_related para optimizar la consulta al acceder a Contrato y Usuario
    alertas = AlertaModel.objects.select_related('contrato', 'usuario_receptor').all()
    
    # Aplicar filtros
    if estado_filtro:
        alertas = alertas.filter(estado_envio=estado_filtro.lower())
    
    if tipo_filtro:
        alertas = alertas.filter(tipo_alerta=tipo_filtro.lower())
        
    # Ordenar por fecha de la más reciente a la más antigua
    alertas = alertas.order_by('-fecha_programada')
    
    serializer = AlertaSerializer(alertas, many=True)
    
    return Response({
        "status": 1, 
        "error": 0,
        "message": "LISTADO GENERAL DE ALERTAS DEL SISTEMA",
        "values": {"alertas": serializer.data}
    }, status=status.HTTP_200_OK)