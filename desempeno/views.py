from datetime import datetime
from django.db.models import Count, Avg, DurationField, ExpressionWrapper, F
from django.db.models.functions import TruncWeek, TruncMonth, Cast
from rest_framework.views import APIView
from usuario.models import Usuario
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.apps import apps
from decouple import config
import json
import re
from django.shortcuts import get_object_or_404
from .serializers import KPISerializer, SerieSerializer, RankingSerializer
from suscripciones.models import Suscripcion
from .utils import (
    get_model, has_field, by_agent_filter, by_property_filter, state_q,
    SCHEDULED_STATES, COMPLETED_STATES, CANCELED_STATES,
    detect_state_field, parse_date, daterange_filter
)

# -------- import seguro de google-generativeai (NO global configure) --------
try:
    import google.generativeai as genai
    _GENAI_OK = True
except Exception:
    genai = None
    _GENAI_OK = False
# ---------------------------------------------------------------------------
class SaasReportesMixin:
    """
    Mixin para verificar si el usuario tiene un plan que permita reportes.
    """
    def check_saas_permission(self, request):
        # 1. Admin/Staff siempre pasa
        if request.user.is_staff or request.user.is_superuser:
            return True, ""

        try:
            # 2. Verificar suscripción activa
            sub = request.user.suscripcion
            if not sub.esta_activa:
                return False, "Tu suscripción ha vencido. Renueva para ver reportes."
            
            # 3. Verificar feature 'permite_reportes'
            if not sub.plan.permite_reportes:
                return False, "Tu plan actual no incluye el módulo de Reportes Avanzados. Actualiza a PRO."
                
            return True, ""
            
        except Suscripcion.DoesNotExist:
            return False, "No tienes un plan contratado."

def load_cita_model():
    """
    Detecta el modelo de 'cita/visita' automáticamente.
    """
    from django.apps import apps  # ← import interno, así no falla
    from .utils import detect_state_field, detect_datetime_field

    # 1) candidatos directos (ajusta/añade si conoces el nombre)
    direct_candidates = [
        ('cita', 'Cita'),
        ('citas', 'Cita'),
        ('citas', 'CitaInmo'),
        ('agenda', 'Cita'),
        ('visita', 'Visita'),
    ]
    for app_label, model_name in direct_candidates:
        try:
            Model = apps.get_model(app_label, model_name)
            return Model
        except Exception:
            pass

    # 2) autodetección por heurística
    best = None
    best_score = -1
    for Model in apps.get_models():
        try:
            full_name = f"{Model._meta.app_label}.{Model.__name__}".lower()
            if full_name.startswith('django.') or any(k in full_name for k in ['authtoken', 'sessions', 'admin', 'contenttypes']):
                continue

            has_state = bool(detect_state_field(Model))
            has_programmed_dt = bool(detect_datetime_field(Model, [
                'programada_para', 'fecha_programada', 'fecha', 'scheduled_for'
            ]))
            has_created_dt = bool(detect_datetime_field(Model, [
                'created_at', 'creado_en', 'created'
            ]))

            score = 0
            if has_state: score += 2
            if has_programmed_dt: score += 2
            if has_created_dt: score += 1
            name_hint = (Model.__name__ + ' ' + full_name)
            if any(h in name_hint.lower() for h in ['cita', 'visita', 'agenda', 'appointment', 'schedule']):
                score += 1

            if score > best_score:
                best = Model
                best_score = score
        except Exception:
            continue

    return best  # puede ser None


def safe_count(qs):
    try:
        return qs.count()
    except Exception:
        return 0


