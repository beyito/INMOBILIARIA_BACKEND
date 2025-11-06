from django.urls import path
from . import views
from .views import avisar_grupos, run_scan  # <-- importa la vista
urlpatterns = [
    # Config por contrato
    path('config/<int:contrato_id>/', views.get_config, name='alertas_get_config'),
    path('config/<int:contrato_id>/update', views.update_config, name='alertas_update_config'),

    # Alertas manuales + listado
    path('', views.listar_alertas, name='alertas_list'),
    path('crear/', views.crear_alerta, name='alertas_crear'),
    path('<int:alerta_id>/mark', views.marcar_enviado, name='alertas_mark'),
    path('mis_alertas/', views.mis_alertas, name='alertas_mias'),
    path('<int:alerta_id>/visto/', views.marcar_como_visto, name='alerta_visto'),
    # Escaneo/envío
    path('avisar/', avisar_grupos, name='alertas-avisar'),
    path('run/', run_scan, name='alertas-run'),
]
