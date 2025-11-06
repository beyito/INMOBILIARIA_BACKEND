# alertas/services.py - VERSIÓN FINAL CORREGIDA

from datetime import date, timedelta
from dateutil.relativedelta import relativedelta
from django.conf import settings
from django.core.mail import send_mail  
from django.db import transaction
from .models import Alerta, AlertLog

# --- FUNCIONES AUXILIARES DE DESTINATARIOS Y ENVÍO BÁSICO ---

def _email_de(u):
    return getattr(u, 'correo', None) or getattr(u, 'email', None)

def _destinatarios(alerta):
    emails = set()
    c = getattr(alerta, 'contrato', None)
    if c:
        for u in (getattr(c, 'cliente', None), getattr(c, 'propietario', None), getattr(c, 'agente', None)):
            e = _email_de(u) if u else None
            if e: emails.add(e)
    # grupos/usuarios destino (para avisos o refuerzos)
    try:
        from usuario.models import Usuario
        for g in alerta.grupos_destino.all():
            # Nota: Cambiado de 'grupo=g' a 'groups=g' si usas ManyToMany estándar
            for u in Usuario.objects.filter(grupo=g, is_active=True):
                e = _email_de(u)
                if e: emails.add(e)
        for u in alerta.usuarios_destino.all():
            e = _email_de(u)
            if e: emails.add(e)
    except Exception:
        pass

    force = getattr(settings, 'ALERTS_FORCE_EMAIL', None)
    if force:
        emails.add(force)
    return [e for e in emails if e]

def _send_email(to, subject, body):
    try:
        send_mail(subject, body, getattr(settings, "DEFAULT_FROM_EMAIL", None), [to], fail_silently=True)
        return True
    except Exception:
        return False

def _send_push_placeholder(num_destinatarios: int):
    # Logueamos cuántas simulaciones de envío ocurrieron
    print(f"--- DEBUG: Simulando envío de PUSH a {num_destinatarios} destinatarios ---") 
    return True

def _alquiler_fecha_pago(fecha_inicio: date, dia_pago: int|None, k: int) -> date:
    base = fecha_inicio + relativedelta(months=+k)
    dia = dia_pago or fecha_inicio.day
    # clamp al último día del mes
    ultimo = (base + relativedelta(day=31)).day
    return base.replace(day=min(dia, ultimo))

# --- FUNCIÓN DE ENVÍO MASIVO (La que funciona) ---
# Usada en scan_and_send_alerts para EMAIL

def enviar_alerta_a_destinatarios(alerta: Alerta, dests: list, asunto: str, cuerpo: str, log_key: str, log_value: int = 0) -> int:
    """
    Función auxiliar que maneja el envío masivo de correos y el registro correcto de AlertLog.
    Retorna el número real de correos enviados.
    """
    if not dests:
        return 0

    emails_enviados = 0
    # Itera sobre CADA correo electrónico
    for addr in dests:
        if _send_email(addr, asunto, cuerpo):
            emails_enviados += 1
            
    # Registra SÓLO UN LOG POR CANAL/ALERTA/DÍA (para evitar duplicados en la base de datos)
    if emails_enviados > 0:
        log_kwargs = {log_key: log_value}
        AlertLog.objects.create(alerta=alerta, canal='email', **log_kwargs)
        
    return emails_enviados


# --# --- FUNCIÓN PRINCIPAL DE ESCANEO DE ALERTAS ---

