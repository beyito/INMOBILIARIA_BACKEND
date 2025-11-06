from rest_framework.decorators import api_view, authentication_classes, permission_classes
from rest_framework.authentication import TokenAuthentication
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from django.shortcuts import get_object_or_404
from django.utils import timezone
from .models import AlertConfig, Alerta
from .serializers import AlertConfigSerializer, AlertaSerializer
from .services import scan_and_send_alerts
from inmobiliaria.permissions import requiere_permiso
from django.db import models # <<< FALTA ESTA IMPORTACIÓN >>>
from .models import AlertaLectura
# CONFIG POR CONTRATO
@api_view(['GET'])
@authentication_classes([TokenAuthentication])
@permission_classes([IsAuthenticated])
#@requiere_permiso("ALERTA", "leer") # <--- AÑADIDO
def get_config(request, contrato_id: int):
    from contrato.models import Contrato
    contrato = get_object_or_404(Contrato, pk=contrato_id)
    cfg, _ = AlertConfig.objects.get_or_create(contrato=contrato, defaults={'dias_recordatorio':[30,15,7,3,1]})
    return Response({"status":1,"error":0,"message":"OK","values":AlertConfigSerializer(cfg).data})

@api_view(['PATCH'])
@authentication_classes([TokenAuthentication])
@permission_classes([IsAuthenticated])
#@requiere_permiso("ALERTA", "actualizar") # <--- AÑADIDO
def update_config(request, contrato_id: int):
    from contrato.models import Contrato
    contrato = get_object_or_404(Contrato, pk=contrato_id)
    cfg, _ = AlertConfig.objects.get_or_create(contrato=contrato)
    ser = AlertConfigSerializer(cfg, data=request.data, partial=True)
    ser.is_valid(raise_exception=True)
    ser.save()
    return Response({"status":1,"error":0,"message":"Actualizado","values":ser.data})

# CRUD ALERTAS MANUALES (tipo=custom por defecto)
@api_view(['POST'])
@authentication_classes([TokenAuthentication])
@permission_classes([IsAuthenticated])
#@requiere_permiso("ALERTA", "crear") # <--- AÑADIDO
def crear_alerta(request):
    data = request.data.copy()
    if 'tipo' not in data:
        data['tipo'] = 'custom'
    ser = AlertaSerializer(data=data)
    ser.is_valid(raise_exception=True)
    ser.save()
    return Response({"status":1,"error":0,"message":"Creada","values":ser.data})

@api_view(['GET'])
@authentication_classes([TokenAuthentication])
@permission_classes([IsAuthenticated])
#@requiere_permiso("ALERTA", "leer") # <--- AÑADIDO
def listar_alertas(request):
    filtro = request.GET.get('filtro', 'proximos')  # proximos|vencidos|todos
    hoy = timezone.now().date()
    qs = Alerta.objects.all().order_by('due_date') 

    if filtro == 'proximos':
        qs = qs.filter(due_date__gte=hoy).exclude(estado='enviado')
    elif filtro == 'vencidos':
        qs = qs.filter(due_date__lt=hoy)
    # 'todos' => sin filtro adicional

    return Response({"status":1,"error":0,"message":"OK","values":AlertaSerializer(qs, many=True).data})

@api_view(['PATCH'])
@authentication_classes([TokenAuthentication])
@permission_classes([IsAuthenticated])
#@requiere_permiso("ALERTA", "actualizar") # <--- AÑADIDO
def marcar_enviado(request, alerta_id: int):
    a = get_object_or_404(Alerta, pk=alerta_id)
    a.estado = 'enviado'
    a.save(update_fields=['estado'])
    return Response({"status":1,"error":0,"message":"Marcada como enviada","values":{"id":a.id}})

# TRIGGER MANUAL DEL ESCÁNER
@api_view(['POST'])
@authentication_classes([TokenAuthentication])
@permission_classes([IsAuthenticated])
#@requiere_permiso("ALERTA", "crear")
def run_scan(request):
    res = scan_and_send_alerts()
    return Response({"status":1,"error":0,"message":"EJECUTADO","values":res})
from django.utils import timezone
from rest_framework.decorators import api_view, authentication_classes, permission_classes
from rest_framework.authentication import TokenAuthentication
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from .models import Alerta, AlertLog
# Asegúrate de importar las funciones de services.py
from .services import _destinatarios, _send_email, _send_push_placeholder 
from usuario.models import Grupo # Ya que se usa en el cuerpo de la función

