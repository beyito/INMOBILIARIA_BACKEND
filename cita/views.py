# cita/views.py (mínimo necesario)

from django.shortcuts import get_object_or_404
from django.db.models import Q
from rest_framework.decorators import api_view
from rest_framework.response import Response
from rest_framework import status

from .models import Cita
from .serializers import CitaSerializer
from inmobiliaria.permissions import requiere_permiso


# --- helpers mínimos ---
def _es_agente(user) -> bool:
    nombre = getattr(getattr(user, "grupo", None), "nombre", "")
    return isinstance(nombre, str) and nombre.strip().lower() == "agente"

def agente_dueño(request, cita: Cita):
    if request.user != cita.agente:
        return Response(
            {"status": 0, "error": 1, "message": "Solo el agente puede realizar esta acción", "values": {}},
            status=status.HTTP_403_FORBIDDEN
        )


# ===== LISTAR / OBTENER =====
@api_view(["GET"])
@requiere_permiso("Cita", "leer")
def listar_citas(request):
    qs = Cita.objects.filter(Q(agente=request.user) | Q(cliente=request.user)).order_by("-fecha_cita", "-hora_inicio")
    ser = CitaSerializer(qs, many=True)
    return Response({"status": 1, "error": 0, "message": "LISTADO DE CITAS", "values": {"citas": ser.data}})

@api_view(["GET"])
@requiere_permiso("Cita", "leer")
def obtener_cita(request, cita_id):
    cita = get_object_or_404(Cita, id=cita_id)
    if cita.agente != request.user and cita.cliente != request.user:
        return Response({"status": 0, "error": 1, "message": "No autorizado", "values": {}},
                        status=status.HTTP_403_FORBIDDEN)
    return Response({"status": 1, "error": 0, "message": "OK", "values": {"cita": CitaSerializer(cita).data}})


# ===== CREAR (solo AGENTE) =====
@api_view(["POST"])
@requiere_permiso("Cita", "crear")
def crear_cita(request):
    if not _es_agente(request.user):
        return Response({"status": 0, "error": 1, "message": "Solo un AGENTE puede crear una cita"},
                        status=status.HTTP_403_FORBIDDEN)

    data = request.data.copy()
    data["agente"] = request.user.id
    data["creado_por"] = request.user.id

    ser = CitaSerializer(data=data, context={"request": request})
    if ser.is_valid():
        ser.save()  # valida disponibilidad y solapamiento
        return Response({"status": 1, "error": 0, "message": "Cita creada", "values": {"cita": ser.data}},
                        status=status.HTTP_201_CREATED)
    return Response({"status": 0, "error": 1, "message": "Error al crear cita", "values": ser.errors},
                    status=status.HTTP_400_BAD_REQUEST)


# ===== REPROGRAMAR (PATCH) =====
@api_view(["PATCH"])
@requiere_permiso("Cita", "actualizar")
def reprogramar_cita(request, cita_id):
    cita = get_object_or_404(Cita, id=cita_id)
    resp = agente_dueño(request, cita)
    if resp: return resp

    ser = CitaSerializer(
        cita,
        data={
            "fecha_cita": request.data.get("fecha_cita", cita.fecha_cita),
            "hora_inicio": request.data.get("hora_inicio", cita.hora_inicio),
            "hora_fin": request.data.get("hora_fin", cita.hora_fin),
            "cliente": cita.cliente.pk,
            "tramite": cita.tramite.pk,
            "titulo": cita.titulo,
            "descripcion": cita.descripcion,
            "estado": Cita.ESTADO_REPROGRAMADA,
        },
        partial=True,
        context={"request": request},
    )
    if ser.is_valid():
        ser.save()
        return Response({"status": 1, "error": 0, "message": "Cita reprogramada", "values": {"cita": ser.data}})
    return Response({"status": 0, "error": 1, "message": "Datos inválidos", "values": ser.errors},
                    status=status.HTTP_400_BAD_REQUEST)


# ===== ACCIONES: CONFIRMAR / CANCELAR =====
@api_view(["POST"])
@requiere_permiso("Cita", "actualizar")
def confirmar_cita(request, cita_id):
    cita = get_object_or_404(Cita, id=cita_id)
    resp = agente_dueño(request, cita)
    if resp: return resp
    cita.estado = Cita.ESTADO_CONFIRMADA
    cita.save(update_fields=["estado", "updated_at"])
    return Response({"status": 1, "error": 0, "message": "Cita confirmada", "values": {"cita": CitaSerializer(cita).data}})

@api_view(["POST"])
@requiere_permiso("Cita", "actualizar")
def cancelar_cita(request, cita_id):
    cita = get_object_or_404(Cita, id=cita_id)
    resp = agente_dueño(request, cita)
    if resp: return resp
    cita.estado = Cita.ESTADO_CANCELADA
    cita.save(update_fields=["estado", "updated_at"])
    return Response({"status": 1, "error": 0, "message": "Cita cancelada", "values": {"cita": CitaSerializer(cita).data}})
