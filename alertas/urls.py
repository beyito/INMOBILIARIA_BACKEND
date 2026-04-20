# alertas/urls.py

from django.urls import path
from .import views

urlpatterns = [
    # ⚠️ CRON JOB (Disparado por el servidor diariamente)
    # RUTA: /alertas/ejecutar-generacion/
    path('ejecutar-generacion/', views.cron_generar_alertas, name='cron_generar_alertas'),
    
    # 📢 AVISO INMEDIATO (Solo para Administrador)
    # RUTA: /alertas/aviso-inmediato/
    path('aviso-inmediato/', views.aviso_inmediato_admin, name='aviso_inmediato_admin'),
    
    # 📊 LECTURA DE ALERTAS (Dashboard para Agente/Admin/Cliente)
    # RUTA: /alertas/listar-mis-alertas/
    path('listar-mis-alertas/', views.listar_mis_alertas, name='listar_mis_alertas'),
    path('marcar-visto/<int:alerta_id>/', views.marcar_estado_alerta, name='marcar_estado_alerta'),
    path('listar-admin/', views.listar_alertas_admin, name='listar_alertas_admin'),
]