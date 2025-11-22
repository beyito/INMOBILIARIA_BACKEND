# reportes/urls.py
from django.urls import path
# ✅ --- IMPORTA LA NUEVA VISTA ---
from .views import GenerarReporteView, ExportarDatosView, ReporteDirectoView
from . import reportes_gerenciales_views

urlpatterns = [
    # Ruta de IA (para ReportesIA.jsx)
    path('generar-json/', GenerarReporteView.as_view(), name='generar_reporte_json'),
    
    # ✅ --- RUTA MANUAL DIRECTA (para el nuevo ReporteRápido.jsx) ---
    path('directo/', ReporteDirectoView.as_view(), name='reporte_directo'),

    # Ruta de exportación (usada por ambos)
    path('exportar/', ExportarDatosView.as_view(), name='exportar_reporte_archivo'),

    # Dashboard general
    path('dashboard/', reportes_gerenciales_views.dashboard_general, name='dashboard_general'),
    
    # Reportes específicos
    path('inmuebles/', reportes_gerenciales_views.reporte_inmuebles, name='reporte_inmuebles'),
    path('contratos/', reportes_gerenciales_views.reporte_contratos, name='reporte_contratos'),
    path('agentes/', reportes_gerenciales_views.reporte_agentes, name='reporte_agentes'),
    path('financiero/', reportes_gerenciales_views.reporte_financiero, name='reporte_financiero'),
    path('alertas/', reportes_gerenciales_views.reporte_alertas, name='reporte_alertas'),
    path('usuarios/', reportes_gerenciales_views.reporte_usuarios, name='reporte_usuarios'),
    path('anuncios/', reportes_gerenciales_views.reporte_anuncios, name='reporte_anuncios'),
    path('comunicacion/', reportes_gerenciales_views.reporte_comunicacion, name='reporte_comunicacion'),
    path('comparativo/', reportes_gerenciales_views.reporte_comparativo, name='reporte_comparativo'),
]