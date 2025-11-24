# ventas/views.py
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from rest_framework import status, permissions
from django.conf import settings
from reportlab.pdfgen import canvas
from django.http import HttpResponse
from .models import VentaInmueble, AlquilerInmueble

from inmobiliaria.permissions import (
    requiere_lectura,
    requiere_creacion,
    requiere_actualizacion,
    requiere_eliminacion,
    requiere_permiso
)

from .serializers import VentaInmuebleSerializer, AlquilerInmuebleSerializer
from inmueble.models import InmuebleModel, AnuncioModel

import stripe
stripe.api_key = settings.STRIPE_SECRET_KEY


# ======================================================================
# 1️⃣ CREAR ORDEN DE PAGO STRIPE
# ======================================================================
@api_view(["POST"])
@permission_classes([permissions.IsAuthenticated])
@requiere_permiso("ventas", "crear")
def crear_orden_stripe(request):
    try:
        inmueble_id = request.data.get("inmueble_id")
        inmueble = InmuebleModel.objects.filter(id=inmueble_id).first()

        if not inmueble:
            return Response({
                "status": 0,
                "error": 1,
                "message": "INMUEBLE NO ENCONTRADO"
            }, status=404)

        # ✅ 1. Crear primero la venta
        venta = VentaInmueble.objects.create(
            comprador=request.user,
            inmueble=inmueble,
            monto=inmueble.precio,
            metodo_pago="stripe",
            estado_pago="pendiente"
        )

        # ✅ 2. Crear la sesión de Stripe ya con venta.id
        session = stripe.checkout.Session.create(
            payment_method_types=['card'],
            line_items=[{
                'price_data': {
                    'currency': 'bob',
                    'product_data': {'name': inmueble.titulo},
                    'unit_amount': int(float(inmueble.precio) * 100),
                },
                'quantity': 1,
            }],
            mode='payment',
            success_url=f"{settings.FRONTEND_SUCCESS_URL}?venta_id={venta.id}",
            cancel_url=settings.FRONTEND_CANCEL_URL,
            customer_email=request.user.correo,
            client_reference_id=str(venta.id),  # opcional pero útil
        )

        # Guardar ID de transacción de Stripe
        venta.transaccion_id = session.id
        venta.save()

        return Response({
            "status": 1,
            "error": 0,
            "message": "ORDEN STRIPE CREADA",
            "values": {
                "checkout_url": session.url,
                "venta_id": venta.id
            }
        }, status=200)

    except Exception as e:
        print("ERROR EN CREAR ORDEN:", e)
        return Response({
            "status": 0,
            "error": 1,
            "message": "ERROR AL CREAR ORDEN",
            "values": str(e)
        }, status=500)


# ======================================================================
# 2️⃣ CONFIRMAR PAGO (webhook o pruebas)
# ======================================================================
@api_view(["POST"])
def confirmar_pago(request):
    try:
        session_id = request.data.get("session_id")

        venta = VentaInmueble.objects.filter(transaccion_id=session_id).first()
        if not venta:
            return Response({
                "status": 0,
                "error": 1,
                "message": "VENTA NO ENCONTRADA"
            }, status=404)

        venta.estado_pago = "pagado"
        venta.save()

        # 🚨 YA NO SE USA estado_inmueble → Usamos ANUNCIO
        anuncio = getattr(venta.inmueble, "anuncio", None)
        if anuncio:
            anuncio.estado = "vendido"
            anuncio.is_active = False
            anuncio.save()

        return Response({
            "status": 1,
            "error": 0,
            "message": "PAGO CONFIRMADO",
            "values": VentaInmuebleSerializer(venta).data
        }, status=200)

    except Exception as e:
        return Response({
            "status": 0,
            "error": 1,
            "message": "ERROR AL CONFIRMAR PAGO",
            "values": str(e)
        }, status=500)



