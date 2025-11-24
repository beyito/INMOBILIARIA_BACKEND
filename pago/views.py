# pago/views.py

from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated, IsAdminUser
from rest_framework.response import Response
from rest_framework import status
from rest_framework.generics import ListAPIView, RetrieveAPIView
from django.shortcuts import get_object_or_404
from django.db import transaction
from django.utils import timezone
from django.core.exceptions import PermissionDenied
from django.http import Http404
from django.conf import settings
from decimal import Decimal, InvalidOperation
import stripe
from django.conf import settings

stripe.api_key = settings.STRIPE_SECRET_KEY
# Importamos modelos y serializadores
from .models import Pago, ComprobantePago 
from .serializers import PagoSerializer, PagoGestionSerializer,ComprobantePagoSerializer
# Asumo que Contrato tiene el campo 'id_cliente' que apunta a 'Usuario'
from contrato.models import Contrato 


# -------------------------------------------------------------
# 🛠️ FUNCIÓN AUXILIAR
# -------------------------------------------------------------

def safe_decimal(value, default=Decimal('0.00')):
    """Convierte un valor a Decimal de forma segura."""
    if value is None or value == "":
        return default
    try:
        if isinstance(value, str):
            value = value.replace(",", "")
        return Decimal(str(value))
    except (ValueError, TypeError, InvalidOperation):
        return default


# =========================================================
# 1. 💰 FLUJO CLIENTE/PASARELA (Stripe)
# =========================================================


@api_view(["POST"])
def iniciar_pago_stripe(request, contrato_id):
    metodo = 'stripe'
    cliente_autenticado = request.user
    
    try:
        contrato = get_object_or_404(Contrato, id=contrato_id)

        monto_a_pagar = contrato.monto
        cliente_obligado = contrato.id_cliente

        if not monto_a_pagar or monto_a_pagar <= Decimal('0.00'):
            return Response({"error": "El monto del contrato es inválido."}, status=400)

        # 1. Crear registro local del pago PENDIENTE
        pago_pendiente = Pago.objects.create(
            contrato=contrato,
            cliente=cliente_obligado,
            monto_pagado=monto_a_pagar,
            metodo=metodo,
            estado='pendiente',
            referencia_transaccion="STRIPE_PENDING"
        )

        # 2. CREAR CHECKOUT SESSION REAL EN STRIPE
        checkout_session = stripe.checkout.Session.create(
            payment_method_types=['card'],
            mode='payment',
            line_items=[{
                "price_data": {
                    "currency": "usd",
                    "unit_amount": int(monto_a_pagar * 100),  # Stripe usa centavos
                    "product_data": {
                        "name": f"Pago de alquiler - Contrato {contrato.id}",
                    },
                },
                "quantity": 1,
            }],
            metadata={
                "pago_id": pago_pendiente.id,
                "contrato_id": contrato.id,
                "cliente_id": cliente_obligado.id,
            },
            success_url=f"{settings.FRONTEND_SUCCESS_URL}?session_id={{CHECKOUT_SESSION_ID}}",
            cancel_url=f"{settings.FRONTEND_CANCEL_URL}",
        )

        # Guardar referencia de Stripe en el pago
        pago_pendiente.referencia_transaccion = checkout_session.id
        pago_pendiente.save()

        return Response({
            "status": 1,
            "message": "Transacción iniciada correctamente.",
            "values": {
                "pago_id": pago_pendiente.id,
                "url_checkout": checkout_session.url
            }
        }, status=201)

    except Exception as e:
        return Response({"error": str(e)}, status=500)



@api_view(["POST"])
# NOTA: En la vida real, esta vista NO llevaría autenticación de usuario
def webhook_pasarela_confirmacion(request):
    """
    Endpoint de la pasarela de pago (Stripe, etc.) para confirmar el pago.
    """
    try:
        # Aquí se implementaría la verificación de la firma del evento de Stripe
        payload = request.data
        pago_id = payload.get('pago_id')
        status_pasarela = payload.get('status') 

        pago = get_object_or_404(Pago, id=pago_id)
        
        if status_pasarela == 'success':
            pago.estado = 'confirmado'
            pago.save()
            return Response({"message": "Pago confirmado y registrado."}, status=status.HTTP_200_OK)
        else:
            pago.estado = 'fallido'
            pago.save()
            return Response({"message": "Pago marcado como fallido."}, status=status.HTTP_200_OK)

    except Http404:
        return Response({"error": "Pago ID no encontrado."}, status=status.HTTP_404_NOT_FOUND)
    except Exception as e:
        return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


