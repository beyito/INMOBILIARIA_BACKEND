# suscripciones/views.py

from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.response import Response
from rest_framework import status
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.conf import settings
import stripe

from .models import Plan, Suscripcion
from .serializers import PlanSerializer, SuscripcionSerializer
from rest_framework.permissions import IsAdminUser
from usuario.models import Usuario
from utils.encrypted_logger import registrar_accion # Para auditoría
stripe.api_key = settings.STRIPE_SECRET_KEY
@api_view(['POST'])
@permission_classes([IsAdminUser]) # Solo Admins pueden tocar esto
def admin_asignar_plan_manual(request):
    """
    Permite al Administrador asignar o cambiar un plan a cualquier usuario.
    Body:
    {
        "usuario_id": 5,
        "plan_id": 2,
        "dias_extra": 30 (opcional, por defecto usa la duración del plan),
        "estado": "activa" (opcional)
    }
    """
    usuario_id = request.data.get('usuario_id')
    plan_id = request.data.get('plan_id')
    dias_extra = request.data.get('dias_extra')
    estado_manual = request.data.get('estado', 'activa')

    if not usuario_id or not plan_id:
        return Response({"error": "Faltan datos (usuario_id, plan_id)"}, status=400)

    try:
        usuario = Usuario.objects.get(id=usuario_id)
        plan = get_object_or_404(Plan, id=plan_id)

        # Buscar suscripción existente o crear una nueva
        suscripcion, created = Suscripcion.objects.get_or_create(usuario=usuario, defaults={'plan': plan})

        # Actualizar datos
        suscripcion.plan = plan
        suscripcion.estado = estado_manual
        
        # Lógica de fechas
        suscripcion.fecha_inicio = timezone.now()
        
        # Si el admin especifica días, los usamos, si no, usamos los del plan
        dias_duracion = int(dias_extra) if dias_extra else plan.duracion_dias
        suscripcion.fecha_fin = timezone.now() + timedelta(days=dias_duracion)
        
        # Limpiar referencia de Stripe si es manual (para evitar confusiones)
        suscripcion.stripe_session_id = f"MANUAL_ADMIN_{request.user.id}"
        
        suscripcion.save()

        # 📝 AUDITORÍA
        registrar_accion(
            usuario=request.user,
            accion=f"Asignó manualmente el plan '{plan.nombre}' al usuario {usuario.username} (ID: {usuario.id})",
            ip=request.META.get("REMOTE_ADDR")
        )

        return Response({
            "status": 1,
            "message": f"Plan {plan.nombre} asignado correctamente a {usuario.username}",
            "values": SuscripcionSerializer(suscripcion).data
        })

    except Usuario.DoesNotExist:
        return Response({"error": "Usuario no encontrado"}, status=404)
    except Exception as e:
        return Response({"error": str(e)}, status=500)


@api_view(['GET'])
@permission_classes([IsAdminUser])
def admin_listar_todas_suscripciones(request):
    """
    Lista todas las suscripciones del sistema con datos del usuario.
    """
    # Optimizamos la consulta trayendo datos del usuario y del plan
    suscripciones = Suscripcion.objects.select_related('usuario', 'plan').all().order_by('-fecha_inicio')
    
    # Podrías crear un serializer específico que incluya el nombre del usuario
    # Pero aquí lo hacemos rápido agregando el dato manualmente o usando el serializer existente
    
    data = []
    for sub in suscripciones:
        item = SuscripcionSerializer(sub).data
        # Agregamos info extra del usuario para que el admin sepa quién es
        item['usuario_nombre'] = sub.usuario.nombre
        item['usuario_email'] = sub.usuario.correo
        item['usuario_rol'] = sub.usuario.grupo.nombre if sub.usuario.grupo else "N/A"
        data.append(item)

    return Response({
        "status": 1,
        "message": "Listado total de suscripciones",
        "values": data
    })

@api_view(['PATCH'])
@permission_classes([IsAdminUser])
def admin_cancelar_suscripcion(request, usuario_id):
    """
    Revoca el acceso inmediatamente a un usuario.
    """
    try:
        usuario = Usuario.objects.get(id=usuario_id)
        sub = usuario.suscripcion # Acceso directo gracias al OneToOne
        
        sub.estado = 'cancelada'
        sub.fecha_fin = timezone.now() # Vence hoy mismo
        sub.save()
        
        registrar_accion(
            usuario=request.user,
            accion=f"Canceló la suscripción del usuario {usuario.username}",
            ip=request.META.get("REMOTE_ADDR")
        )

        return Response({"status": 1, "message": "Suscripción cancelada."})

    except Usuario.DoesNotExist:
        return Response({"error": "Usuario no encontrado"}, status=404)
    except Suscripcion.DoesNotExist:
         return Response({"error": "El usuario no tiene suscripción para cancelar"}, status=404)
