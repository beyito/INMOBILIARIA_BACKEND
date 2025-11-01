from django.urls import path
from . import views

urlpatterns = [
    path('comisiones/dashboard', views.dashboard_comisiones, name='dashboard-comisiones'),
    path('comisiones/agente/<int:agente_id>', views.detalle_comisiones_agente, name='detalle-comisiones-agente'),
]