class KPIsView(APIView, SaasReportesMixin):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        permitido, mensaje = self.check_saas_permission(request)
        if not permitido:
            return Response({"detail": mensaje}, status=403)
        Cita = load_cita_model()
        scope = request.query_params.get('scope', 'global')  # global|agente|inmueble
        scope_id = request.query_params.get('id')
        d1 = parse_date(request.query_params.get('from'))
        d2 = parse_date(request.query_params.get('to'))

        payload = {
            'scope': scope,
            'scope_id': int(scope_id) if scope_id else None,
            'desde': d1.date() if d1 else None,
            'hasta': d2.date() if d2 else None,
            'citas_total': 0, 'citas_programadas': 0,
            'citas_completadas': 0, 'citas_canceladas': 0,
            'tasa_cumplimiento': 0.0, 'tasa_cancelacion': 0.0,
            'duracion_promedio_min': None, 'lead_time_promedio_h': None,
        }

        if not Cita:
            return Response(payload)

        qs = Cita.objects.all()
        if scope == 'agente' and scope_id:
            qs = qs.filter(**by_agent_filter(Cita, int(scope_id)))
        elif scope == 'inmueble' and scope_id:
            qs = qs.filter(**by_property_filter(Cita, int(scope_id)))

        qs = daterange_filter(Cita, qs, d1, d2)
        state_field = detect_state_field(Cita)

        total = safe_count(qs)
        prog = safe_count(qs.filter(state_q(Cita, state_field, SCHEDULED_STATES))) if state_field else 0
        comp = safe_count(qs.filter(state_q(Cita, state_field, COMPLETED_STATES))) if state_field else 0
        canc = safe_count(qs.filter(state_q(Cita, state_field, CANCELED_STATES))) if state_field else 0

        payload['citas_total'] = total
        payload['citas_programadas'] = prog
        payload['citas_completadas'] = comp
        payload['citas_canceladas'] = canc
        payload['tasa_cumplimiento'] = round((comp/total)*100, 2) if total else 0.0
        payload['tasa_cancelacion'] = round((canc/total)*100, 2) if total else 0.0

        # duración promedio (si existe 'duracion_min' o 'duracion')
        dur_field = None
        for c in ['duracion_min', 'duracion']:
            if has_field(Cita, c):
                dur_field = c
                break
        if dur_field:
            try:
                from django.db.models import FloatField
                avg_dur = qs.aggregate(v=Avg(Cast(F(dur_field), output_field=FloatField())))['v']
                payload['duracion_promedio_min'] = round(avg_dur or 0, 2)
            except Exception:
                payload['duracion_promedio_min'] = None

        # lead time programada - creada (si existen ambos)
        created_field = None
        for c in ['created_at', 'creado_en', 'created']:
            if has_field(Cita, c):
                created_field = c
                break
        scheduled_field = None
        for c in ['programada_para', 'fecha_programada', 'fecha', 'scheduled_for']:
            if has_field(Cita, c):
                scheduled_field = c
                break

        if created_field and scheduled_field:
            try:
                delta = ExpressionWrapper(F(scheduled_field) - F(created_field), output_field=DurationField())
                avg_delta = qs.annotate(d=delta).aggregate(s=Avg('d'))['s']
                if avg_delta is not None:
                    payload['lead_time_promedio_h'] = round(avg_delta.total_seconds()/3600.0, 2)
            except Exception:
                payload['lead_time_promedio_h'] = None

        return Response(payload)


class SeriesView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        Cita = load_cita_model()
        metric = request.query_params.get('metric', 'citas')      # citas|completadas|canceladas
        group_by = request.query_params.get('group_by', 'month')  # week|month
        d1 = parse_date(request.query_params.get('from'))
        d2 = parse_date(request.query_params.get('to'))

        if not Cita:
            return Response({'metric': metric, 'group_by': group_by, 'points': []})

        qs = daterange_filter(Cita, Cita.objects.all(), d1, d2)
        state_field = detect_state_field(Cita)

        if group_by == 'week':
            trunc = TruncWeek
            fmt = '%Y-%m-%d'   # lunes de la semana
        else:
            trunc = TruncMonth
            fmt = '%Y-%m-01'

        # bucket por created_at si existe; si no, por programada/fecha disponible
        if has_field(Cita, 'created_at'):
            base = qs.annotate(bucket=trunc('created_at'))
        else:
            dt_alt = None
            for c in ['programada_para', 'fecha_programada', 'fecha', 'scheduled_for']:
                if has_field(Cita, c):
                    dt_alt = c
                    break
            base = qs.annotate(bucket=trunc(dt_alt)) if dt_alt else qs

        if metric == 'completadas' and state_field:
            base = base.filter(state_q(Cita, state_field, COMPLETED_STATES))
        elif metric == 'canceladas' and state_field:
            base = base.filter(state_q(Cita, state_field, CANCELED_STATES))

        agg = base.values('bucket').annotate(y=Count('id')).order_by('bucket')
        points = []
        for row in agg:
            b = row['bucket']
            points.append({'x': b.strftime(fmt) if b else '', 'y': float(row['y'])})

        return Response({'metric': metric, 'group_by': group_by, 'points': points})


