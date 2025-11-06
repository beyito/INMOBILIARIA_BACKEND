# reportes/views.py
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status, permissions
from django.http import HttpResponse
from django.conf import settings

import json
import os
import traceback
from decimal import Decimal, InvalidOperation
from datetime import datetime, date

import google.generativeai as genai

# --- Django ORM / utilidades ---
from django.db import models
from django.db.models import Sum, Count, Q
from django.core.exceptions import FieldDoesNotExist
from django.utils import timezone

# --- Apps ---
from usuario.models import Usuario, Grupo
from inmueble.models import InmuebleModel, TipoInmuebleModel, AnuncioModel
from contrato.models import Contrato
from cita.models import Cita

from .permissions import IsAdminOrAgente
from .generators import generar_reporte_pdf, generar_reporte_excel

# --- (Imports de dateutil y decouple) ---
try:
    from dateutil.parser import parse as dateutil_parse
    dateutil_parse('2023-01-01')
    print("[INFO] dateutil.parser loaded successfully.")
except ImportError:
    dateutil_parse = None
    print("[WARN] dateutil.parser not found. Date parsing will be basic (YYYY-MM-DD).")
except Exception as dateutil_err:
    dateutil_parse = None
    print(f"[WARN] dateutil.parser loaded but failed test parse: {dateutil_err}.")

try:
    from decouple import config as env_config
except Exception:
    env_config = None

# --- Configuración de Gemini y Constantes ---
GEMINI_CONFIGURED = False
# Nota: "gemini-2.5-pro" no existe públicamente. Usamos un nombre estable por defecto:
GEMINI_MODEL_NAME = getattr(settings, 'GEMINI_MODEL_NAME', 'models/gemini-2.5-pro')

VALID_TIPOS = {'inmuebles', 'contratos', 'agentes', 'clientes', 'citas', 'anuncios'}
DJANGO_LOOKUP_OPERATORS = [
    'exact', 'iexact', 'contains', 'icontains', 'in', 'gt', 'gte', 'lt', 'lte',
    'isnull', 'range', 'year', 'month', 'day', 'week_day', 'startswith',
    'istartswith', 'endswith', 'iendswith'
]
ALLOWED_AGGREGATIONS = {'Sum': Sum, 'Count': Count}
MAX_ROWS = 1000

_GEMINI_API_KEY = getattr(settings, 'GEMINI_API_KEY', None) \
    or os.getenv('GEMINI_API_KEY') \
    or (env_config('GEMINI_API_KEY', default=None) if env_config else None)

if _GEMINI_API_KEY:
    try:
        genai.configure(api_key=_GEMINI_API_KEY)
        GEMINI_CONFIGURED = True
        print("[INFO] Gemini configurado correctamente.")
    except Exception as e:
        print(f"[ERROR] No se pudo configurar Gemini: {e}")
else:
    print("[WARN] GEMINI_API_KEY no encontrada. Reportes con IA deshabilitados.")

# --- Utilidades ---
def _json_converter(o):
    if isinstance(o, (datetime, date)): return o.isoformat()
    if isinstance(o, Decimal): return f"{o:.2f}"
    raise TypeError(f"Object of type {o.__class__.__name__} is not JSON serializable")

def _safe_decimal(value):
    try: return Decimal(value)
    except (InvalidOperation, TypeError, ValueError): return None

def _normalize_interpretacion(data: dict, default_tipo="inmuebles"):
    if not isinstance(data, dict): data = {}
    tipo = str(data.get("tipo_reporte") or "").strip().lower()
    if tipo not in VALID_TIPOS: tipo = default_tipo
    out = {
        "tipo_reporte": tipo, "formato": "pantalla",
        "filtros": data.get("filtros") or {},
        "agrupacion": data.get("agrupacion") or [],
        "calculos": data.get("calculos") or {},
        "orden": data.get("orden") or [],
        "error": data.get("error") or None,
    }
    if not isinstance(out["filtros"], dict): out["filtros"] = {}
    if not isinstance(out["agrupacion"], list): out["agrupacion"] = []
    if not isinstance(out["calculos"], dict): out["calculos"] = {}
    if not isinstance(out["orden"], list): out["orden"] = []
    return out

