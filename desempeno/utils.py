from django.apps import apps
from django.db.models import Q

# Estados comunes (normalizados a mayúsculas)
COMPLETED_STATES = {'COMPLETADA', 'COMPLETED', 'DONE', 'REALIZADA'}
CANCELED_STATES  = {'CANCELADA', 'CANCELED'}
SCHEDULED_STATES = {'PENDIENTE', 'PROGRAMADA', 'SCHEDULED'}

def get_model(app_label, model_name):
    return apps.get_model(app_label, model_name)

def has_field(model, name):
    return any(getattr(f, 'name', None) == name for f in model._meta.get_fields())

def detect_datetime_field(model, candidates):
    for c in candidates:
        if has_field(model, c):
            return c
    return None

def detect_state_field(model):
    for c in ('estado', 'status', 'situacion'):
        if has_field(model, c):
            return c
    return None

def by_agent_filter(model, agent_id):
    # Devuelve kwargs apropiados para filtrar por agente
    # preferimos FKs sencillas y luego relaciones con __id
    candidates_fk_id = ['agente_id', 'agent_id', 'responsable_id', 'created_by_id', 'owner_id', 'usuario_id', 'user_id']
    for f in candidates_fk_id:
        base = f.replace('_id', '')
        if has_field(model, base):
            return {f: agent_id}
    candidates_fk = ['agente', 'agent', 'responsable', 'created_by', 'owner', 'usuario', 'user']
    for f in candidates_fk:
        if has_field(model, f):
            return {f + '__id': agent_id}
    return {'pk__isnull': True}

def by_property_filter(model, inmueble_id):
    candidates_fk_id = ['inmueble_id', 'propiedad_id', 'property_id']
    for f in candidates_fk_id:
        base = f.replace('_id', '')
        if has_field(model, base):
            return {f: inmueble_id}
    candidates_fk = ['inmueble', 'propiedad', 'property']
    for f in candidates_fk:
        if has_field(model, f):
            return {f + '__id': inmueble_id}
    return {'pk__isnull': True}

def state_q(model, state_field, states_set):
    if not state_field:
        return Q()
    q = Q()
    for s in states_set:
        q |= Q(**{f'{state_field}__iexact': s})
    return q

def parse_date(s):
    from datetime import datetime
    if not s:
        return None
    for fmt in ("%Y-%m-%d", "%Y/%m/%d", "%d-%m-%Y", "%d/%m/%Y"):
        try:
            return datetime.strptime(s, fmt)
        except ValueError:
            continue
    return None

def daterange_filter(model, qs, start_dt, end_dt):
    # Preferimos campo programado; si no hay, usamos created_at o similar
    dt_field = detect_datetime_field(model, [
        'programada_para', 'fecha_programada', 'fecha', 'scheduled_for',
        'created_at', 'creado_en', 'created'
    ])
    if not dt_field:
        return qs
    if start_dt:
        qs = qs.filter(**{f'{dt_field}__gte': start_dt})
    if end_dt:
        qs = qs.filter(**{f'{dt_field}__lt': end_dt})
    return qs