# ======================================================================
# 3️⃣ REGISTRAR VENTA EN EFECTIVO
# ======================================================================
@api_view(["POST"])
@permission_classes([permissions.IsAuthenticated])
@requiere_creacion("ventas")
def venta_efectivo(request):
    try:
        inmueble_id = request.data.get("inmueble_id")
        inmueble = InmuebleModel.objects.filter(id=inmueble_id).first()

        if not inmueble:
            return Response({
                "status": 0,
                "error": 1,
                "message": "INMUEBLE NO ENCONTRADO"
            }, status=404)

        venta = VentaInmueble.objects.create(
            comprador=request.user,
            inmueble=inmueble,
            monto=inmueble.precio,
            metodo_pago="efectivo",
            estado_pago="pagado"
        )

        # 🚨 YA NO USAMOS estado_inmueble → Cambiar anuncio
        anuncio = getattr(inmueble, "anuncio", None)
        if anuncio:
            anuncio.estado = "vendido"
            anuncio.is_active = False
            anuncio.save()

        return Response({
            "status": 1,
            "error": 0,
            "message": "VENTA EN EFECTIVO REGISTRADA",
            "values": VentaInmuebleSerializer(venta).data
        }, status=201)

    except Exception as e:
        return Response({
            "status": 0,
            "error": 1,
            "message": "ERROR AL REGISTRAR VENTA EN EFECTIVO",
            "values": str(e)
        }, status=500)



# ======================================================================
# 4️⃣ HISTORIAL DE COMPRAS (cliente)
# ======================================================================
@api_view(["GET"])
# @requiere_lectura("ventas")
def historial_compras(request):
    try:
        ventas = VentaInmueble.objects.filter(comprador=request.user)

        return Response({
            "status": 1,
            "error": 0,
            "message": "HISTORIAL OBTENIDO",
            "values": VentaInmuebleSerializer(ventas, many=True).data
        }, status=200)

    except Exception as e:
        return Response({
            "status": 0,
            "error": 1,
            "message": "ERROR AL OBTENER HISTORIAL",
            "values": str(e)
        }, status=500)



# ======================================================================
# 5️⃣ HISTORIAL GENERAL (administrador)
# ======================================================================
@api_view(["GET"])
# @requiere_lectura("ventas")
def historial_general(request):
    try:
        if not request.user.grupo or request.user.grupo.nombre != "administrador":
            return Response({
                "status": 2,
                "error": 1,
                "message": "ACCESO SOLO PARA ADMINISTRADORES"
            }, status=403)

        ventas = VentaInmueble.objects.all()

        return Response({
            "status": 1,
            "error": 0,
            "message": "HISTORIAL GENERAL OBTENIDO",
            "values": VentaInmuebleSerializer(ventas, many=True).data
        })

    except Exception as e:
        return Response({
            "status": 0,
            "error": 1,
            "message": "ERROR AL OBTENER HISTORIAL GENERAL",
            "values": str(e)
        }, status=500)

# ======================================================================
#  WEBHOOK DE STRIPE
# ======================================================================
@api_view(["POST"])
@permission_classes([permissions.AllowAny])
def stripe_webhook(request):
    payload = request.body
    sig_header = request.META.get("HTTP_STRIPE_SIGNATURE")
    endpoint_secret = settings.STRIPE_WEBHOOK_SECRET

    try:
        event = stripe.Webhook.construct_event(
            payload, sig_header, endpoint_secret
        )
    except ValueError:
        return Response(status=400)
    except stripe.error.SignatureVerificationError:
        return Response(status=400)

    event_type = event["type"]

    # Ignorar todos los eventos excepto checkout.session.completed
    if event_type != "checkout.session.completed":
        return Response(status=200)

    # Procesar el evento de pago completado
    session = event["data"]["object"]
    session_id = session.get("id")

    venta = VentaInmueble.objects.filter(transaccion_id=session_id).first()
    if venta:
        venta.estado_pago = "pagado"
        venta.save()

        anuncio = getattr(venta.inmueble, "anuncio", None)
        if anuncio:
            anuncio.estado = "vendido"
            anuncio.is_active = False
            anuncio.save()

    return Response(status=200)
@api_view(["GET"])
@permission_classes([permissions.IsAuthenticated])
def venta_detalle(request, pk):
    venta = VentaInmueble.objects.filter(id=pk, comprador=request.user).first()

    if not venta:
        return Response({
            "status": 0,
            "error": 1,
            "message": "VENTA NO ENCONTRADA"
        }, status=404)

    return Response({
        "status": 1,
        "error": 0,
        "message": "DETALLE OBTENIDO",
        "values": VentaInmuebleSerializer(venta).data
    })