def _naive_interpret(user_prompt: str):
    p = (user_prompt or "").lower()
    tipo = "inmuebles"
    if "contrato" in p: tipo = "contratos"
    elif "cita" in p: tipo = "citas"
    elif "anuncio" in p: tipo = "anuncios"
    elif "agente" in p: tipo = "agentes"
    elif "cliente" in p: tipo = "clientes"
    calculos = {}
    if "cantidad" in p or "conteo" in p or "total" in p:
        calculos = {"cantidad": "Count('id')"}
    filtros = {}
    if "aprobado" in p:
        if tipo == "inmuebles": filtros["estado__iexact"] = "aprobado"
        elif tipo == "contratos": filtros["estado__iexact"] = "activo"
    if "santa cruz" in p: filtros["ciudad__icontains"] = "Santa Cruz"
    if "venta" in p and tipo == "inmuebles": filtros["tipo_operacion__iexact"] = "venta"
    if "alquiler" in p and tipo == "inmuebles": filtros["tipo_operacion__iexact"] = "alquiler"
    return _normalize_interpretacion({
        "tipo_reporte": tipo, "formato": "pantalla", "filtros": filtros,
        "agrupacion": [], "calculos": calculos, "orden": [], "error": None,
    })

def _sanitize_inmueble_filters(filtros: dict) -> dict:
    """
    Corrige entradas de fecha inválidas para 'inmuebles', mapeando a anuncio__fecha_publicacion.
    También corrige el error común ciudad__nombre__icontains -> ciudad__icontains.
    """
    if not isinstance(filtros, dict):
        return {}
    corrected = {}
    for k, v in filtros.items():
        # Fix ciudad__nombre__icontains -> ciudad__icontains
        if k == "ciudad__nombre__icontains":
            corrected["ciudad__icontains"] = v
            continue

        # Detectar campos de fecha mal referenciados en Inmueble
        if k.startswith("fecha_aprobacion") or k.startswith("fecha_creacion") or k.startswith("fecha_"):
            # mantener sufijo de lookup si lo hay
            sufijo = ""
            if "__" in k:
                sufijo = k[k.index("__"):]  # ej: "__gte", "__lte", "__range"
            corrected["anuncio__fecha_publicacion" + sufijo] = v
        else:
            corrected[k] = v
    return corrected

