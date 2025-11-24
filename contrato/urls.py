# contrato/urls.py
from django.urls import path
from . import views

urlpatterns = [
    path('comisiones/dashboard', views.dashboard_comisiones, name='dashboard-comisiones'),
    path('comisiones/agente/<int:agente_id>', views.detalle_comisiones_agente, name='detalle-comisiones-agente'),
    path('crear-contrato-anticretico/', views.crear_contrato_anticretico, name='crear_contrato_anticretico'),
    path('descargar-pdf/<int:contrato_id>/', views.descargar_contrato_pdf, name='descargar_contrato_pdf'),
    path('detalle/<int:contrato_id>/',views.detalle_contrato, name='detalle_contrato'),
    path('aprobar/<int:contrato_id>/',views.aprobar_contrato,name='aprobar_contrato'),
    path('finalizar/<int:contrato_id>/',views.finalizar_contrato,name='finalizar_contrato'),
    path('listar-anticretico/',views.listar_contratos_anticretico, name='listar_contratos_anticretico'),
    path("generarContratoDeServiciosAnticreticoPdf", views.ContratoServiciosAnticreticoView.as_view(), name="generarContratoDeServiciosAnticreticoPdf"),
    path('generarContratoAlquilerPdf', views.ContratoAlquilerView.as_view(), name='generarContratoAlquilerPdf'),
    path('ver/<int:contrato_id>', views.ContratoViewPdf.as_view(), name='ver-contrato-pdf'),
    path('listar', views.listar_contratos, name='listar-contratos'),
   path('detalle-pdf/<int:contrato_id>', views.detalle_contrato_pdf, name='detalle-contrato-pdf'),
   path('mis-contratos/', views.listar_mis_contratos_cliente, name='listar_mis_contratos_cliente'),
   path('cliente/alquileres/', views.listar_contratos_alquiler_cliente, name='contratos-alquiler-cliente'),
    

]