@api_view(["GET"])
@permission_classes([permissions.AllowAny]) 
def comprobante_venta(request, pk):
    # Permitir token por query params para descargas
    token = request.query_params.get("token")
    if token:
        from rest_framework.authtoken.models import Token
        try:
            user = Token.objects.get(key=token).user
            request.user = user
        except Token.DoesNotExist:
            return Response({"detail": "Token inválido"}, status=401)
    venta = VentaInmueble.objects.filter(id=pk, comprador=request.user).first()

    if not venta:
        return Response({"message": "VENTA NO ENCONTRADA"}, status=404)

    response = HttpResponse(content_type="application/pdf")
    response["Content-Disposition"] = f'attachment; filename="comprobante_venta_{pk}.pdf"'

    c = canvas.Canvas(response)
    c.setFont("Helvetica-Bold", 20)
    c.drawString(180, 800, "COMPROBANTE DE PAGO")

    c.setFont("Helvetica", 12)
    c.drawString(50, 760, f"Cliente: {venta.comprador.nombre}")
    c.drawString(50, 740, f"Inmueble: {venta.inmueble.titulo}")
    c.drawString(50, 720, f"Dirección: {venta.inmueble.direccion}")
    c.drawString(50, 700, f"Monto pagado: {venta.monto} BOB")
    c.drawString(50, 680, f"Método de pago: {venta.metodo_pago}")
    c.drawString(50, 660, f"ID de transacción: {venta.transaccion_id}")
    c.drawString(50, 640, f"Fecha: {venta.fecha.strftime('%d/%m/%Y %H:%M')}")

    c.line(50, 600, 550, 600)
    c.drawString(50, 580, "Gracias por confiar en nuestra inmobiliaria.")
    c.drawString(50, 560, "Un agente se contactará contigo en breve.")

    c.showPage()
    c.save()
    return response


# ALQUILER

# @api_view(["POST"])
# @permission_classes([permissions.IsAuthenticated])
# @requiere_permiso("alquileres", "crear")
# def crear_orden_alquiler_stripe(request):
#     try:
#         inmueble_id = request.data.get("inmueble_id")
#         inmueble = InmuebleModel.objects.filter(id=inmueble_id).first()

#         if not inmueble:
#             return Response({
#                 "status": 0,
#                 "error": 1,
#                 "message": "INMUEBLE NO ENCONTRADO"
#             }, status=404)

#         # ⚠ Precio mensual del alquiler
#         monto = inmueble.precio  

#         # 1️⃣ Crear registro de ALQUILER (pendiente)
#         alquiler = AlquilerInmueble.objects.create(
#             arrendatario=request.user,
#             inmueble=inmueble,
#             monto_mensual=monto,
#             metodo_pago="stripe",
#             estado_pago="pendiente",
#         )

#         # 2️⃣ Crear sesión Stripe
#         session = stripe.checkout.Session.create(
#             payment_method_types=['card'],
#             line_items=[{
#                 'price_data': {
#                     'currency': 'bob',
#                     'product_data': {'name': f"Alquiler - {inmueble.titulo}"},
#                     'unit_amount': int(float(monto) * 100),
#                 },
#                 'quantity': 1,
#             }],
#             mode='payment',
#             success_url=f"{settings.FRONTEND_SUCCESS_URL}?alquiler_id={alquiler.id}",
#             cancel_url=settings.FRONTEND_CANCEL_URL,
#             customer_email=request.user.correo,
#             client_reference_id=str(alquiler.id),
#         )

#         alquiler.transaccion_id = session.id
#         alquiler.save()

#         return Response({
#             "status": 1,
#             "error": 0,
#             "message": "ORDEN DE ALQUILER CREADA",
#             "values": {
#                 "checkout_url": session.url,
#                 "alquiler_id": alquiler.id
#             }
#         }, status=200)

#     except Exception as e:
#         return Response({
#             "status": 0,
#             "error": 1,
#             "message": "ERROR AL CREAR ORDEN",
#             "values": str(e)
#         }, status=500)