# ===================================================================
# ✅ --- CLASE BASE --- ✅
# ===================================================================
class ReporteBaseView(APIView):
    permission_classes = [permissions.IsAuthenticated, IsAdminOrAgente]

    def _parse_date_value(self, value):
        if value is None: return None
        if isinstance(value, str):
            if dateutil_parse:
                try: return dateutil_parse(value)
                except ValueError: pass
            for fmt in ('%Y-%m-%d', '%Y-%m-%d %H:%M:%S'):
                try:
                    dt = datetime.strptime(value, fmt)
                    return dt if ' ' in value else dt.date()
                except ValueError:
                    continue
            raise ValueError(f"Formato de fecha no reconocido: {value}. Use YYYY-MM-DD.")
        return value

    def _validate_and_convert_value(self, model_class, lookup, value):
        """
        Valida y convierte tipos en base al model_class. Endurecido:
        - Si el campo/relación no se resuelve, se lanza FieldDoesNotExist.
        - Sólo se toleran operadores si el resto del path fue válido.
        """
        current_model = model_class
        field_instance = None
        parts = lookup.split('__')
        try:
            for i, part in enumerate(parts):
                is_last = (i == len(parts) - 1)
                # si la última parte es un operador (gte, lte, etc.) dejamos de resolver campos
                if is_last and part in DJANGO_LOOKUP_OPERATORS:
                    break
                try:
                    field_instance = current_model._meta.get_field(part)
                    if getattr(field_instance, 'related_model', None):
                        current_model = field_instance.related_model
                    else:
                        # Si hay más path pero el campo no es relación y la siguiente parte no es operador => error
                        if i < len(parts) - 1 and parts[i + 1] not in DJANGO_LOOKUP_OPERATORS:
                            raise FieldDoesNotExist(f"'{part}' no es relación válida en {current_model.__name__}")
                except FieldDoesNotExist as e:
                    # Endurecido: re-lanzar siempre.
                    raise FieldDoesNotExist(f"Campo/relación inválido en '{lookup}': {e}")

            # Si no hay field_instance y la última parte NO es operador, también error
            if field_instance is None and parts[-1] not in DJANGO_LOOKUP_OPERATORS:
                raise FieldDoesNotExist(f"No se pudo resolver '{lookup}' en {model_class.__name__}")

            if value is None:
                if parts[-1] == 'isnull': return bool(value)
                return None

            lookup_operator = parts[-1] if parts[-1] in DJANGO_LOOKUP_OPERATORS else 'exact'
            converted_value = value

            if lookup_operator == 'isnull':
                converted_value = bool(value) if not isinstance(value, bool) else value
            elif lookup_operator == 'in':
                if not isinstance(value, list): raise ValueError("Valor para 'in' debe ser una lista.")
                converted_value = value
            elif lookup_operator == 'range':
                if not isinstance(value, list) or len(value) != 2: 
                    raise ValueError("Valor para 'range' debe ser lista de dos elementos [desde, hasta].")
                converted_value = [self._parse_date_value(value[0]), self._parse_date_value(value[1])]
            elif parts[-1] in ['year', 'month', 'day', 'week_day']:
                converted_value = int(value)
            elif field_instance:
                target_type = type(field_instance)
                if target_type in (models.DecimalField, models.FloatField):
                    dec = _safe_decimal(value)
                    if dec is None: raise ValueError(f"No se pudo convertir '{value}' a Decimal.")
                    converted_value = dec
                elif target_type == models.IntegerField:
                    converted_value = int(value)
                elif target_type in (models.DateTimeField, models.DateField, models.TimeField):
                    converted_value = self._parse_date_value(value)
                elif target_type == models.BooleanField:
                    if isinstance(value, str):
                        low = value.lower()
                        if low in ('true', '1', 't', 'yes', 'y', 'si', 'sí'): converted_value = True
                        elif low in ('false', '0', 'f', 'no', 'n'): converted_value = False
                        else: raise ValueError("Boolean string inválido.")
                    else:
                        converted_value = bool(value)
                elif target_type == models.CharField and not isinstance(value, str):
                    converted_value = str(value)

            return converted_value

        except FieldDoesNotExist as e:
            raise FieldDoesNotExist(f"Campo/relación inválido en '{lookup}': {e}")
        except (ValueError, TypeError) as e:
            raise ValueError(f"Valor '{value}' inválido para filtro '{lookup}': {e}")

    def _build_queryset(self, interpretacion):
        """
        Construye el queryset según la interpretación. Incluye:
        - Sanitizado defensivo de filtros para 'inmuebles' (fechas -> anuncio__fecha_publicacion).
        - Validación estricta de lookups.
        """
        tipo = interpretacion.get("tipo_reporte")
        filtros_dict = interpretacion.get("filtros", {})
        agrupacion_list = interpretacion.get("agrupacion", [])
        calculos_dict = interpretacion.get("calculos", {})
        orden_list = interpretacion.get("orden", [])

        ModelClass = None
        base_queryset = None

        if tipo == "inmuebles":
            ModelClass = InmuebleModel
            base_queryset = InmuebleModel.objects.select_related('agente', 'cliente', 'tipo_inmueble', 'anuncio')
            # --- SANITIZADO DEFENSIVO ---
            filtros_dict = _sanitize_inmueble_filters(filtros_dict)
        elif tipo == "contratos":
            ModelClass = Contrato
            base_queryset = Contrato.objects.select_related('agente', 'inmueble')
        elif tipo == "agentes":
            ModelClass = Usuario
            base_queryset = Usuario.objects.select_related('grupo').filter(grupo__nombre__iexact='Agente')
        elif tipo == "clientes":
            ModelClass = Usuario
            base_queryset = Usuario.objects.select_related('grupo').filter(grupo__nombre__iexact='Cliente')
        elif tipo == "citas":
            ModelClass = Cita
            base_queryset = Cita.objects.select_related('cliente', 'agente')
        elif tipo == "anuncios":
            ModelClass = AnuncioModel
            base_queryset = AnuncioModel.objects.select_related('inmueble', 'inmueble__agente')
        else:
            raise ValueError(f"Tipo de reporte '{tipo}' no soportado.")

        # Aplicar filtros con validación estricta
        q_filtros = Q()
        for lookup, value in dict(filtros_dict).items():
            try:
                converted_value = self._validate_and_convert_value(ModelClass, lookup, value)
                q_filtros &= Q(**{lookup: converted_value})
            except (FieldDoesNotExist, ValueError, TypeError) as e:
                print(f"[WARN] Skipping invalid filter: {lookup}={repr(value)}. Reason: {e}")
                continue

        queryset = base_queryset.filter(q_filtros)

        # (distinct, si lo necesitas, puedes activar tu lógica)
        needs_distinct = False
        if needs_distinct:
            queryset = queryset.distinct()

        # Agrupación
        hubo_agrupacion = False
        valid_agrupacion = []
        if agrupacion_list:
            hubo_agrupacion = True
            for field_path in agrupacion_list:
                try:
                    self._validate_and_convert_value(ModelClass, field_path, None)
                    valid_agrupacion.append(field_path)
                except (FieldDoesNotExist, ValueError):
                    print(f"[WARN] Invalid grouping field skipped: {field_path}")
            if not valid_agrupacion:
                raise ValueError("Ningún campo de agrupación válido.")
            queryset = queryset.values(*valid_agrupacion)

            # Cálculos
            if calculos_dict:
                aggregations = {}
                for name, expr in calculos_dict.items():
                    agg_func_name, field_in_agg_raw = None, None
                    if isinstance(expr, str):
                        parts = expr.replace(")", "").split("(")
                        if len(parts) == 2:
                            agg_func_name, field_in_agg_raw = parts
                    elif isinstance(expr, dict):
                        agg_func_name, field_in_agg_raw = expr.get("funcion"), expr.get("campo")
                    else:
                        print(f"[WARN] Valor de cálculo desconocido: {expr}")
                        continue

                    if agg_func_name and field_in_agg_raw:
                        field_in_agg = field_in_agg_raw.strip("'\" ")
                        if agg_func_name in ALLOWED_AGGREGATIONS and field_in_agg:
                            AggFunc = ALLOWED_AGGREGATIONS[agg_func_name]
                            try:
                                validation_field = field_in_agg if field_in_agg != '*' else 'id'
                                self._validate_and_convert_value(ModelClass, validation_field, None)
                                aggregations[name] = AggFunc(field_in_agg)
                            except (FieldDoesNotExist, ValueError, TypeError):
                                print(f"[WARN] Invalid field in aggregation skipped: {field_in_agg}")
                        else:
                            print(f"[WARN] Invalid aggregation function skipped: {agg_func_name}")
                    else:
                        print(f"[WARN] Could not parse aggregation: {expr}")

                if aggregations:
                    queryset = queryset.annotate(**aggregations)

            # Orden por defecto si no definieron
            if not orden_list:
                orden_list = valid_agrupacion

        # Ordenamiento (valida que el campo sea válido según contexto)
        final_orden_fields = []
        if orden_list:
            for field_order in orden_list:
                field_name = field_order.lstrip('-')
                is_group_field = field_name in valid_agrupacion
                is_calc_field = field_name in calculos_dict
                is_model_field = not hubo_agrupacion
                if is_model_field:
                    try:
                        self._validate_and_convert_value(ModelClass, field_name, None)
                    except (FieldDoesNotExist, ValueError):
                        is_model_field = False
                if is_group_field or is_calc_field or is_model_field:
                    final_orden_fields.append(field_order)
                else:
                    print(f"[WARN] Invalid ordering field skipped: {field_order}")

        if final_orden_fields:
            queryset = queryset.order_by(*final_orden_fields)
        elif not hubo_agrupacion:
            if tipo == "inmuebles": queryset = queryset.order_by('-id')
            elif tipo == "contratos": queryset = queryset.order_by('-fecha_contrato')
            elif tipo == "agentes": queryset = queryset.order_by('nombre')
            elif tipo == "clientes": queryset = queryset.order_by('nombre')
            elif tipo == "citas": queryset = queryset.order_by('-fecha_cita', 'hora_inicio')
            elif tipo == "anuncios": queryset = queryset.order_by('-fecha_publicacion')

        return queryset, hubo_agrupacion