class RankingAgentesView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        """
        Ranking por agentes:
        - by=citas|completadas|canceladas (default: citas)
        """
        Cita = load_cita_model()
        by = request.query_params.get('by', 'citas')
        d1 = parse_date(request.query_params.get('from'))
        d2 = parse_date(request.query_params.get('to'))

        if not Cita:
            return Response({'by': by, 'items': []})

        qs = daterange_filter(Cita, Cita.objects.all(), d1, d2)

        # detectar FK a agente
        agent_fk = None
        for f in ['agente', 'agent', 'responsable', 'created_by', 'owner', 'usuario', 'user']:
            if has_field(Cita, f):
                agent_fk = f
                break
        if not agent_fk:
            return Response({'by': by, 'items': []})

        state_field = detect_state_field(Cita)
        if by == 'completadas' and state_field:
            qs = qs.filter(state_q(Cita, state_field, COMPLETED_STATES))
        elif by == 'canceladas' and state_field:
            qs = qs.filter(state_q(Cita, state_field, CANCELED_STATES))

        # nombre del agente: intenta nombre / first_name + last_name
        name_fields = [
            f'{agent_fk}__nombre',
            f'{agent_fk}__first_name',
            f'{agent_fk}__last_name',
        ]

        agg = qs.values(
            f'{agent_fk}__id',
            *name_fields
        ).annotate(value=Count('id')).order_by('-value')[:20]

        items = []
        for row in agg:
            entity_id = row.get(f'{agent_fk}__id')
            name = row.get(f'{agent_fk}__nombre') or (
                ((row.get(f'{agent_fk}__first_name') or '') + ' ' + (row.get(f'{agent_fk}__last_name') or '')).strip()
            ) or f'Agente {entity_id}'
            items.append({'entity_id': entity_id, 'entity_name': name, 'value': float(row['value'])})

        return Response({'by': by, 'items': items})


class AnunciosAgenteView(APIView):
    permission_classes = [IsAuthenticated]  # usa TokenAuthentication desde settings

    def get(self, request, agente_id: int):
        # Import local para evitar problemas al cargar apps al iniciar
        from inmueble.models import InmuebleModel, AnuncioModel

        # 1) Publicaciones (inmuebles) del agente
        inmuebles_qs = InmuebleModel.objects.filter(agente_id=agente_id, is_active=True)

        total_publicaciones = inmuebles_qs.count()
        # 2) Solo los inmuebles que tienen anuncio (OneToOne → related_name="anuncio")
        publicaciones_con_anuncio = inmuebles_qs.filter(anuncio__isnull=False).count()

        # 3) Anuncios de esas publicaciones
        anuncios_qs = AnuncioModel.objects.filter(
            inmueble__in=inmuebles_qs, is_active=True
        )
        total_anuncios = anuncios_qs.count()

        # 4) Conteos por estado (el modelo guarda en minúsculas)
        def c(estado: str) -> int:
            return anuncios_qs.filter(estado__iexact=estado).count()

        vendidos     = c("vendido")
        anticreticos = c("anticretico")
        alquilados   = c("alquilado")

        otros = max(0, total_anuncios - (vendidos + anticreticos + alquilados))

        def pct(n: int, d: int) -> float:
            return round((n * 100.0 / d), 2) if d else 0.0

        data = {
            "agente_id": agente_id,
            "totales": {
                "publicaciones": total_publicaciones,
                "publicaciones_con_anuncio": publicaciones_con_anuncio,
                "anuncios": total_anuncios,
            },
            "estados": {
                "vendido":     {"count": vendidos,     "pct": pct(vendidos, total_anuncios)},
                "anticretico": {"count": anticreticos, "pct": pct(anticreticos, total_anuncios)},
                "alquilado":   {"count": alquilados,   "pct": pct(alquilados, total_anuncios)},
                "otros":       {"count": otros,        "pct": pct(otros, total_anuncios)},
            },
        }

        # ---- KPI de desempeño (tasa de cierre) + tasa de publicación ----
        cerrados = vendidos + anticreticos + alquilados
        desempeno = pct(cerrados, total_anuncios)
        tasa_publicacion = pct(publicaciones_con_anuncio, total_publicaciones)

        def etiqueta_desempeno(p):
            if p >= 75: return "Excelente"
            if p >= 50: return "Bueno"
            if p >= 25: return "Regular"
            return "Bajo"

        data["kpis"] = {
            "desempeno": desempeno,               # % de anuncios cerrados / total anuncios
            "tasa_publicacion": tasa_publicacion, # % de publicaciones del agente que tienen anuncio
            "nota": etiqueta_desempeno(desempeno)
        }

        return Response(data, status=200)