@api_view(['POST'])
@authentication_classes([TokenAuthentication])
@permission_classes([IsAuthenticated])
#@requiere_permiso("ALERTA", "crear")
def avisar_grupos(request):
    """
    Crea una alerta 'custom' y la envía de inmediato a los grupos/usuarios indicados.
    El conteo de 'email' ahora reflejará el número real de correos enviados.
    """
    data = request.data
    titulo = (data.get('titulo') or '').strip()
    if not titulo:
        return Response({"error": "titulo es requerido"}, status=400)

    hoy = timezone.localdate()

    # 1. CREAR ALERTA BASE
    # *********************
    alerta = Alerta.objects.create(
        tipo='custom',
        titulo=titulo,
        descripcion=data.get('descripcion', '') or '',
        due_date=hoy,
        estado='pendiente'
    )

    # 2. ADJUNTAR DESTINOS (sin cambios)
    # **********************************
    grupos_req = data.get('grupos_destino') or []
    for g in grupos_req:
        if isinstance(g, int):
            alerta.grupos_destino.add(g)
        else:
            # Importado arriba: from usuario.models import Grupo
            obj = Grupo.objects.filter(nombre__iexact=str(g).strip()).first()
            if obj:
                alerta.grupos_destino.add(obj.id)

    for uid in (data.get('usuarios_destino') or []):
        try:
            alerta.usuarios_destino.add(int(uid))
        except Exception:
            pass

    # 3. CONSTRUIR Y ENVIAR YA (Lógica de conteo corregida)
    # *****************************************************
    enviados = {"email": 0, "push": 0}
    dests = _destinatarios(alerta)
    
    # 3.1. LÓGICA DE EMAIL
    # ====================
    # Verifica si el AlertLog ya existe para ESTA alerta y ESTE canal HOY.
    # El AlertLog SÓLO debe crearse si el envío fue exitoso a CUALQUIERA.
    ya_email_enviado = AlertLog.objects.filter(
        alerta=alerta, canal='email', fecha_envio=hoy, days_before=0
    ).exists()
    
    if not ya_email_enviado:
        total_emails_enviados = 0
        asunto = alerta.titulo
        cuerpo = alerta.descripcion or ""
        
        # Itera sobre TODOS los destinatarios
        for addr in dests:
            if _send_email(addr, asunto, cuerpo):
                total_emails_enviados += 1 # <-- CONTEO INDIVIDUAL PRECISO

        # Si se envió al menos un correo, crea el AlertLog (para evitar futuros duplicados)
        if total_emails_enviados > 0:
            AlertLog.objects.create(alerta=alerta, canal='email', days_before=0)
            enviados["email"] = total_emails_enviados # <-- ASIGNA EL CONTEO TOTAL REAL
            
    # 3.2. LÓGICA DE PUSH
    # ===================
    ya_push_enviado = AlertLog.objects.filter(
        alerta=alerta, canal='push', fecha_envio=hoy, days_before=0
    ).exists()
    
    if not ya_push_enviado and _send_push_placeholder(len(dests)):
        AlertLog.objects.create(alerta=alerta, canal='push', days_before=0)
        enviados["push"] = len(dests) # Asume que PUSH es un solo envío a un servicio

    # 4. MARCAR Y RESPONDER
    # *********************
    alerta.estado = 'enviado'
    alerta.save(update_fields=['estado'])

    return Response({
        "status": 1,
        "error": 0,
        "message": "AVISO ENVIADO",
        "values": {
            "alerta_id": alerta.id,
            "email": enviados["email"], # <-- ¡Aquí verás el número real de correos enviados!
            "push": enviados["push"]
        }
    }, status=200)
# alertas/views.py (agrega)
@api_view(['GET'])
@authentication_classes([TokenAuthentication])
@permission_classes([IsAuthenticated])
#@requiere_permiso("ALERTA", "leer") # <--- DECORADOR APLICADO

# alerta/views.py (Función mis_alertas CON LÓGICA SIMPLIFICADA)

def mis_alertas(request):
    """ Retorna todas las alertas dirigidas al usuario, anotadas con el estado 'visto'. """
    user = request.user
    hoy = timezone.localdate()
    
    # 1. CONSULTA BASE
    alertas_vistas = AlertaLectura.objects.filter(usuario=user).values_list('alerta_id', flat=True)
    qs = Alerta.objects.filter(
        models.Q(usuarios_destino=user) |
        (user.grupo and models.Q(grupos_destino=user.grupo)) |
        models.Q(contrato__agente=user) 
    ).distinct().order_by('-creado')    

    # 2. ANOTACIÓN (Agrega el campo 'visto' para el serializador)
    qs = qs.annotate(
        visto=models.Case(
            models.When(id__in=alertas_vistas, then=True),
            default=False,
            output_field=models.BooleanField()
        )
    )


    # 3. FILTRADO (El cliente solo quiere la lista completa)
    # >>> Ignoramos el parámetro de filtro para devolver siempre el QuerySet completo (qs) <<<

    return Response({"status":1,"error":0,"message":"OK","values":AlertaSerializer(qs, many=True).data})

# ... (El resto del archivo, incluyendo marcar_como_visto, permanece igual)
@api_view(['POST'])
@authentication_classes([TokenAuthentication])
@permission_classes([IsAuthenticated])
def marcar_como_visto(request, alerta_id: int):
    """
    Registra que el usuario actual ha visto la alerta específica.
    """
    user = request.user
    alerta = get_object_or_404(Alerta, pk=alerta_id)
    
    # Intenta crear la entrada. Si ya existe, simplemente se ignora.
    AlertaLectura.objects.get_or_create(alerta=alerta, usuario=user)

    return Response({"status": 1, "error": 0, "message": "Alerta marcada como vista"})