# reportes/urls.py
from django.urls import path
# ✅ --- IMPORTA LA NUEVA VISTA ---
from .views import GenerarReporteView, ExportarDatosView, ReporteDirectoView

urlpatterns = [
    # Ruta de IA (para ReportesIA.jsx)
    path('generar-json/', GenerarReporteView.as_view(), name='generar_reporte_json'),
    
    # ✅ --- RUTA MANUAL DIRECTA (para el nuevo ReporteRápido.jsx) ---
    path('directo/', ReporteDirectoView.as_view(), name='reporte_directo'),

    # Ruta de exportación (usada por ambos)
    path('exportar/', ExportarDatosView.as_view(), name='exportar_reporte_archivo'),
]