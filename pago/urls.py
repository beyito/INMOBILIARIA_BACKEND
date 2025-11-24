# pago/urls.py

from django.urls import path
from .views import (
    # Flujo Cliente/Pasarela
    iniciar_pago_stripe,
    webhook_pasarela_confirmacion,
    
    # Flujo Admin/Manual
    registrar_pago_manual,
    gestionar_pago_manual,
    estado_cuenta_contrato_alquiler,
    # Consultas
    ListarPagosPorContrato,
    ObtenerDetallePago,
    simular_webhook_stripe,
    verificar_estado_pago
    
)

urlpatterns = [
    # ------------------ RUTAS DE CLIENTE/PASARELA ------------------
    # POST: Cliente autenticado inicia el proceso de pago electrónico con Stripe
    path('contratos/<int:contrato_id>/stripe/iniciar/', iniciar_pago_stripe, name='pago-iniciar-stripe'),
    
    # POST: Webhook de la pasarela (Sin autenticación de Django)
    path('webhook/confirmacion/', webhook_pasarela_confirmacion, name='pago-webhook-confirmacion'),
    
    # ------------------ RUTAS DE REGISTRO MANUAL (ADMIN/AGENTE) ------------------
    # POST: Admin/Agente sube un comprobante (Transferencia/QR)
    path('contratos/<int:contrato_id>/manual/', registrar_pago_manual, name='pago-registrar-manual'),

    # ------------------ RUTAS DE CONSULTA (CLIENTE/ADMIN) ------------------
    # GET: Lista todos los pagos de un contrato (ACCESO RESTRINGIDO)
    path('contratos/<int:contrato_id>/', ListarPagosPorContrato.as_view(), name='pago-listar-por-contrato'),
    
    # GET: Detalle de un pago
    path('detalle/<int:pago_id>/', ObtenerDetallePago.as_view(), name='pago-detalle'),
    
    # ------------------ RUTAS DE GESTIÓN (ADMIN EXCLUSIVO) ------------------
    # PATCH: Confirma o rechaza un pago manual pendiente
    path('gestion/<int:pago_id>/', gestionar_pago_manual, name='pago-gestionar-manual'),

    path('contrato/alquiler/<int:contrato_id>/estado-cuenta/', estado_cuenta_contrato_alquiler, name='estado-cuenta-alquiler'),
    path('verificar/<int:pago_id>', verificar_estado_pago, name='verificar-estado-pago'),
    path('simular-webhook/<int:pago_id>/', simular_webhook_stripe, name='simular-webhook'),
]