from django.urls import path
from . import views

urlpatterns = [
    path('planes/', views.listar_planes, name='listar_planes'),
    path('pagar/', views.iniciar_pago_suscripcion, name='iniciar_pago_suscripcion'),
    path('confirmar-simulado/', views.confirmar_pago_suscripcion_simulado, name='confirmar_simulado'),
    path('mi-estado/', views.mi_suscripcion, name='mi_suscripcion'),
    
    path('admin/asignar/', views.admin_asignar_plan_manual, name='admin_asignar'),
    path('admin/listar/', views.admin_listar_todas_suscripciones, name='admin_listar'),
    path('admin/cancelar/<int:usuario_id>/', views.admin_cancelar_suscripcion, name='admin_cancelar'),
]