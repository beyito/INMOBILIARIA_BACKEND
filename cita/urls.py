from django.urls import path
from . import views

urlpatterns = [
    path("citas/", views.listar_citas, name="listar_citas"),
    path("citas/crear/", views.crear_cita, name="crear_cita"),

    path("citas/<int:cita_id>/reprogramar/", views.reprogramar_cita, name="reprogramar_cita"),
    path("citas/<int:cita_id>/confirmar/",  views.confirmar_cita,  name="confirmar_cita"),
    path("citas/<int:cita_id>/cancelar/",   views.cancelar_cita,   name="cancelar_cita"),
    path("citas/<int:cita_id>/", views.obtener_cita, name="obtener_cita"),
]
