from django.shortcuts import get_object_or_404
from django.db.models import Q
from rest_framework.decorators import api_view
from rest_framework.response import Response
from rest_framework import status

from .models import Cita,TipoTramite
from .serializers import CitaSerializer,TipoTramiteSerializer
from inmobiliaria.permissions import requiere_permiso

# ==========================
# LISTAR / OBTENER
# ==========================
@api_view(["GET"])
@requiere_permiso("Cita", "leer")
def listar_citas(request):
    """
    Lista las citas en las que participa el usuario autenticado
    (como agente o como cliente). Control de acceso solo por permiso 'leer'.
    """
    qs = (Cita.objects
          .filter(Q(agente=request.user) | Q(cliente=request.user))
          .order_by("-fecha_cita", "-hora_inicio"))
    ser = CitaSerializer(qs, many=True)
    return Response({"status": 1, "error": 0, "message": "LISTADO DE CITAS", "values": {"citas": ser.data}})


@api_view(["GET"])
@requiere_permiso("Cita", "leer")
def obtener_cita(request, cita_id):
    """
    Devuelve el detalle de una cita.
    (Si prefieres permitir leer cualquier cita a quien tenga 'leer', remueve el chequeo de participación.)
    """
    cita = get_object_or_404(Cita, id=cita_id)
    if cita.agente != request.user and cita.cliente != request.user:
        return Response(
            {"status": 0, "error": 1, "message": "No autorizado a ver esta cita", "values": {}},
            status=status.HTTP_403_FORBIDDEN
        )
    return Response({"status": 1, "error": 0, "message": "OK", "values": {"cita": CitaSerializer(cita).data}})


# ==========================
# CREAR (solo por permiso)
# ==========================
@api_view(["POST"])
#@requiere_permiso("Cita", "crear")
def crear_cita(request):
    """
    Crea una cita.
    Ya no se exige 'ser agente': basta con tener permiso 'crear' en el componente 'Cita'.
    El backend fuerza 'agente' y 'creado_por' al usuario autenticado.
    """
    data = request.data.copy()
    data["agente"] = request.user.id
    data["creado_por"] = request.user.id
    data["estado"] = Cita.ESTADO_CONFIRMADA

    ser = CitaSerializer(data=data, context={"request": request})
    if ser.is_valid():
        ser.save()
        return Response({"status": 1, "error": 0, "message": "Cita creada", "values": {"cita": ser.data}},
                        status=status.HTTP_201_CREATED)
    return Response({"status": 0, "error": 1, "message": "Error al crear cita", "values": ser.errors},
                    status=status.HTTP_400_BAD_REQUEST)


# ==========================
# REPROGRAMAR / CONFIRMAR / CANCELAR
# (solo por permiso 'actualizar')
# ==========================
@api_view(["PATCH"])
@requiere_permiso("Cita", "actualizar")
def reprogramar_cita(request, cita_id):
    """
    Reprograma fecha/hora. Ya no se exige ser el agente dueño; solo permiso 'actualizar'.
    """
    cita = get_object_or_404(Cita, id=cita_id)
    payload = {
        "fecha_cita": request.data.get("fecha_cita", cita.fecha_cita),
        "hora_inicio": request.data.get("hora_inicio", cita.hora_inicio),
        "hora_fin": request.data.get("hora_fin", cita.hora_fin),
        "cliente": cita.cliente.pk,
        "tramite": cita.tramite.pk,
        "titulo": cita.titulo,
        "descripcion": cita.descripcion,
        "estado": Cita.ESTADO_REPROGRAMADA,
    }
    ser = CitaSerializer(cita, data=payload, partial=True, context={"request": request})
    if ser.is_valid():
        ser.save()
        return Response({"status": 1, "error": 0, "message": "Cita reprogramada", "values": {"cita": ser.data}})
    return Response({"status": 0, "error": 1, "message": "Datos inválidos", "values": ser.errors},
                    status=status.HTTP_400_BAD_REQUEST)


@api_view(["POST"])
@requiere_permiso("Cita", "actualizar")
def confirmar_cita(request, cita_id):
    """
    Cambia estado a CONFIRMADA. Solo por permiso 'actualizar'.
    """
    cita = get_object_or_404(Cita, id=cita_id)
    cita.estado = Cita.ESTADO_CONFIRMADA
    cita.save(update_fields=["estado", "updated_at"])
    return Response({"status": 1, "error": 0, "message": "Cita confirmada", "values": {"cita": CitaSerializer(cita).data}})


