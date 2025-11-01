# inmueble/urls.py
from django.urls import path
from . import views

urlpatterns = [
    # EL AGENTE REGISTRA EL INMUEBLE, ESPERA LA CONFIRMACION DEL ADMIN
    path('agente_registrar_inmueble', views.agente_registrar_inmueble, name='agente_registrar_inmueble'), # PROBADO
    path('solicitar_cambio_inmueble/<int:inmueble_id>', views.solicitar_cambio_inmueble, name='solicitar_cambio_inmueble'), 
    # path('publicar_anuncio/<int:inmueble_id>', views.publicar_anuncio, name='publicar_anuncio'),
    path('publicar_inmueble/<int:inmueble_id>', views.publicar_inmueble, name='publicar_inmueble'),
    # 🔹 NUEVO: listados del agente para las pestañas
    path('mis-inmuebles', views.mis_inmuebles, name='mis_inmuebles'),
    path('mis-inmuebles/resumen', views.resumen_mis_inmuebles, name='resumen_mis_inmuebles'),
    path('listar_inmuebles_agente/', views.listar_inmuebles_agente, name='listar_inmuebles_agente'),
    path('historial-publicaciones', views.historial_publicaciones, name='historial_publicaciones'),
    # ✅ Rutas de corrección y reenvío
    path('corregir_reenviar_inmueble/<int:inmueble_id>/', views.corregir_y_reenviar_inmueble, name='corregir_y_reenviar_inmueble'),
    path('solicitar_correccion_inmueble/<int:inmueble_id>/', views.solicitar_correccion_inmueble, name='solicitar_correccion_inmueble'),
    # --------------------------
    # TIPO INMUEBLE
    # --------------------------
    path('listar_tipo_inmuebles', views.listar_tipo_inmuebles, name='listar_tipo_inmuebles'), #PROBADO
    path('crear_tipo_inmueble', views.crear_tipo_inmueble, name='crear_grupo'), #PROBADO
    path('actualizar_tipo_inmueble/<int:tipo_id>', views.actualizar_tipo_inmueble, name='editar_grupo'), #PROBADO
    path('eliminar_tipo_inmueble/<int:tipo_id>', views.eliminar_tipo_inmueble, name='eliminar_grupo'), #PROBADO
    path('activar_tipo_inmueble/<int:tipo_id>', views.activar_tipo_inmueble, name='activar_grupo'), #PROBADO

    path('listar_inmuebles', views.listar_inmuebles, name='listar_inmuebles'),
    path('inmueble/<int:pk>', views.obtener_inmueble, name='obtener_inmueble'),
    path('aprobados-no-publicados', views.listar_inmuebles_aprobados_no_publicados, name='aprobados-no-publicados'),

# PARA EL ADMIN
    path('aceptar_inmueble/<int:inmueble_id>/', views.aceptar_inmueble, name='aceptar_inmueble'),
    path('rechazar_inmueble/<int:inmueble_id>/', views.rechazar_inmueble, name='rechazar_inmueble'),
    path('aceptar_cambio_inmueble/<int:cambio_id>', views.aceptar_cambio_inmueble, name='aceptar_cambio_inmueble'),
    path('rechazar_cambio_inmueble/<int:cambio_id>', views.rechazar_cambio_inmueble, name='rechazar_cambio_inmueble'),
    path('editar_inmueble/<int:inmueble_id>', views.editar_inmueble, name='editar_inmueble'),
    path('listar_inmuebles/', views.listar_inmuebles_por_estado, name='listar_inmuebles_por_estado'),  
# GESTION DE ANUNCIOS     
    path('anuncios/', views.admin_listar_anuncios, name='admin_listar_anuncios'),
    path('anuncios/crear/<int:inmueble_id>', views.admin_crear_anuncio, name='admin_crear_anuncio'),
    path('anuncios/<int:anuncio_id>', views.admin_actualizar_anuncio, name='admin_actualizar_anuncio'),
    path('anuncios/no_publicados', views.admin_inmuebles_sin_anuncio, name='admin_inmuebles_sin_anuncio'),
    path('anuncios/detalle/<int:anuncio_id>', views.admin_obtener_anuncio, name='admin_obtener_anuncio'), 

    # GESTION DE ANUNCIOS
    path('listar_anuncios_disponibles',views.listar_anuncios_disponibles, name='listar_anuncios_disponibles'),
        # GESTIÓN DE ANUNCIOS (para KPI/visualización)
    path('anuncio/crear/', views.anuncio_crear, name='anuncio_crear'),
    path('anuncio/<int:anuncio_id>/actualizar/', views.anuncio_actualizar, name='anuncio_actualizar'),
    path('anuncio/<int:anuncio_id>/estado/', views.estado_anuncio_por_id, name='estado_anuncio_por_id'),
    path('anuncio/estado', views.estado_anuncio_por_inmueble, name='estado_anuncio_por_inmueble'),
    path('anuncio/<int:inmueble_id>/', views.obtener_anuncio_por_inmueble, name='obtener_anuncio_por_inmueble'),
    path('todos-mis-inmuebles', views.todos_mis_inmuebles, name='todos_mis_inmuebles'),

]