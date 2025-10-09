from django.urls import path
from . import views

urlpatterns = [
    # EL AGENTE REGISTRA EL INMUEBLE, ESPERA LA CONFIRMACION DEL ADMIN
    path('agente_registrar_inmueble', views.agente_registrar_inmueble, name='agente_registrar_inmueble'), # PROBADO
    path('solicitar_cambio_inmueble/<int:inmueble_id>', views.solicitar_cambio_inmueble, name='solicitar_cambio_inmueble'), 
    # path('publicar_anuncio/<int:inmueble_id>', views.publicar_anuncio, name='publicar_anuncio'),
    # --------------------------
    # TIPO INMUEBLE
    # --------------------------
    path('listar_tipo_inmuebles', views.listar_tipo_inmuebles, name='listar_tipo_inmuebles'), #PROBADO
    path('crear_tipo_inmueble', views.crear_tipo_inmueble, name='crear_grupo'), #PROBADO
    path('actualizar_tipo_inmueble/<int:tipo_id>', views.actualizar_tipo_inmueble, name='editar_grupo'), #PROBADO
    path('eliminar_tipo_inmueble/<int:tipo_id>', views.eliminar_tipo_inmueble, name='eliminar_grupo'), #PROBADO
    path('activar_tipo_inmueble/<int:tipo_id>', views.activar_tipo_inmueble, name='activar_grupo'), #PROBADO

# PARA EL ADMIN
    path('aceptar_inmueble/<int:inmueble_id>/', views.aceptar_inmueble, name='aceptar_inmueble'),
    path('rechazar_inmueble/<int:inmueble_id>/', views.rechazar_inmueble, name='rechazar_inmueble'),
    path('aceptar_cambio_inmueble/<int:cambio_id>', views.aceptar_cambio_inmueble, name='aceptar_cambio_inmueble'),
    path('rechazar_cambio_inmueble/<int:cambio_id>', views.rechazar_cambio_inmueble, name='rechazar_cambio_inmueble'),
    path('editar_inmueble/<int:inmueble_id>', views.editar_inmueble, name='editar_inmueble'),
    path('listar_inmuebles/', views.listar_inmuebles_por_estado, name='listar_inmuebles_por_estado'),

# GESTION DE ANUNCIOS
    path('listar_anuncios_disponibles',views.listar_anuncios_disponibles, name='listar_anuncios_disponibles'),

]