# =========================================================
# 2. 📝 FLUJO AGENTE/ADMIN (Registro de Pago Manual/QR)
# =========================================================

@api_view(["POST"])
@permission_classes([IsAdminUser]) # EXCLUSIVO para personal de administración
def registrar_pago_manual(request, contrato_id):
    """
    Admin/Agente registra un pago recibido por Transferencia o QR/Efectivo, subiendo un comprobante.
    """
    monto_ingresado = request.data.get('monto') 
    metodo = request.data.get('metodo')
    comprobante_archivo = request.FILES.get('comprobante')
    usuario_registro = request.user 
    
    if metodo not in ['transferencia', 'qr_efectivo'] or not comprobante_archivo:
        return Response({"error": "Método o comprobante inválido."}, status=status.HTTP_400_BAD_REQUEST)
    
    try:
        with transaction.atomic():
            contrato = get_object_or_404(Contrato, id=contrato_id)
            cliente_pagador = contrato.id_cliente
            monto_registrado = safe_decimal(monto_ingresado)
            
            if not cliente_pagador:
                 return Response({"error": "El contrato no tiene un cliente vinculado."}, status=status.HTTP_400_BAD_REQUEST)
                 
            # 1. Crear registro de PAGO
            pago = Pago.objects.create(
                contrato=contrato,
                cliente=cliente_pagador, 
                monto_pagado=monto_registrado, # MONTO REGISTRADO POR EL ADMIN
                metodo=metodo,
                estado='requiere_revision', 
            )
            
            # 2. Crear COMPROBANTE y guardar el archivo
            comprobante = ComprobantePago.objects.create(
                pago=pago,
                archivo_comprobante=comprobante_archivo,
                usuario_registro=usuario_registro,
                observaciones=request.data.get('observaciones', '')
            )
            
            return Response({
                "status": 1,
                "message": "Pago y comprobante registrados. Pendiente de confirmación.",
                "values": {"pago_id": pago.id, "comprobante_url": comprobante.archivo_comprobante.url}
            }, status=status.HTTP_201_CREATED)
            
    except Exception as e:
        return Response({"error": f"Error al procesar pago manual: {str(e)}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

# =========================================================
# 3. 📊 CONSULTAS Y GESTIÓN
# =========================================================

class ListarPagosPorContrato(ListAPIView):
    """Listar todos los pagos asociados a un contrato específico."""
    serializer_class = PagoSerializer
  #  permission_classes = [IsAuthenticated]

    def get_queryset(self):
        contrato_id = self.kwargs['contrato_id']
        usuario_autenticado = self.request.user
        
        try:
            contrato = get_object_or_404(Contrato, id=contrato_id)
        except Contrato.DoesNotExist:
            raise Http404
        es_dueno = (contrato.id_cliente.id == usuario_autenticado.id)
        
        # Permisos: Cliente del contrato O Usuario Staff/Admin
        if es_dueno or usuario_autenticado.is_staff:
            return Pago.objects.filter(contrato=contrato).select_related('cliente').prefetch_related('comprobante')
        
        raise PermissionDenied("No tiene permisos para ver los pagos de este contrato.")

class ObtenerDetallePago(RetrieveAPIView):
    """Obtener el detalle de un pago específico."""
    queryset = Pago.objects.all().select_related('cliente').prefetch_related('comprobante')
    serializer_class = PagoSerializer
    permission_classes = [IsAuthenticated]
    lookup_field = 'id' 
    lookup_url_kwarg = 'pago_id' 

    def get_object(self):
        obj = super().get_object()
        # Permisos: Cliente del pago O Usuario Staff/Admin
        if (obj.cliente == self.request.user) or self.request.user.is_staff:
            return obj
        raise PermissionDenied("No tiene permisos para ver el detalle de este pago.")


@api_view(["PATCH"])
@permission_classes([IsAdminUser]) # EXCLUSIVO para personal administrativo
def gestionar_pago_manual(request, pago_id):
    """Permite al Admin/Agente confirmar o rechazar un pago manual pendiente."""
    accion = request.data.get('accion')
    
    if accion not in ['confirmar', 'rechazar']:
        return Response({"error": "Acción inválida. Use 'confirmar' o 'rechazar'."}, status=status.HTTP_400_BAD_REQUEST)

    try:
        pago = get_object_or_404(Pago, id=pago_id)
        
        if pago.estado != 'requiere_revision':
            return Response({"error": f"El pago ya fue procesado y tiene estado: {pago.estado}"}, status=status.HTTP_400_BAD_REQUEST)
        
        with transaction.atomic():
            if accion == 'confirmar':
                pago.estado = 'confirmado'
                pago.referencia_transaccion = f"CONFIRMADO_MANUAL_{pago.id}"
                mensaje = "Pago confirmado exitosamente."

            elif accion == 'rechazar':
                pago.estado = 'fallido'
                pago.referencia_transaccion = f"RECHAZADO_MANUAL_{pago.id}"
                mensaje = "Pago rechazado."
            
            pago.save()
            
            serializer = PagoGestionSerializer(pago)
            return Response({"status": 1, "message": mensaje, "pago": serializer.data}, status=status.HTTP_200_OK)

    except Http404:
        return Response({"error": "Pago no encontrado."}, status=status.HTTP_404_NOT_FOUND)
    except Exception as e:
        return Response({"error": f"Error de gestión: {str(e)}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
@api_view(["GET"])
# @permission_classes([IsAuthenticated])
def estado_cuenta_contrato_alquiler(request, contrato_id):
    """
    Estado de cuenta exclusivo para contratos de alquiler
    El monto del contrato se considera como monto mensual de alquiler
    """
    try:
        # Buscar contrato específicamente de alquiler
        contrato = get_object_or_404(
            Contrato, 
            id=contrato_id, 
            id_cliente=request.user,
            tipo_contrato='alquiler'  # ✅ Solo alquileres
        )
        
        # Obtener todos los pagos del contrato (puede estar vacío)
        pagos = Pago.objects.filter(contrato=contrato)
        
        # Calcular total pagado (solo confirmados) - manejar caso vacío
        pagos_confirmados = pagos.filter(estado='confirmado')
        total_pagado = sum(
            pago.monto_pagado for pago in pagos_confirmados
        ) if pagos_confirmados.exists() else Decimal('0.00')
        
        # Pagos por estado
        pagos_pendientes = pagos.filter(estado__in=['pendiente', 'requiere_revision'])
        pagos_fallidos = pagos.filter(estado='fallido')
        
        # Calcular meses pagados (asumiendo que cada pago es un mes)
        meses_pagados = pagos_confirmados.count()
        
        return Response({
            "status": 1,
            "error": 0,
            "message": "ESTADO DE CUENTA - CONTRATO DE ALQUILER",
            "values": {
                "contrato_id": contrato.id,
                "inmueble_direccion": contrato.inmueble.direccion if contrato.inmueble else "No especificado",
                "inmueble_ciudad": contrato.inmueble.ciudad if contrato.inmueble else "No especificado",
                "fecha_inicio": contrato.fecha_inicio,
                "fecha_fin": contrato.fecha_fin,
                "monto_mensual": contrato.monto,  # ✅ Monto mensual de alquiler
                "total_pagado": total_pagado,
                "saldo_pendiente": max(contrato.monto - total_pagado, Decimal('0.00')),
                "meses_pagados": meses_pagados,
                "resumen_estados": {
                    "confirmados": pagos_confirmados.count(),
                    "pendientes": pagos_pendientes.count(),
                    "fallidos": pagos_fallidos.count(),
                    "total": pagos.count()
                },
                "pagos_confirmados": PagoSerializer(pagos_confirmados, many=True).data,
                "pagos_pendientes": PagoSerializer(pagos_pendientes, many=True).data,
                "pagos_fallidos": PagoSerializer(pagos_fallidos, many=True).data,
                "proximo_vencimiento": calcular_proximo_vencimiento(contrato)  # Función auxiliar
            }
        })
        
    except Http404:
        return Response({
            "status": 0,
            "error": 1,
            "message": "Contrato de alquiler no encontrado",
            "values": {}
        }, status=status.HTTP_404_NOT_FOUND)
    except PermissionDenied:
        return Response({
            "status": 0,
            "error": 1,
            "message": "No tienes permisos para ver este contrato",
            "values": {}
        }, status=status.HTTP_403_FORBIDDEN)
    except Exception as e:
        return Response({
            "status": 0,
            "error": 1,
            "message": f"Error al cargar estado de cuenta: {str(e)}",
            "values": {}
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


# Función auxiliar para calcular próximo vencimiento
def calcular_proximo_vencimiento(contrato):
    """
    Calcula la fecha del próximo vencimiento basado en los pagos realizados
    """
    if not contrato.fecha_inicio:
        return None
    
    # Obtener el último pago confirmado
    ultimo_pago = Pago.objects.filter(
        contrato=contrato, 
        estado='confirmado'
    ).order_by('-fecha_pago').first()
    
    if ultimo_pago:
        # Si hay pagos, el próximo vencimiento es un mes después del último pago
        return ultimo_pago.fecha_pago + timezone.timedelta(days=30)
    else:
        # Si no hay pagos, el próximo vencimiento es la fecha de inicio
        return contrato.fecha_inicio
    
@api_view(["GET"])
@permission_classes([IsAuthenticated])
def verificar_estado_pago(request, pago_id):
    """
    Verifica el estado detallado de un pago específico
    """
    try:
        pago = get_object_or_404(Pago, id=pago_id)
        
        # Verificar permisos
        if pago.cliente != request.user and not request.user.is_staff:
            raise PermissionDenied("No tienes permisos para ver este pago")
        
        # Información adicional según el estado
        estado_info = {
            'pendiente': {
                'mensaje': 'Pago pendiente de procesar',
                'siguientes_pasos': ['Espere confirmación', 'Contacte soporte si demora más de 24h']
            },
            'confirmado': {
                'mensaje': 'Pago confirmado exitosamente',
                'siguientes_pasos': ['Pago procesado correctamente']
            },
            'fallido': {
                'mensaje': 'Pago fallido o rechazado',
                'siguientes_pasos': ['Intente nuevamente', 'Contacte soporte si el problema persiste']
            },
            'requiere_revision': {
                'mensaje': 'Pago en revisión manual',
                'siguientes_pasos': ['El administrador revisará su comprobante', 'Puede tomar hasta 48 horas']
            }
        }
        
        serializer = PagoSerializer(pago)
        
        return Response({
            "pago": serializer.data,
            "estado_detallado": estado_info.get(pago.estado, {'mensaje': 'Estado desconocido'}),
            "tiempo_transcurrido": f"{(timezone.now() - pago.fecha_pago).days} días"
        })
        
    except Http404:
        return Response({"error": "Pago no encontrado"}, status=status.HTTP_404_NOT_FOUND)

@api_view(["POST"])
@permission_classes([IsAuthenticated])
def simular_webhook_stripe(request, pago_id):
    """
    Endpoint temporal para simular el webhook de Stripe en desarrollo
    """
    try:
        pago = get_object_or_404(Pago, id=pago_id)
        print(f"🔔 Simulando webhook para Pago ID: {pago_id}, Usuario: {request.user.id}")
        
        # Verificar que el usuario tenga permisos
        if pago.cliente != request.user:
            return Response({
                "status": 0,
                "error": 1,
                "message": "No tienes permisos para esta acción"
            }, status=403)
        
        with transaction.atomic():
            # Simular pago exitoso
            pago.estado = 'confirmado'
            pago.referencia_transaccion = f"STRIPE_SIMULATED_{pago.id}_{timezone.now().strftime('%Y%m%d%H%M%S')}"
            
            print("✅ Estado y referencia actualizados")
            
            # Crear comprobante automático de manera segura
            try:
                comprobante = ComprobantePago.objects.create(
                    pago=pago,
                    usuario_registro=request.user,
                    observaciones="Pago simulado para testing. Comprobante generado automáticamente."
                )
                print(f"✅ Comprobante creado: {comprobante.id}")
            except Exception as e:
                print(f"⚠️ Error creando comprobante: {e}")
                # Continuar sin comprobante si hay error
                comprobante = None
            
            pago.save()
            print("✅ Pago guardado en base de datos")
            
            # Preparar respuesta
            response_data = {
                "status": 1,
                "error": 0,
                "message": "Pago simulado exitosamente. Comprobante generado.",
                "values": {
                    "pago_id": pago.id,
                    "nuevo_estado": pago.estado,
                    "referencia": pago.referencia_transaccion
                }
            }
            
            # Agregar comprobante solo si se creó exitosamente
            if comprobante:
                response_data["values"]["comprobante_id"] = comprobante.id
            
            print("📤 Enviando respuesta...")
            return Response(response_data, status=status.HTTP_200_OK)
            
    except Http404:
        print("❌ Pago no encontrado")
        return Response({
            "status": 0,
            "error": 1,
            "message": "Pago no encontrado"
        }, status=status.HTTP_404_NOT_FOUND)
        
    except Exception as e:
        print(f"💥 Error en simulación: {str(e)}")
        import traceback
        print(f"📋 Traceback completo:")
        traceback.print_exc()
        
        return Response({
            "status": 0,
            "error": 1,
            "message": f"Error en simulación: {str(e)}"
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)