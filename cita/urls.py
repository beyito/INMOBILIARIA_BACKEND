




from . import views
from django.urls import path

urlpatterns = [
    path("", views.listar_citas, name="listar_citas"),
    path("crear/", views.crear_cita, name="crear_cita"),

    path("<int:cita_id>/reprogramar/", views.reprogramar_cita, name="reprogramar_cita"),
    path("<int:cita_id>/confirmar/",  views.confirmar_cita,  name="confirmar_cita"),
    path("<int:cita_id>/cancelar/",   views.cancelar_cita,   name="cancelar_cita"),
    path("<int:cita_id>/", views.obtener_cita, name="obtener_cita"),

    # TIPO TRÁMITE
    path("tramites/", views.listar_tipos_tramite, name="listar_tipos_tramite"),
    path("tramite/crear/", views.crear_tipo_tramite, name="crear_tipo_tramite"),#probado
    path("tramite/<int:tipo_id>/", views.obtener_tipo_tramite, name="obtener_tipo_tramite"),
    path("tramite/<int:tipo_id>/actualizar/", views.actualizar_tipo_tramite, name="actualizar_tipo_tramite"),#probado
    path("tramite/<int:tipo_id>/desactivar/", views.desactivar_tipo_tramite, name="desactivar_tipo_tramite"),
    path("tramite/<int:tipo_id>/activar/", views.activar_tipo_tramite, name="activar_tipo_tramite"),
# Disponibilidad (opcional pero recomendado)
    path("disponibilidad/", views.listar_disponibilidades),
    path("disponibilidad/crear/", views.crear_disponibilidad),
]
