# ventas/urls.py
from django.urls import path
from .views import (
    crear_orden_stripe,
    confirmar_pago,
    venta_efectivo,
    historial_compras,
    historial_general,
    stripe_webhook,
    venta_detalle,
    comprobante_venta,
)

urlpatterns = [
    # Stripe
    path("stripe/crear-orden/", crear_orden_stripe, name="crear_orden_stripe"),
    path("stripe/confirmar-pago/", confirmar_pago, name="confirmar_pago"),

    # Ventas en efectivo
    path("efectivo/", venta_efectivo, name="venta_efectivo"),

    # Historiales
    path("historial/compras/", historial_compras, name="historial_compras"),
    path("historial/general/", historial_general, name="historial_general"),

    path("stripe/webhook/", stripe_webhook, name="stripe_webhook"),
    path("detalle/<int:pk>/", venta_detalle, name="venta_detalle"),
    path("comprobante/<int:pk>/", comprobante_venta, name="comprobante_venta"),

]
