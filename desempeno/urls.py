from django.urls import path
from .views import KPIsView, SeriesView, RankingAgentesView, AnunciosAgenteView

urlpatterns = [
    path('kpis/', KPIsView.as_view(), name='desempeno-kpis'),
    path('series/', SeriesView.as_view(), name='desempeno-series'),
    path('ranking/agentes/', RankingAgentesView.as_view(), name='desempeno-ranking-agentes'),
    path('anuncios/agente/<int:agente_id>/', AnunciosAgenteView.as_view(), name='desempeno-anuncios-agente'),
]