# ===================================================================
# VISTA #1: GenerarReporteView (IA)
# ===================================================================
class GenerarReporteView(ReporteBaseView):

    def _call_gemini_api(self, user_prompt: str):
        if not GEMINI_CONFIGURED:
            return _naive_interpret(user_prompt)

        now = timezone.now()
        current_date_str = now.strftime('%Y-%m-%d')
        current_year_str = now.strftime('%Y')

        schema_definition = f"""
Esquema de Modelos y Relaciones (Usa estos campos EXACTOS):
Fecha actual: {current_date_str}. Año por defecto: {current_year_str}. Moneda: $us.

1. Inmueble (InmuebleModel):
   - Campos: id, agente (-> Usuario), cliente (-> Usuario), tipo_inmueble (-> TipoInmuebleModel), 
   - Campos: titulo, ciudad, zona, precio, tipo_operacion ('venta', 'alquiler', 'anticretico'),
   - Campos: estado (Choices: 'pendiente', 'aprobado', 'rechazado'). <-- ¡Este es el estado de APROBACIÓN!
   - CAMPO CLAVE: 'ciudad' es un CharField (texto). Usa 'ciudad__icontains', NO 'ciudad__nombre__icontains'.
   - CAMPO CLAVE: El campo de estado es 'estado', NO 'estado_inmueble'.

2. Contrato (Contrato):
   - Campos: id, agente (-> Usuario), inmueble (-> InmuebleModel),
   - Campos: tipo_contrato ('servicios', 'venta', 'alquiler', 'anticretico'),
   - Campos: estado (Choices: 'activo', 'finalizado', 'cancelado', 'pendiente'),
   - Campos: fecha_contrato (DateField), fecha_creacion (DateTimeField), monto, comision_monto.

3. Usuario (Usuario):
   - Campos: id, nombre, correo, ci, telefono,
   - Campos: grupo (-> Grupo, related_name='usuarios'),
   - Campos: date_joined (DateTimeField). <-- USA ESTE CAMPO para "fecha de registro".

4. Cita (Cita):
   - Campos: id, titulo, fecha_cita (DateField), hora_inicio (TimeField),
   - Campos: estado (Choices: 'PENDIENTE', 'CONFIRMADA', 'CANCELADA', 'REALIZADA'),
   - Campos: cliente (-> Usuario), agente (-> Usuario).
   
5. Anuncio (AnuncioModel):
   - Campos: id, inmueble (OneToOneField -> InmuebleModel, related_name='anuncio'),
   - Campos: fecha_publicacion (DateTimeField),
   - Campos: estado (Choices: 'disponible', 'pendiente', 'alquilado', 'vendido', 'anticretico', 'inactivo').
   - Campos: prioridad ('normal', 'destacado', 'premium').

--- REGLAS DE FILTRADO ---
- REGLA #1: Si piden inmuebles "vendidos/alquilados/disponibles", filtra por `anuncio__estado`.
- REGLA #2: El 'estado' de InmuebleModel es SOLO 'pendiente/aprobado/rechazado'.
- REGLA #3: InmuebleModel NO tiene 'fecha_aprobacion' ni 'fecha_creacion'.
- REGLA #4: Cualquier filtro de fecha para 'inmuebles' usa `anuncio__fecha_publicacion`.
- REGLA #5: Ejemplo: "Inmuebles aprobados de los últimos 90 días" -> 
  {{"filtros": {{"estado": "aprobado", "anuncio__fecha_publicacion__gte": "..."}}}}
- REGLA #6: Para ciudad usa `ciudad__icontains`.
- Tipos: 'inmuebles', 'contratos', 'agentes', 'clientes', 'citas', 'anuncios'.
"""
        system_instruction = f"""
Eres un asistente experto en bases de datos para una Inmobiliaria (Moneda: $us). Fecha actual: {current_date_str}.
Devuelve ÚNICAMENTE un JSON con la estructura exacta:

{{
  "tipo_reporte": "string", 
  "formato": "pantalla",
  "filtros": {{ "campo__lookup": "valor" }},
  "agrupacion": ["campo_para_agrupar"], 
  "calculos": {{ "nombre_del_calculo": "Funcion('campo')" }}, 
  "orden": ["campo_para_ordenar"], 
  "error": null | "string"
}}

Reglas:
- "tipo_reporte": uno de los tipos válidos.
- "formato": "pantalla".
- "filtros": usa campos EXACTOS del esquema.
- "calculos": CLAVE=nombre, VALOR=string tipo "Sum('precio')" o "Count('id')".
- "error": string si la solicitud es imposible/ambigua.
- Aplica TODAS las REGLAS DE FILTRADO anteriores (especialmente la #4 y #5).
"""
        try:
            print(f"\n[Gemini] Using model: {GEMINI_MODEL_NAME}")
            print(f"[Gemini] Sending prompt:\nUser Prompt: {user_prompt}")
            model = genai.GenerativeModel(GEMINI_MODEL_NAME)
            generation_config = genai.types.GenerationConfig(response_mime_type="application/json")
            response = model.generate_content(
                [system_instruction, schema_definition, user_prompt],
                generation_config=generation_config
            )

            raw_response_text = (response.text or "").strip()
            print(f"[Gemini] Raw JSON response received:\n{raw_response_text}")

            cleaned = raw_response_text.removeprefix("```json").removesuffix("```").strip()
            if not (cleaned.startswith('{') and cleaned.endswith('}')):
                i, j = cleaned.find('{'), cleaned.rfind('}')
                if i != -1 and j != -1 and j > i:
                    cleaned = cleaned[i:j+1]
                else:
                    raise json.JSONDecodeError("No JSON object found", cleaned, 0)

            parsed = json.loads(cleaned)
            interp = _normalize_interpretacion(parsed, default_tipo="inmuebles")

            # Tolerancia: si viene "error" pero el tipo es válido, seguimos.
            if parsed.get("error") and interp["tipo_reporte"] in VALID_TIPOS:
                print(f"[Gemini] Warning from LLM: {parsed.get('error')}. Using tolerant mode.")
                interp["error"] = None

            # Saneamiento extra por si la IA insiste:
            if interp["tipo_reporte"] == "inmuebles":
                interp["filtros"] = _sanitize_inmueble_filters(interp.get("filtros", {}))

            return interp

        except Exception as e:
            print(f"[ERROR] Gemini failed -> falling back to naive. Reason: {e}")
            traceback.print_exc()
            return _naive_interpret(user_prompt)

    def post(self, request, *args, **kwargs):
        prompt = (request.data.get('prompt') or "").strip()
        if not prompt:
            interpretacion = _naive_interpret(prompt)
        else:
            interpretacion = self._call_gemini_api(prompt)

        # Asegura estructura y limpia error para no bloquear UX
        if interpretacion.get("error") and not interpretacion.get("tipo_reporte"):
            interpretacion = _normalize_interpretacion({}, default_tipo="inmuebles")
        interpretacion["error"] = None
        interpretacion["prompt"] = prompt

        try:
            queryset, hubo_agrupacion = self._build_queryset(interpretacion)
        except ValueError as e:
            print(f"[WARN] Build queryset failed with ValueError: {e}. Falling back to simple list.")
            interpretacion = _normalize_interpretacion({}, default_tipo="inmuebles")
            queryset, hubo_agrupacion = self._build_queryset(interpretacion)
        except Exception as e:
            print(f"[ERROR] Unexpected error building queryset: {e}")
            traceback.print_exc()
            return Response({"error": "Error interno al procesar."}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        try:
            tipo_reporte = interpretacion.get("tipo_reporte")
            if hubo_agrupacion:
                data_para_reporte = list(queryset[:MAX_ROWS])
            else:
                fields_to_select = []
                ModelClass = None
                if tipo_reporte == "inmuebles":
                    ModelClass = InmuebleModel
                    fields_to_select = ['id', 'titulo', 'agente__nombre', 'tipo_inmueble__nombre', 'ciudad', 'zona', 'precio', 'tipo_operacion', 'estado']
                elif tipo_reporte == "contratos":
                    ModelClass = Contrato
                    fields_to_select = ['id', 'tipo_contrato', 'agente__nombre', 'inmueble__titulo', 'fecha_contrato', 'monto', 'comision_monto', 'estado']
                elif tipo_reporte in ("agentes", "clientes"):
                    ModelClass = Usuario
                    fields_to_select = ['id', 'nombre', 'correo', 'telefono', 'ci', 'grupo__nombre']
                elif tipo_reporte == "citas":
                    ModelClass = Cita
                    fields_to_select = ['id', 'titulo', 'agente__nombre', 'cliente__nombre', 'fecha_cita', 'hora_inicio', 'estado']
                elif tipo_reporte == "anuncios":
                    ModelClass = AnuncioModel
                    fields_to_select = ['id', 'inmueble__titulo', 'fecha_publicacion', 'estado', 'prioridad']

                if ModelClass and fields_to_select:
                    valid_fields = []
                    for f in fields_to_select:
                        try:
                            self._validate_and_convert_value(ModelClass, f, None)
                            valid_fields.append(f)
                        except (FieldDoesNotExist, ValueError):
                            print(f"[WARN] Campo por defecto no encontrado, se omite: {f}")
                    data_para_reporte = list(queryset.values(*valid_fields)[:MAX_ROWS])
                else:
                    data_para_reporte = list(queryset.values()[:MAX_ROWS])

            json_output = json.dumps(data_para_reporte, default=_json_converter)
            return HttpResponse(json_output, content_type='application/json', status=status.HTTP_200_OK)

        except Exception as e:
            print(f"[ERROR] Exception during data preparation: {e}")
            traceback.print_exc()
            return Response({"error": "Error al preparar los datos del reporte."}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

# ===================================================================
# ✅ VISTA #2: ReporteDirectoView (SIN IA)
# ===================================================================
class ReporteDirectoView(ReporteBaseView):
    """
    Recibe un JSON estructurado desde el "Reporte Rápido" y genera el reporte directamente.
    """

    def post(self, request, *args, **kwargs):
        builder_data = request.data
        print(f"[Direct Report] Received builder data: {builder_data}")

        # 1) Traducir JSON simple al formato de interpretación
        try:
            interpretacion = self._traducir_builder_a_interpretacion(builder_data)
        except Exception as e:
            print(f"[ERROR] Error traduciendo el builder JSON: {e}")
            return Response({"error": f"Error en el formato del builder: {e}"}, status=status.HTTP_400_BAD_REQUEST)

        # 2) Construir queryset
        try:
            queryset, hubo_agrupacion = self._build_queryset(interpretacion)
        except ValueError as e:
            return Response({"error": f"Error al procesar solicitud: {e}"}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            print(f"[ERROR] Unexpected error building queryset: {e}")
            traceback.print_exc()
            return Response({"error": "Error interno al procesar."}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        # 3) Preparar datos
        try:
            tipo_reporte = interpretacion.get("tipo_reporte")
            if hubo_agrupacion:
                data_para_reporte = list(queryset[:MAX_ROWS])
            else:
                fields_to_select = []
                ModelClass = None
                if tipo_reporte == "inmuebles":
                    ModelClass = InmuebleModel
                    fields_to_select = ['id', 'titulo', 'agente__nombre', 'tipo_inmueble__nombre', 'ciudad', 'zona', 'precio', 'tipo_operacion', 'estado']
                elif tipo_reporte == "contratos":
                    ModelClass = Contrato
                    fields_to_select = ['id', 'tipo_contrato', 'agente__nombre', 'inmueble__titulo', 'fecha_contrato', 'monto', 'comision_monto', 'estado']
                elif tipo_reporte in ("agentes", "clientes"):
                    ModelClass = Usuario
                    fields_to_select = ['id', 'nombre', 'correo', 'telefono', 'ci', 'grupo__nombre']
                elif tipo_reporte == "citas":
                    ModelClass = Cita
                    fields_to_select = ['id', 'titulo', 'agente__nombre', 'cliente__nombre', 'fecha_cita', 'hora_inicio', 'estado']
                elif tipo_reporte == "anuncios":
                    ModelClass = AnuncioModel
                    fields_to_select = ['id', 'inmueble__titulo', 'fecha_publicacion', 'estado', 'prioridad']

                if ModelClass and fields_to_select:
                    valid_fields = []
                    for f in fields_to_select:
                        try:
                            self._validate_and_convert_value(ModelClass, f, None)
                            valid_fields.append(f)
                        except (FieldDoesNotExist, ValueError):
                            print(f"[WARN] Campo por defecto no encontrado, se omite: {f}")
                    data_para_reporte = list(queryset.values(*valid_fields)[:MAX_ROWS])
                else:
                    data_para_reporte = list(queryset.values()[:MAX_ROWS])

            json_output = json.dumps(data_para_reporte, default=_json_converter)
            return HttpResponse(json_output, content_type='application/json', status=status.HTTP_200_OK)

        except Exception as e:
            print(f"[ERROR] Exception during data preparation: {e}")
            traceback.print_exc()
            return Response({"error": "Error al preparar los datos del reporte."}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    def _traducir_builder_a_interpretacion(self, builder):
        """
        Convierte el JSON simple del "Reporte Rápido" al formato esperado por _build_queryset.
        Incluye filtros de MONTO y mapea fechas al campo correcto por tipo.
        """
        tipo = (builder or {}).get("tipo", "inmuebles")
        filtros_in = (builder or {}).get("filtros", {})

        filtros_out = {}

        # 1) Estado
        if filtros_in.get("estado"):
            filtros_out["estado__exact"] = filtros_in["estado"]

        # 2) Ciudad
        if filtros_in.get("ciudad"):
            filtros_out["ciudad__icontains"] = filtros_in["ciudad"]

        # 3) Fechas
        fecha_desde = filtros_in.get("fechaDesde")
        fecha_hasta = filtros_in.get("fechaHasta")

        DATE_FIELD_MAP = {
            "inmuebles": "anuncio__fecha_publicacion",
            "contratos": "fecha_contrato",
            "citas": "fecha_cita",
            "anuncios": "fecha_publicacion",
            "agentes": "date_joined",
            "clientes": "date_joined"
        }
        date_field = DATE_FIELD_MAP.get(tipo, "id")

        if fecha_desde and fecha_hasta:
            filtros_out[f"{date_field}__range"] = [fecha_desde, fecha_hasta]
        elif fecha_desde:
            filtros_out[f"{date_field}__gte"] = fecha_desde
        elif fecha_hasta:
            filtros_out[f"{date_field}__lte"] = fecha_hasta

        # 4) Monto
        monto_op = filtros_in.get("montoOp", "gte")  # gte por defecto
        monto_valor = filtros_in.get("montoValor")

        MONTO_FIELD_MAP = {
            "inmuebles": "precio",
            "contratos": "monto",
            "anuncios": "inmueble__precio",
        }
        monto_field = MONTO_FIELD_MAP.get(tipo)

        if monto_field and (monto_valor is not None and str(monto_valor) != ""):
            lookup = f"{monto_field}__{monto_op}"
            filtros_out[lookup] = monto_valor

        interpretacion = {
            "tipo_reporte": tipo,
            "formato": "pantalla",
            "filtros": filtros_out if tipo != "inmuebles" else _sanitize_inmueble_filters(filtros_out),
            "agrupacion": [],
            "calculos": {},
            "orden": [],
            "error": None
        }

        print(f"[Direct Report] Interpretacion generada: {interpretacion}")
        return interpretacion

# ===================================================================
# VISTA #3: ExportarDatosView
# ===================================================================
class ExportarDatosView(ReporteBaseView):

    def post(self, request, *args, **kwargs):
        data = request.data.get('data')
        formato = (request.data.get('formato') or "").lower()
        prompt = request.data.get('prompt', 'Reporte')

        if not data or not isinstance(data, list):
            return Response({"error": "No se proporcionaron datos válidos para exportar."},
                            status=status.HTTP_400_BAD_REQUEST)
        if formato not in ['pdf', 'excel']:
            return Response({"error": "Formato no válido. Debe ser 'pdf' o 'excel'."},
                            status=status.HTTP_400_BAD_REQUEST)

        interpretacion = {'prompt': prompt, 'formato': formato}
        print(f"[Export] Solicitud de exportación recibida. Formato: {formato}. Filas: {len(data)}")
        try:
            if formato == "pdf":
                print("[Export] Llamando a generar_reporte_pdf...")
                return generar_reporte_pdf(data, interpretacion)
            else:
                print("[Export] Llamando a generar_reporte_excel...")
                return generar_reporte_excel(data, interpretacion)
        except Exception as e:
            print(f"[ERROR] Falló la generación del archivo: {e}")
            traceback.print_exc()
            return Response({"error": "Error interno al generar el archivo."},
                            status=status.HTTP_500_INTERNAL_SERVER_ERROR)
