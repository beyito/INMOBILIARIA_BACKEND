from django.urls import path
from .views import KPIsView, SeriesView, RankingAgentesView, AnunciosAgenteView, ReporteIAGeminiView

urlpatterns = [
    path('kpis/', KPIsView.as_view(), name='desempeno-kpis'),
    path('series/', SeriesView.as_view(), name='desempeno-series'),
    path('ranking/agentes/', RankingAgentesView.as_view(), name='desempeno-ranking-agentes'),
    path('anuncios/agente/<int:agente_id>/', AnunciosAgenteView.as_view(), name='desempeno-anuncios-agente'),
    path('reporte_ia_gemini/', ReporteIAGeminiView.as_view(), name='reporte_ia_gemini'),
]