# 1. LISTAR PLANES (Público)
@api_view(['GET'])
@permission_classes([AllowAny])
def listar_planes(request):
    planes = Plan.objects.filter(is_active=True)
    serializer = PlanSerializer(planes, many=True)
    return Response({
        "status": 1,
        "message": "Planes disponibles",
        "values": serializer.data
    })

# 2. INICIAR PAGO STRIPE (Generar Link)
@api_view(['POST'])
@permission_classes([IsAuthenticated])
def iniciar_pago_suscripcion(request):
    """
    Body: { "plan_id": 2 }
    """
    usuario = request.user
    plan_id = request.data.get('plan_id')
    
    if not plan_id:
        return Response({"error": "Falta plan_id"}, status=400)

    plan = get_object_or_404(Plan, id=plan_id)

    # Crear o buscar suscripción pendiente
    suscripcion, created = Suscripcion.objects.get_or_create(usuario=usuario, defaults={'plan': plan})
    
    # Actualizamos el plan por si el usuario cambió de opinión
    suscripcion.plan = plan
    suscripcion.estado = 'pendiente'
    suscripcion.save()

    try:
        # 🛠️ TRUCO PARA NO TOCAR EL .ENV
        # Tu .env dice: http://localhost:5173/success
        # Le quitamos el "/success" para quedarnos solo con el dominio
        base_frontend = settings.FRONTEND_SUCCESS_URL.replace('/success', '') 
        
        # Construimos las URLs específicas para SAAS
        SUCCESS_URL = f"{base_frontend}/home/suscripcion/exito"
        CANCEL_URL = f"{base_frontend}/home/planes"

        # Crear sesión de Stripe
        session = stripe.checkout.Session.create(
            payment_method_types=['card'],
            line_items=[{
                'price_data': {
                    'currency': 'usd', # Cambia a 'bob' si tu cuenta lo permite
                    'product_data': {
                        'name': f"Suscripción {plan.nombre}",
                        'description': plan.descripcion,
                    },
                    'unit_amount': int(plan.precio * 100), # Centavos
                },
                'quantity': 1,
            }],
            mode='payment', # Pago único
            success_url=SUCCESS_URL,
            cancel_url=CANCEL_URL,
            metadata={
                'usuario_id': usuario.id,
                'plan_id': plan.id,
                'tipo': 'suscripcion_saas'
            }
        )

        # Guardar referencia
        suscripcion.stripe_session_id = session.id
        suscripcion.save()

        return Response({
            "status": 1,
            "message": "Sesión de pago creada",
            "values": {"url_checkout": session.url}
        })

    except Exception as e:
        return Response({"error": str(e)}, status=500)


# 3. CONFIRMACIÓN (WEBHOOK SIMULADO)
@api_view(['POST'])
@permission_classes([IsAuthenticated])
def confirmar_pago_suscripcion_simulado(request):
    """
    Activa el plan inmediatamente al volver de Stripe
    """
    usuario = request.user
    
    try:
        suscripcion = Suscripcion.objects.get(usuario=usuario)
        
        # Simular éxito
        suscripcion.estado = 'activa'
        suscripcion.fecha_inicio = timezone.now()
        suscripcion.fecha_fin = suscripcion.calcular_fecha_fin() 
        suscripcion.save()
        
        return Response({
            "status": 1,
            "message": f"¡Plan {suscripcion.plan.nombre} activado exitosamente!",
            "values": SuscripcionSerializer(suscripcion).data
        })

    except Suscripcion.DoesNotExist:
        return Response({"error": "No hay suscripción pendiente"}, status=404)


# 4. VER MI ESTADO
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def mi_suscripcion(request):
    try:
        sub = request.user.suscripcion
        return Response({
            "status": 1,
            "values": SuscripcionSerializer(sub).data
        })
    except Suscripcion.DoesNotExist:
        return Response({"status": 0, "values": None})