# @api_view(["POST"])
# def confirmar_pago_alquiler(request):
#     try:
#         session_id = request.data.get("session_id")

#         alquiler = AlquilerInmueble.objects.filter(transaccion_id=session_id).first()
#         if not alquiler:
#             return Response({
#                 "status": 0,
#                 "error": 1,
#                 "message": "ALQUILER NO ENCONTRADO"
#             }, status=404)

#         # Marcar pagado
#         alquiler.estado_pago = "pagado"
#         alquiler.save()

#         # ⚠ Cambiar estado del anuncio a "alquilado"
#         anuncio = getattr(alquiler.inmueble, "anuncio", None)
#         if anuncio:
#             anuncio.estado = "alquilado"
#             anuncio.is_active = False
#             anuncio.save()

#         return Response({
#             "status": 1,
#             "error": 0,
#             "message": "ALQUILER PAGADO",
#             "values": AlquilerInmuebleSerializer(alquiler).data
#         }, status=200)

#     except Exception as e:
#         return Response({
#             "status": 0,
#             "error": 1,
#             "message": "ERROR AL CONFIRMAR PAGO",
#             "values": str(e)
#         }, status=500)

# @api_view(["POST"])
# @permission_classes([permissions.IsAuthenticated])
# @requiere_creacion("alquileres")
# def alquiler_efectivo(request):
#     try:
#         inmueble_id = request.data.get("inmueble_id")
#         inmueble = InmuebleModel.objects.filter(id=inmueble_id).first()

#         if not inmueble:
#             return Response({
#                 "status": 0,
#                 "error": 1,
#                 "message": "INMUEBLE NO ENCONTRADO"
#             }, status=404)

#         # Precio mensual
#         monto = inmueble.precio

#         alquiler = AlquilerInmueble.objects.create(
#             arrendatario=request.user,
#             inmueble=inmueble,
#             monto_mensual=monto,
#             metodo_pago="efectivo",
#             estado_pago="pagado",
#         )

#         # Cambiar anuncio
#         anuncio = getattr(inmueble, "anuncio", None)
#         if anuncio:
#             anuncio.estado = "alquilado"
#             anuncio.is_active = False
#             anuncio.save()

#         return Response({
#             "status": 1,
#             "error": 0,
#             "message": "ALQUILER EFECTIVO REGISTRADO",
#             "values": AlquilerInmuebleSerializer(alquiler).data
#         }, status=201)

#     except Exception as e:
#         return Response({
#             "status": 0,
#             "error": 1,
#             "message": "ERROR AL REGISTRAR ALQUILER",
#             "values": str(e)
#         }, status=500)

# @api_view(["GET"])
# def historial_alquileres(request):
#     try:
#         alquileres = AlquilerInmueble.objects.filter(arrendatario=request.user)

#         return Response({
#             "status": 1,
#             "error": 0,
#             "message": "HISTORIAL DE ALQUILERES OBTENIDO",
#             "values": AlquilerInmuebleSerializer(alquileres, many=True).data
#         }, status=200)

#     except Exception as e:
#         return Response({
#             "status": 0,
#             "error": 1,
#             "message": "ERROR AL OBTENER HISTORIAL",
#             "values": str(e)
#         }, status=500)

# @api_view(["GET"])
# def historial_general_alquileres(request):
#     try:
#         if not request.user.grupo or request.user.grupo.nombre != "administrador":
#             return Response({
#                 "status": 2,
#                 "error": 1,
#                 "message": "ACCESO SOLO PARA ADMINISTRADORES"
#             }, status=403)

#         alquileres = AlquilerInmueble.objects.all()

#         return Response({
#             "status": 1,
#             "error": 0,
#             "message": "HISTORIAL GENERAL OBTENIDO",
#             "values": AlquilerInmuebleSerializer(alquileres, many=True).data
#         }, status=200)

#     except Exception as e:
#         return Response({
#             "status": 0,
#             "error": 1,
#             "message": "ERROR AL OBTENER HISTORIAL GENERAL",
#             "values": str(e)
#         }, status=500)