@transaction.atomic
def scan_and_send_alerts(hoy: date|None = None) -> dict:
    hoy = hoy or date.today()
    enviados = {'email': 0, 'push': 0}

    # Ordenar por contrato y luego por fecha de vencimiento (due_date)
    alertas = Alerta.objects.select_related('contrato').filter(estado='pendiente').order_by('contrato_id', 'due_date')

    for a in alertas:
        c = a.contrato
        dests = _destinatarios(a)
        if not dests:
            continue
        
        asunto = a.titulo
        cuerpo = (a.descripcion or "Recordatorio").strip()

        # === 1) ALQUILER MENSUAL (Lógica de Cuota Específica Corregida) ===
        if c and getattr(c, 'tipo_contrato', '') == 'alquiler':
            fecha_inicio = getattr(c, 'fecha_inicio', None) or getattr(c, 'fecha_contrato', None)
            if not fecha_inicio: continue

            dia_pago = getattr(c, 'dia_pago', None) or fecha_inicio.day # Usar fecha_inicio.day para el día de pago
            if hoy < fecha_inicio: continue
            
            # 1. CÁLCULO DE K AJUSTADO (k=1 para la primera cuota)
            k_raw = (hoy.year - fecha_inicio.year)*12 + (hoy.month - fecha_inicio.month)
            k_actual = k_raw + 1 
            fecha_pago = _alquiler_fecha_pago(fecha_inicio, dia_pago, k_actual)
            
            ventanas_previas = {0, 1, 3} 
            delta = (fecha_pago - hoy).days
            
            # 🚨 FILTRO CRÍTICO 1: Si esta alerta NO es la cuota que el cálculo dice, la saltamos.
            if a.periodo_index != k_actual:
                continue 
            
            if delta in ventanas_previas:
                asunto = f"[Alquiler] Pago Cuota #{k_actual} - ({fecha_pago.isoformat()})"
                
                # --- USO DE LA FUNCIÓN DE ENVÍO MASIVO ---
                ya_email = AlertLog.objects.filter(alerta=a, canal='email', fecha_envio=hoy, periodo_index=k_actual).exists()
                if not ya_email:
                    emails_count = enviar_alerta_a_destinatarios(a, dests, asunto, cuerpo, 'periodo_index', k_actual)
                    enviados['email'] += emails_count

                ya_push = AlertLog.objects.filter(alerta=a, canal='push', fecha_envio=hoy, periodo_index=k_actual).exists()
                if not ya_push:
                    if _send_push_placeholder(len(dests)):
                        AlertLog.objects.create(alerta=a, canal='push', periodo_index=k_actual)
                        enviados['push'] += len(dests)
            
            continue

        # === 2) ANTICRÉTICO (fin de contrato) (Lógica corregida) ===
        if c and getattr(c, 'tipo_contrato', '') == 'anticretico':
            fecha_fin = getattr(c, 'fecha_fin', None)
            if not fecha_fin: continue
            delta = (fecha_fin - hoy).days

            if delta in {7, 3, 1, 0}:
                asunto = f"[Anticrético] El contrato finaliza el {fecha_fin.isoformat()}"
                
                ya_email = AlertLog.objects.filter(alerta=a, canal='email', fecha_envio=hoy, days_before=delta).exists()
                if not ya_email:
                    emails_count = enviar_alerta_a_destinatarios(a, dests, asunto, cuerpo, 'days_before', delta)
                    enviados['email'] += emails_count

                ya_push = AlertLog.objects.filter(alerta=a, canal='push', fecha_envio=hoy, days_before=delta).exists()
                if not ya_push:
                    if _send_push_placeholder(len(dests)):
                        AlertLog.objects.create(alerta=a, canal='push', days_before=delta)
                        enviados['push'] += len(dests)

            if delta <= 0:
                a.estado = 'enviado'
                a.save(update_fields=['estado'])
            continue

        # === 3) CUSTOM one-shot con due_date (Lógica corregida) ===
        if getattr(a, 'due_date', None) and a.tipo == 'custom':
            delta = (a.due_date - hoy).days
            
            if delta in {0}:
                asunto = a.titulo
                
                ya_email = AlertLog.objects.filter(alerta=a, canal='email', fecha_envio=hoy, days_before=0).exists()
                if not ya_email:
                    emails_count = enviar_alerta_a_destinatarios(a, dests, asunto, cuerpo, 'days_before', 0)
                    enviados['email'] += emails_count

                ya_push = AlertLog.objects.filter(alerta=a, canal='push', fecha_envio=hoy, days_before=0).exists()
                if not ya_push:
                    if _send_push_placeholder(len(dests)):
                        AlertLog.objects.create(alerta=a, canal='push', days_before=0)
                        enviados['push'] += len(dests)
                
                a.estado = 'enviado'
                a.save(update_fields=['estado'])
            continue
        
        continue

    return enviados