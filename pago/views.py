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
#@permission_classes([IsAuthenticated])
def iniciar_pago_stripe(request, contrato_id):
    """
    Cliente autenticado inicia el proceso de pago electrónico con Stripe.
    El MONTO y el CLIENTE se obtienen del Contrato.
    """
    metodo = 'stripe'
    cliente_autenticado = request.user
    
    if not metodo:
        return Response({"error": "Faltan datos: método es requerido."}, status=status.HTTP_400_BAD_REQUEST)
    
    try:
        contrato = get_object_or_404(Contrato, id=contrato_id)
        
        # 🚨 Obtener Monto y Cliente Obligado del Contrato
        monto_a_pagar = contrato.monto
        cliente_obligado = contrato.id_cliente
        
        if not monto_a_pagar or monto_a_pagar <= Decimal('0.00'):
            return Response({"error": "El monto a pagar del contrato es inválido."}, status=status.HTTP_400_BAD_REQUEST)
        
        # Permiso: Verificar que el usuario autenticado es el cliente obligado
        #if cliente_obligado != cliente_autenticado:
         #   raise PermissionDenied("No tienes permiso para pagar este contrato.")
            
        # 1. Crear registro de PAGO en estado PENDIENTE
        pago_pendiente = Pago.objects.create(
            contrato=contrato,
            cliente=cliente_obligado,       
            monto_pagado=monto_a_pagar,     
            metodo=metodo,
            estado='pendiente',
            referencia_transaccion="STRIPE_TEMP_ID" # Placeholder
        )
        
        # 2. Simulación de respuesta de pasarela: retornar URL de pago
        # En la vida real: Inicializar Stripe con settings.STRIPE_SECRET_KEY y crear Checkout Session
        url_pasarela = f"https://stripe.com/checkout?pago_id={pago_pendiente.id}" 

        return Response({
            "status": 1,
            "message": "Transacción iniciada. Redirigiendo a pasarela.",
            "values": {"pago_id": pago_pendiente.id, "url_checkout": url_pasarela}
        }, status=status.HTTP_201_CREATED)
        
    except PermissionDenied as e:
        return Response({"error": str(e)}, status=status.HTTP_403_FORBIDDEN)
    except Exception as e:
        return Response({"error": f"Error al iniciar pago: {str(e)}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


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