@api_view(["POST"])
@requiere_permiso("Cita", "actualizar")
def cancelar_cita(request, cita_id):
    """
    Cambia estado a CANCELADA. Solo por permiso 'actualizar'.
    """
    cita = get_object_or_404(Cita, id=cita_id)
    cita.estado = Cita.ESTADO_CANCELADA
    cita.save(update_fields=["estado", "updated_at"])
    return Response({"status": 1, "error": 0, "message": "Cita cancelada", "values": {"cita": CitaSerializer(cita).data}})

# --- al inicio del archivo ---


# ==============================
# TIPO TRÁMITE (CRUD)
# ==============================

@api_view(["GET"])
@requiere_permiso("TipoTramite", "leer")
def listar_tipos_tramite(request):
    """
    Lista tipos de trámite. Si pasas ?solo_activos=1 filtra por activos.
    """
    qs = TipoTramite.objects.all()
    if request.GET.get("solo_activos") in ("1", "true", "True"):
        qs = qs.filter(is_activo=True)
    ser = TipoTramiteSerializer(qs, many=True)
    return Response({"status": 1, "error": 0, "message": "LISTA DE TIPOS DE TRÁMITE", "values": {"tipos": ser.data}})

@api_view(["GET"])
@requiere_permiso("TipoTramite", "leer")
def obtener_tipo_tramite(request, tipo_id):
    tipo = get_object_or_404(TipoTramite, id=tipo_id)
    return Response({"status": 1, "error": 0, "message": "OK", "values": {"tipo": TipoTramiteSerializer(tipo).data}})

@api_view(["POST"])
@requiere_permiso("TipoTramite", "crear")
def crear_tipo_tramite(request):
    """
    Campos: nombre (único), descripcion (opcional), is_activo (bool).
    """
    ser = TipoTramiteSerializer(data=request.data)
    if ser.is_valid():
        ser.save()
        return Response({"status": 1, "error": 0, "message": "Tipo de trámite creado", "values": {"tipo": ser.data}},
                        status=status.HTTP_201_CREATED)
    return Response({"status": 0, "error": 1, "message": "Error al crear", "values": ser.errors},
                    status=status.HTTP_400_BAD_REQUEST)

@api_view(["PATCH"])
@requiere_permiso("TipoTramite", "actualizar")
def actualizar_tipo_tramite(request, tipo_id):
    tipo = get_object_or_404(TipoTramite, id=tipo_id)
    ser = TipoTramiteSerializer(tipo, data=request.data, partial=True)
    if ser.is_valid():
        ser.save()
        return Response({"status": 1, "error": 0, "message": "Tipo de trámite actualizado", "values": {"tipo": ser.data}})
    return Response({"status": 0, "error": 1, "message": "Error al actualizar", "values": ser.errors},
                    status=status.HTTP_400_BAD_REQUEST)

@api_view(["DELETE"])
@requiere_permiso("TipoTramite", "eliminar")
def desactivar_tipo_tramite(request, tipo_id):
    """
    Soft delete: is_activo = False
    """
    tipo = get_object_or_404(TipoTramite, id=tipo_id)
    tipo.is_activo = False
    tipo.save(update_fields=["is_activo", "updated_at"])
    return Response({"status": 1, "error": 0, "message": "Tipo de trámite desactivado", "values": {"tipo": TipoTramiteSerializer(tipo).data}})

@api_view(["PATCH"])
@requiere_permiso("TipoTramite", "actualizar")
def activar_tipo_tramite(request, tipo_id):
    tipo = get_object_or_404(TipoTramite, id=tipo_id)
    tipo.is_activo = True
    tipo.save(update_fields=["is_activo", "updated_at"])
    return Response({"status": 1, "error": 0, "message": "Tipo de trámite activado", "values": {"tipo": TipoTramiteSerializer(tipo).data}})

# --- Disponibilidad del agente (mínimo) ---
from .models import DisponibilidadAgente
from .serializers import DisponibilidadAgenteSerializer

@api_view(["GET"])
@requiere_permiso("DisponibilidadAgente", "leer")
def listar_disponibilidades(request):
    qs = DisponibilidadAgente.objects.filter(agente=request.user).order_by("dia_semana","hora_inicio")
    ser = DisponibilidadAgenteSerializer(qs, many=True)
    return Response({"status":1,"error":0,"message":"DISPONIBILIDADES","values":{"items":ser.data}})

@api_view(["POST"])
@requiere_permiso("DisponibilidadAgente", "crear")
def crear_disponibilidad(request):
    data = request.data.copy()
    data["agente"] = request.user.id  # la disponibilidad siempre del usuario logueado
    ser = DisponibilidadAgenteSerializer(data=data)
    if ser.is_valid():
        ser.save()
        return Response({"status":1,"error":0,"message":"Disponibilidad creada","values":{"item":ser.data}})
    return Response({"status":0,"error":1,"message":"Error al crear","values":ser.errors}, status=400)
