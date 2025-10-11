# cita/views.py  (REEMPLAZAR)
from rest_framework.decorators import api_view, authentication_classes, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.authentication import TokenAuthentication
from rest_framework.response import Response
from rest_framework import status
from django.shortcuts import get_object_or_404
from django.db import models
from django.contrib.auth import get_user_model

from .models import Cita
from .serializers import CitaSerializer

# ⬇️ Ajusta este import si tu decorador vive en otro módulo
from inmobiliaria.permissions import requiere_permiso 

User = get_user_model()


def _can_view(user, cita: Cita) -> bool:
    if getattr(user, "is_superuser", False):
        return True
    uid = getattr(user, "id", None)
    return uid in (cita.agente_id, cita.cliente_id, (cita.creado_por_id or 0))


def _is_agent_owner(user, cita: Cita) -> bool:
    if getattr(user, "is_superuser", False):
        return True
    return getattr(user, "id", None) == cita.agente_id


def _is_agent_or_client(user, cita: Cita) -> bool:
    if getattr(user, "is_superuser", False):
        return True
    uid = getattr(user, "id", None)
    return uid in (cita.agente_id, cita.cliente_id)


@api_view(["GET"])
@authentication_classes([TokenAuthentication])
@permission_classes([IsAuthenticated])
#@requiere_permiso(componente="Cita", accion="leer")
def listar_citas(request):
    """
    Un agente ve sus citas; un cliente ve las suyas.
    (Admins verán todas si así lo define el decorador o la lógica de privilegios.)
    """
    user = request.user
    qs = Cita.objects.filter(
        models.Q(agente=user) | models.Q(cliente=user)
    ).select_related("agente", "cliente")
    ser = CitaSerializer(qs, many=True)
    return Response({"values": {"citas": ser.data}}, status=status.HTTP_200_OK)


@api_view(["GET"])
@authentication_classes([TokenAuthentication])
@permission_classes([IsAuthenticated])
@requiere_permiso(componente="cita", accion="leer")
def obtener_cita(request, cita_id):
    cita = get_object_or_404(Cita, id=cita_id)
    if not _can_view(request.user, cita):
        return Response({"detail": "Forbidden"}, status=status.HTTP_403_FORBIDDEN)
    ser = CitaSerializer(cita)
    return Response({"values": ser.data}, status=status.HTTP_200_OK)


@api_view(["POST"])
@authentication_classes([TokenAuthentication])
@permission_classes([IsAuthenticated])
@requiere_permiso(componente="cita", accion="crear")
def crear_cita(request):
    # ❌ no metas agente/creado_por en el body; el serializer los setea
    ser = CitaSerializer(data=request.data, context={"request": request})
    if ser.is_valid():
        cita = ser.save()  # aquí ya vienen agente/creado_por = request.user
        return Response(
            {"message": "Cita creada", "values": CitaSerializer(cita).data},
            status=status.HTTP_201_CREATED,
        )
    return Response({"errors": ser.errors}, status=status.HTTP_400_BAD_REQUEST)


@api_view(["POST"])
@authentication_classes([TokenAuthentication])
@permission_classes([IsAuthenticated])
@requiere_permiso(componente="cita", accion="actualizar")
def reprogramar_cita(request, cita_id):
    cita = get_object_or_404(Cita, id=cita_id)
    if not _is_agent_owner(request.user, cita):
        return Response(
            {"detail": "Solo el agente titular puede reprogramar esta cita."},
            status=status.HTTP_403_FORBIDDEN,
        )

    allowed = {"fecha_cita", "hora_inicio", "hora_fin"}
    parcial = {k: v for k, v in request.data.items() if k in allowed}

    ser = CitaSerializer(cita, data=parcial, partial=True)
    if ser.is_valid():
        obj = ser.save(estado="REPROGRAMADA")
        return Response(
            {"message": "Cita reprogramada", "values": CitaSerializer(obj).data},
            status=status.HTTP_200_OK,
        )
    return Response({"errors": ser.errors}, status=status.HTTP_400_BAD_REQUEST)


from datetime import datetime, time
from django.utils.timezone import now as tz_now

def _is_past(cita: Cita) -> bool:
    """Devuelve True si la cita ya terminó (fecha pasada o hoy pero hora_fin ya pasó)."""
    hoy = tz_now().date()
    if cita.fecha_cita < hoy:
        return True
    if cita.fecha_cita > hoy:
        return False
    # fecha == hoy: compara hora_fin con hora actual (aware/naive según tu config)
    hora_actual = tz_now().time()
    return cita.hora_fin <= hora_actual
@api_view(["DELETE", "POST"])
@authentication_classes([TokenAuthentication])
@permission_classes([IsAuthenticated])
@requiere_permiso(componente="cita", accion="eliminar")  # o 'actualizar' según tu policy
def eliminar_cita(request, cita_id):
    cita = get_object_or_404(Cita, id=cita_id)
    if not _is_agent_owner(request.user, cita):
        return Response({"detail": "Solo el agente titular puede eliminar."}, status=status.HTTP_403_FORBIDDEN)

    # 🔒 No permitir eliminar citas vencidas (ya cumplidas)
    if _is_past(cita):
        return Response(
            {"detail": "No se puede eliminar una cita que ya se cumplió. Puedes reprogramar o dejarla como historial."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    # (Opcional) también impedir eliminar CANCELADAS explicitamente:
    # if cita.estado == "CANCELADA":
    #     return Response({"detail": "La cita ya está cancelada."}, status=400)

    cita.delete()
    return Response({"message": "Cita eliminada"}, status=status.HTTP_200_OK)

