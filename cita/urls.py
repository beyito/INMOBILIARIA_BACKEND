




from . import views
from django.urls import path

urlpatterns = [
    path("", views.listar_citas, name="listar_citas"),
    path("crear/", views.crear_cita, name="crear_cita"),

    path("<int:cita_id>/reprogramar/", views.reprogramar_cita, name="reprogramar_cita"),
    path("<int:cita_id>/", views.obtener_cita, name="obtener_cita"),

        path("<int:cita_id>/eliminar/", views.eliminar_cita, name="eliminar_cita"),

]
