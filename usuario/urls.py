from django.urls import path
from . import views

urlpatterns = [
    # --------------------------
    # LOGIN / USUARIO
    # --------------------------
    path('login/', views.login, name='login'), #PROBADO
    path('asignar_grupo_usuario', views.asignar_grupo_usuario, name='asignar_grupo_usuario'), #PROBADO
    path('profile/', views.profile, name='profile'), #PROBADO
    path('register', views.register, name='register'), #PROBADO
    path('editar_usuario/<int:usuario_id>', views.editar_usuario, name='editar_usuario'), #PROBADO
    path('eliminar_usuario/<int:usuario_id>', views.eliminar_usuario, name='eliminar_usuario'), #PROBADO
    path('activar_usuario/<int:usuario_id>', views.activar_usuario, name='activar_usuario'), #PROBADO
    path('listar_usuarios', views.listar_usuarios, name='listar_usuarios'), #PROBADO
    path('recuperacion-codigo-actualizar/', views.SetNewPasswordView.as_view(), name='recuperacion-codigo-actualizar'),
    path('recuperacion-codigo/', views.PasswordResetRequestView.as_view(), name='codigo-recuperacion'),
    path('recuperacion-codigo-confirmar/', views.PasswordResetVerifyCodeView.as_view(), name='recuperacion-codigo-confirmar'),
    path("generarContratoPdf", views.ContratoAgenteView.as_view(), name="generarContratoPdf"),
    path("get_privilegios", views.get_privilegios, name = 'get_privilegios'),


    # --------------------------
    # GRUPO
    # --------------------------
    path('listar_grupos', views.listar_grupos, name='listar_grupos'), #PROBADO
    path('crear_grupo', views.crear_grupo, name='crear_grupo'), #PROBADO
    path('editar_grupo/<int:grupo_id>', views.editar_grupo, name='editar_grupo'), #PROBADO
    path('eliminar_grupo/<int:grupo_id>', views.eliminar_grupo, name='eliminar_grupo'), #PROBADO
    path('activar_grupo/<int:grupo_id>', views.activar_grupo, name='activar_grupo'), #PROBADO

    # --------------------------
    # COMPONENTE
    # --------------------------
    path('crear_componente', views.crear_componente, name='crear_componente'), #PROBADO
    path('editar_componente/<int:componente_id>', views.editar_componente, name='editar_componente'), #PROBADO
    path('listar_componentes', views.listar_componentes, name='listar_componentes'), #PROBADO
    path('eliminar_componente/<int:componente_id>', views.eliminar_componente, name='eliminar_componente'), #PROBADO
    path('activar_componente/<int:componente_id>', views.activar_componente, name='activar_componente'), #PROBADO

    # --------------------------
    # PRIVILEGIO
    # --------------------------
    path('asignar_privilegio', views.asignar_privilegio, name='asignar_privilegio'), #PROBADO
    path('editar_privilegio/<int:privilegio_id>', views.editar_privilegio, name='editar_privilegio'), #PROBADO
    path('eliminar_privilegio/<int:privilegio_id>', views.eliminar_privilegio, name='eliminar_privilegio'), #PROBADO
    path('listar_privilegios', views.listar_privilegios, name='listar_privilegios'), #PROBADO

    # --------------------------
    # BITACORA
    # --------------------------
    path('leer_bitacora/',views.BitacoraView.as_view(),name='leer_bitacora'),
    # --------------------------
    # SOLICITUD AGENTE
    # --------------------------
    path('solicitudes-agentes', views.listar_solicitudes_agentes, name='listar_solicitudes_agentes'),
    path('solicitudes-agentes/<int:solicitud_id>/estado', views.cambiar_estado_solicitud_agente, name='cambiar_estado_solicitud_agente'),
    path('listar-agentes', views.listar_usuarios_agente, name='listar_agentes'),

    # --------------------------
    # (Opcional) Usuario CRUD si luego quieres agregar
    # --------------------------
    # path('usuarios/', views.listar_usuarios, name='listar_usuarios'),
    # path('usuarios/crear/', views.crear_usuario, name='crear_usuario'),
    # path('usuarios/editar/<int:usuario_id>/', views.editar_usuario, name='editar_usuario'),
]

# pasos para recuperar contraseña
#1. /usuario/recuperacion-codigo/
# {
#   "email": "sebas@gmail.com"
# }
#
#2. /usuario/recuperacion-codigo-confirmar/
# {
#   "email": "sebas@gmail.com",
#   "code": "(codigo enviado al email)"
# }
#
#3. /usuario/recuperacion-codigo-actualizar/
# {
#   "email": "sebas@gmail.com",
#   "password": "123456"
# }