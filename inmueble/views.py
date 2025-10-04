from django.shortcuts import render
from rest_framework.decorators import api_view
from rest_framework.response import Response
from rest_framework import status
from django.shortcuts import get_object_or_404
from .models import InmuebleModel, CambioInmuebleModel, TipoInmuebleModel
from .serializers import InmuebleSerializer, CambioInmuebleSerializer, TipoInmuebleSerializer
from inmobiliaria.permissions import requiere_permiso 

# Create your views here.
#TIPO DE INMUEBLES

# --------------------- Crear TipoInmueble ---------------------
@api_view(['POST'])
@requiere_permiso("TipoInmueble", "crear")
def crear_tipo_inmueble(request):
    serializer = TipoInmuebleSerializer(data=request.data)
    if serializer.is_valid():
        serializer.save()
        return Response({
            "status": 1,
            "error": 0,
            "message": "Tipo de inmueble creado correctamente",
            "values": {"tipo_inmueble": serializer.data}
        })
    return Response({
        "status": 0,
        "error": 1,
        "message": "Error al crear tipo de inmueble",
        "values": serializer.errors
    })

# --------------------- Actualizar TipoInmueble ---------------------
@api_view(['PATCH'])
@requiere_permiso("TipoInmueble", "actualizar")
def actualizar_tipo_inmueble(request, tipo_id):
    tipo = get_object_or_404(TipoInmuebleModel, id=tipo_id)
    serializer = TipoInmuebleSerializer(tipo, data=request.data, partial=True)
    if serializer.is_valid():
        serializer.save()
        return Response({
            "status": 1,
            "error": 0,
            "message": "Tipo de inmueble actualizado correctamente",
            "values": {"tipo_inmueble": serializer.data}
        })
    return Response({
        "status": 0,
        "error": 1,
        "message": "Error al actualizar tipo de inmueble",
        "values": serializer.errors
    })

# ELMINAR TIPO INMUEBLE
@api_view(['DELETE'])
@requiere_permiso("TipoInmueble", "eliminar")
def eliminar_tipo_inmueble(request, tipo_id):
    tipo = get_object_or_404(TipoInmuebleModel, id=tipo_id)
    tipo.is_active = False
    tipo.save()
    return Response({
        "status": 1,
        "error": 0,
        "message": f"Tipo de inmueble fué desactivado exitósamente",
        "values": {"tipo_inmueble": TipoInmuebleSerializer(tipo).data}
    })


# ACIVAR TIPO INMUEBLE
@api_view(['PATCH'])
@requiere_permiso("TipoInmueble", "activar")
def activar_tipo_inmueble(request, tipo_id):
    tipo = get_object_or_404(TipoInmuebleModel, id=tipo_id)
    tipo.is_active = True
    tipo.save()
    return Response({
        "status": 1,
        "error": 0,
        "message": f"Tipo de inmueble fué activado exitósamente",
        "values": {"tipo_inmueble": TipoInmuebleSerializer(tipo).data}
    })

# LISTAR TIPO INMUEBLES

@api_view(['GET'])
@requiere_permiso("TipoInmueble","leer") 
def listar_tipo_inmuebles(request):
    tipo_inmueble = TipoInmuebleModel.objects.all()
    serializer = TipoInmuebleSerializer(tipo_inmueble, many=True)
    return Response({
        "status": 1,
        "error": 0,
        "message": "LISTADO DE TIPO DE INMUEBLES",
        "values": {"tipo_inmueble": serializer.data}
    })

# INMUEBLES
#PARA EL AGENTE Y ADMIN, SI LO HACE EL AGENTE NO ENVIA EL ESTADO, PORQUE SERÁ PENDIENTE

@api_view(['POST'])
@requiere_permiso("Inmueble", "crear")
def agente_registrar_inmueble(request):
    data = request.data.copy()
    data['agente'] = request.user.id  # asignamos el agente desde el token
    # data['estado'] = 'pendiente' # estado inicial siempre pendiente
    serializer = InmuebleSerializer(data=data)
    if serializer.is_valid():
        serializer.save()
        return Response({
            "status": 1,
            "error": 0,
            "message": "INMUEBLE REGISTRADO CORRECTAMENTE ESPERANDO APROBACION DEL ADMINISTRADOR",
            "values": {"inmueble": serializer.data}
        })
    
    return Response({
        "status": 0,
        "error": 1,
        "message": "ERROR AL REGISTRAR EL INMUEBLE",
        "values": serializer.errors
    })


# EL AGENTE ENVIA SOLICITUD AL ADMIN PARA HACER CAMBIOS

@api_view(['POST'])
@requiere_permiso("Cambio_inmueble", "crear")
def solicitar_cambio_inmueble(request, inmueble_id):
    inmueble = get_object_or_404(InmuebleModel, id=inmueble_id)
    agente = request.user  # usuario autenticado
    # Validación: solo el agente asignado puede solicitar cambios
    if inmueble.agente != agente:
        return Response({
            "status": 0,
            "error": 1,
            "message": "Solo el agente asignado puede solicitar cambios para este inmueble."
        })

    # Crear registro de cambio con solo los campos enviados
    cambio_data = request.data.copy()
    print(agente.id)
    cambio_data['agente'] = agente.id

    serializer = CambioInmuebleSerializer(data=cambio_data)
    if serializer.is_valid():
        serializer.save()
        return Response({
            "status": 1,
            "error": 0,
            "message": "Cambio solicitado correctamente. Esperando aprobación del admin.",
            "values": {"cambio": serializer.data}
        })
    
    return Response({
        "status": 0,
        "error": 1,
        "message": "Error al solicitar cambio",
        "values": serializer.errors
    })