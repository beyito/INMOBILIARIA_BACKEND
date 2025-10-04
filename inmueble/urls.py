from django.urls import path
from . import views

urlpatterns = [
    # EL AGENTE REGISTRA EL INMUEBLE, ESPERA LA CONFIRMACION DEL ADMIN
    path('agente_registrar_inmueble', views.agente_registrar_inmueble, name='agente_registrar_inmueble'), # PROBADO
    path('solicitar_cambio_inmueble/<int:inmueble_id>', views.solicitar_cambio_inmueble, name='solicitar_cambio_inmueble'), 
    # --------------------------
    # TIPO INMUEBLE
    # --------------------------
    path('listar_tipo_inmuebles', views.listar_tipo_inmuebles, name='listar_tipo_inmuebles'), #PROBADO
    path('crear_tipo_inmueble', views.crear_tipo_inmueble, name='crear_grupo'), #PROBADO
    path('actualizar_tipo_inmueble/<int:tipo_id>', views.actualizar_tipo_inmueble, name='editar_grupo'), #PROBADO
    path('eliminar_tipo_inmueble/<int:tipo_id>', views.eliminar_tipo_inmueble, name='eliminar_grupo'), #PROBADO
    path('activar_tipo_inmueble/<int:tipo_id>', views.activar_tipo_inmueble, name='activar_grupo'), #PROBADO
]