# --------------------------- IA: Reporte con Gemini ---------------------------

class ReporteIAGeminiView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        # 1) Paquete presente
        if not _GENAI_OK:
            return Response(
                {"detail": "Falta el paquete 'google-generativeai'. Ejecuta: pip install google-generativeai"},
                status=503
            )

        # 2) API Key (acepta API_GEMINI o GOOGLE_API_KEY)
        api_key = config('API_GEMINI', default=config('GOOGLE_API_KEY', default=''))
        if not api_key:
            return Response(
                {"detail": "Falta API_GEMINI (o GOOGLE_API_KEY) en .env / settings."},
                status=503
            )

        # 3) Payload desde el front
        payload = request.data or {}
        kpis = payload.get("kpis") if isinstance(payload.get("kpis"), dict) else None
        notas = payload.get("notas", "")

        # enriquecer con nombre del agente si llega (no bloquea si falla)
        agente_nombre = None
        agente_id = payload.get("agente_id") or getattr(request.user, "id", None)
        if agente_id:
            try:
                u = Usuario.objects.get(pk=int(agente_id))
                agente_nombre = getattr(u, "nombre", f"Agente {u.id}")
            except Exception:
                pass

        if not kpis:
            kpis = {k: v for k, v in payload.items() if k not in {"notas", "agente_id"}}
        if not isinstance(kpis, dict) or not kpis:
            return Response({"detail": "El campo 'kpis' debe ser un objeto con métricas."}, status=400)

        info = {"agente": agente_nombre or (str(agente_id) if agente_id else "N/D"), "kpis": kpis}

        prompt = f"""
Eres un analista experto en desempeño inmobiliario.
Con base en los siguientes datos, redacta un informe claro y profesional en español.
Incluye:
- Resumen del desempeño general.
- Interpretación de KPIs.
- 3 recomendaciones accionables.

Instrucciones:
- Devuelve texto plano (sin Markdown, sin **, ##, ni \\n).
- Párrafos naturales, sin listas.

Datos:
{json.dumps(info, ensure_ascii=False)}
Notas: {notas}
"""

        try:
            import google.generativeai as genai  # import local por si el módulo cambia
            genai.configure(api_key=api_key)

            # 4) Descubrir modelos disponibles y compatibles con generateContent
            all_models = list(genai.list_models())
            compatibles = [
                m for m in all_models
                if getattr(m, "supported_generation_methods", None)
                and "generateContent" in m.supported_generation_methods
            ]

            if not compatibles:
                return Response(
                    {
                        "detail": "Tu API key no tiene modelos con generateContent habilitado.",
                        "available_models": [getattr(m, "name", "") for m in all_models],
                    },
                    status=500
                )

            # Preferencia: gemini-1.5 flash/pro si existen; si no, el primero compatible
            preferencia = ["flash", "flash-latest", "pro", "pro-latest", "1.5", "1.0", "gemini"]
            def score(mname: str) -> int:
                name = mname.lower()
                # mayor score si contiene palabras preferidas
                return sum(p in name for p in preferencia)

            # obtener mejor candidato por score
            best = max(compatibles, key=lambda m: score(m.name or ""))
            model_id = best.name

            # 5) Generar
            model = genai.GenerativeModel(model_id)
            result = model.generate_content(prompt)
            text = (getattr(result, "text", "") or "").strip()

            # Limpieza defensiva
            text = re.sub(r'\*\*|##|###|\\n', ' ', text)
            text = re.sub(r'\s+', ' ', text).strip()

            if not text:
                return Response({"detail": "Gemini no devolvió texto.", "model_used": model_id}, status=502)

            return Response({"reporte": text, "reporte_ia": text, "model_used": model_id}, status=200)

        except Exception as e:
            # Si falla por NotFound u otro, devolvemos también los modelos que ve tu key
            try:
                ms = [m.name for m in genai.list_models()]
            except Exception:
                ms = []
            return Response(
                {"detail": f"{type(e).__name__}: {e}", "available_models": ms},
                status=500
            )

