# inmueble/views.py
from django.shortcuts import render
from rest_framework.decorators import api_view
from rest_framework.response import Response
from rest_framework import status
from django.shortcuts import get_object_or_404
from .models import InmuebleModel, CambioInmuebleModel, TipoInmuebleModel, AnuncioModel, FotoModel
from .serializers import InmuebleSerializer, CambioInmuebleSerializer, TipoInmuebleSerializer
from .serializers import AnuncioSerializer
from utils.encrypted_logger import registrar_accion
from inmobiliaria.permissions import requiere_permiso 
from datetime import date
from django.db.models import Q, Count
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
# EL AGENTE REGISTRA INMUEBLE (PENDIENTE DE APROBACION DEL ADMIN)
from usuario.models import Usuario

@api_view(['POST'])
@requiere_permiso("Inmueble", "crear")
def agente_registrar_inmueble(request):
    data = request.data.copy()
    data['agente'] = request.user.id

    serializer = InmuebleSerializer(data=data)
    if serializer.is_valid():
        inmueble = serializer.save()

        # 👇 CAMBIO MÍNIMO: crear fotos desde URLs si vinieron
        urls = request.data.get('fotos_urls', [])
        if isinstance(urls, list) and urls:
            FotoModel.objects.bulk_create(
                [FotoModel(inmueble=inmueble, url=u.strip()) for u in urls if isinstance(u, str) and u.strip()]
            )

        # re-serializa para incluir fotos recién creadas
        out = InmuebleSerializer(inmueble)
        return Response({
            "status": 1,
            "error": 0,
            "message": "INMUEBLE REGISTRADO CORRECTAMENTE ESPERANDO APROBACION DEL ADMINISTRADOR",
            "values": {"inmueble": out.data}
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
    cambio_data['inmueble'] = inmueble.id    

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

# ADMIN ACEPTA INMUEBLE DEL AGENTE
@api_view(["PATCH"])
@requiere_permiso("Inmueble", "actualizar")
def rechazar_inmueble(request, inmueble_id):
    """
    Permite que un administrador apruebe un inmueble pendiente.
    URL: PATCH /api/inmuebles/aprobar/<inmueble_id>/
    """

    inmueble = get_object_or_404(InmuebleModel, pk=inmueble_id)

    # Verificar si ya está aprobado
    if inmueble.estado == "aprobado":
        return Response({
            "status": 2,
            "error": 1,
            "message": "El inmueble ya fue aprobado anteriormente."
        })

    # Cambiar estado a aprobado
    inmueble.estado = "rechazado"
    inmueble.save()

    # Registrar en la bitácora
    registrar_accion(
        usuario=request.user,
        accion=f"Rechazó el inmueble con ID: {inmueble.id}",
        ip=request.META.get("REMOTE_ADDR")
    )

    return Response({
        "status": 1,
        "error": 0,
        "message": "INMUEBLE RECHAZADO CORRECTAMENTE",
        "values": {
            "id": inmueble.id,
            "titulo": inmueble.titulo,
            "estado": inmueble.estado
        }
    })

@api_view(["PATCH"])
@requiere_permiso("Inmueble", "actualizar")
def aceptar_inmueble(request, inmueble_id):
    """
    Permite que un administrador apruebe un inmueble pendiente.
    URL: PATCH /api/inmuebles/aprobar/<inmueble_id>/
    """

    inmueble = get_object_or_404(InmuebleModel, pk=inmueble_id)

    # Verificar si ya está aprobado
    if inmueble.estado == "aprobado":
        return Response({
            "status": 2,
            "error": 1,
            "message": "El inmueble ya fue aprobado anteriormente."
        })

    # Cambiar estado a aprobado
    inmueble.estado = "aprobado"
    inmueble.save()

    # Registrar en la bitácora
    registrar_accion(
        usuario=request.user,
        accion=f"Aprobó el inmueble con ID: {inmueble.id}",
        ip=request.META.get("REMOTE_ADDR")
    )

    return Response({
        "status": 1,
        "error": 0,
        "message": "INMUEBLE APROBADO CORRECTAMENTE",
        "values": {
            "id": inmueble.id,
            "titulo": inmueble.titulo,
            "estado": inmueble.estado
        }
    })

# EL ADMIN APRUEBA SOLICITUD DE CAMBIO EN LOS DATOS DE LA NIMOBILIARIA

@api_view(["PATCH"])
@requiere_permiso("Cambio_inmueble", "actualizar")
def aceptar_cambio_inmueble(request, cambio_id):
    cambio = get_object_or_404(CambioInmuebleModel, id=cambio_id)

    if cambio.estado != "pendiente":
        return Response({
            "status": 0,
            "error": 1,
            "message": f"El cambio ya fue {cambio.estado.lower()} anteriormente."
        })
    cambio.fecha_revision = date.today()
    inmueble = get_object_or_404(InmuebleModel, id=cambio.inmueble.id)

    # Actualizar solo los campos que no sean nulos
    campos_actualizables = [
        "titulo", "descripcion", "direccion", "ciudad", "zona",
        "superficie", "dormitorios", "baños", "precio",
        "tipo_operacion", "latitud", "longitud"
    ]

    for campo in campos_actualizables:
        valor = getattr(cambio, campo)
        if valor not in [None, ""]:
            setattr(inmueble, campo, valor)

    inmueble.save()

    # Actualizar estado del cambio
    cambio.estado = "aprobado"
    cambio.save()

    # Registrar acción en bitácora
    registrar_accion(
        usuario=request.user,
        accion=f"Aprobó el cambio de inmueble ID: {inmueble.id} (Cambio ID: {cambio.id})",
        ip=request.META.get("REMOTE_ADDR")
    )

    return Response({
        "status": 1,
        "error": 0,
        "message": "Cambio de inmueble aprobado y aplicado correctamente.",
        "values": {
            "cambio_id": cambio.id,
            "inmueble_id": inmueble.id,
            "estado_cambio": cambio.estado
        }
    })


@api_view(["PATCH"])
@requiere_permiso("Cambio_inmueble", "actualizar")
def rechazar_cambio_inmueble(request, cambio_id):
    cambio = get_object_or_404(CambioInmuebleModel, id=cambio_id)

    if cambio.estado != "pendiente":
        return Response({
            "status": 0,
            "error": 1,
            "message": f"El cambio ya fue {cambio.estado.lower()} anteriormente."
        })
    cambio.fecha_revision = date.today()
    inmueble = get_object_or_404(InmuebleModel, id=cambio.inmueble.id)

    # Actualizar estado del cambio
    cambio.estado = "rechazado"
    cambio.save()

    # Registrar acción en bitácora
    registrar_accion(
        usuario=request.user,
        accion=f"Rechazó el cambio de inmueble ID: {inmueble.id} (Cambio ID: {cambio.id})",
        ip=request.META.get("REMOTE_ADDR")
    )

    return Response({
        "status": 1,
        "error": 0,
        "message": "Cambio de inmueble rechazado y aplicado correctamente.",
        "values": {
            "cambio_id": cambio.id,
            "inmueble_id": inmueble.id,
            "estado_cambio": cambio.estado
        }
    })

@api_view(['PATCH'])
@requiere_permiso("Inmueble", "actualizar")
def editar_inmueble(request, inmueble_id):
    # Buscar inmueble
    inmueble = get_object_or_404(InmuebleModel, id=inmueble_id)

    # Actualizar datos con los que vengan en el request
    serializer = InmuebleSerializer(inmueble, data=request.data, partial=True)
    if serializer.is_valid():
        serializer.save()

        # Registrar en la bitácora
        registrar_accion(
            usuario=request.user,
            accion=f"El usuario con ID {request.user.id} editó el inmueble con ID {inmueble.id}",
            ip=request.META.get("REMOTE_ADDR")
        )

        return Response({
            "status": 1,
            "error": 0,
            "message": "Inmueble actualizado correctamente.",
            "values": serializer.data
        })
    
    return Response({
        "status": 0,
        "error": 1,
        "message": "Error al actualizar el inmueble.",
        "values": serializer.errors
    })

# GESTION DE ANUNCIOS

@api_view(['GET'])
@requiere_permiso("Anuncio", "leer")
def listar_anuncios_disponibles(request):
    # Filtramos los anuncios disponibles
    anuncios = AnuncioModel.objects.filter(estado='disponible')

    # Obtenemos los IDs de los inmuebles relacionados
    inmueble_ids = anuncios.values_list('inmueble_id', flat=True)

    # Filtramos los inmuebles correspondientes
    inmuebles = InmuebleModel.objects.filter(id__in=inmueble_ids)

    # Serializamos
    serializer = InmuebleSerializer(inmuebles, many=True)

    return Response({
        "status": 1,
        "error": 0,
        "message": "LISTADO DE INMUEBLES DISPONIBLES",
        "values": {"inmueble": serializer.data}
    })



def _ok(values, message="OK"):
    return Response({"status": 1, "error": 0, "message": message, "values": values})

def _err(errors, message="ERROR", http=status.HTTP_400_BAD_REQUEST):
    return Response({"status": 0, "error": 1, "message": message, "values": errors}, status=http)

# Listar inmuebles aprobados y publicados (anuncio activo)
@api_view(['GET'])
def listar_inmuebles(request):
    """
    Lista solo los inmuebles aprobados y con anuncio activo (publicados).
    """
    qs = (
        InmuebleModel.objects
        .filter(estado="aprobado", is_active=True, anuncio__is_active=True)
        .select_related("tipo_inmueble", "anuncio")
        .prefetch_related("fotos")
        .order_by("-id")
    )

    # Filtros opcionales
    tipo = request.GET.get("tipo")
    if tipo:
        qs = qs.filter(tipo_operacion__iexact=tipo)

    ciudad = request.GET.get("ciudad")
    if ciudad:
        qs = qs.filter(ciudad__icontains=ciudad)

    zona = request.GET.get("zona")
    if zona:
        qs = qs.filter(zona__icontains=zona)

    q = request.GET.get("q")
    if q:
        qs = qs.filter(
            Q(titulo__icontains=q) |
            Q(descripcion__icontains=q) |
            Q(direccion__icontains=q)
        )

    serializer = InmuebleSerializer(qs, many=True, context={'request': request})
    return Response({
        "status": 1,
        "error": 0,
        "message": "LISTA DE INMUEBLES APROBADOS Y PUBLICADOS",
        "values": {"inmuebles": serializer.data}
    })



@api_view(['GET'])
def obtener_inmueble(request, pk):
    obj = get_object_or_404(
        InmuebleModel.objects.prefetch_related('fotos'),
        pk=pk
    )
    data = InmuebleSerializer(obj, context={'request': request}).data
    return _ok({"inmueble": data}, message="DETALLE DE INMUEBLE")

@api_view(['GET'])
@requiere_permiso("Inmueble", "leer")
def listar_inmuebles_por_estado(request):
    """
    Retorna inmuebles filtrados por estado:
    ?estado=pendiente | aprobado | rechazado | todos
    Ejemplos:
      /inmueble/listar_inmuebles_por_estado/?estado=aprobado
      /inmueble/listar_inmuebles_por_estado/?estado=todos
    """
    try:
        estado = request.GET.get('estado', 'pendiente').lower()

        inmuebles = InmuebleModel.objects.filter(is_active=True)

        if estado != 'todos':
            inmuebles = inmuebles.filter(estado=estado)

        serializer = InmuebleSerializer(inmuebles, many=True)

        return Response({
            "status": 1,
            "error": 0,
            "message": f"LISTADO DE INMUEBLES ({estado.upper()})",
            "values": {"inmuebles": serializer.data}
        })
    except Exception as e:
        print(f"⚠ Error en listar_inmuebles_por_estado: {e}")
        return Response({
            "status": 0,
            "error": 1,
            "message": f"Error interno: {str(e)}"
        }, status=500)

# =========================================================
# 🟢 PUBLICAR INMUEBLE (solo agente con inmueble aprobado)
# =========================================================
@api_view(['POST'])
@requiere_permiso("Anuncio", "crear")
def publicar_inmueble(request, inmueble_id):
    """
    Permite al agente publicar un inmueble aprobado.
    Si ya estaba publicado, lo reactiva.
    """
    inmueble = get_object_or_404(InmuebleModel, id=inmueble_id)
    agente = request.user

    # Solo el agente dueño puede publicar
    if inmueble.agente != agente:
        return Response({
            "status": 0, "error": 1,
            "message": "No tienes permiso para publicar este inmueble."
        }, status=status.HTTP_403_FORBIDDEN)

    # Solo se puede publicar si está aprobado
    if inmueble.estado != "aprobado":
        return Response({
            "status": 0, "error": 1,
            "message": "El inmueble debe estar aprobado antes de publicarse."
        }, status=status.HTTP_400_BAD_REQUEST)

    # Crear o reactivar anuncio
    anuncio, created = AnuncioModel.objects.get_or_create(
        inmueble=inmueble,
        defaults={"estado": "disponible", "is_active": True}  # 🟩 aseguramos que se marque como activo
    )

    # 🟩 Si ya existía, reactivar
    if not created:
        if not anuncio.is_active or anuncio.estado != "disponible":
            anuncio.is_active = True
            anuncio.estado = "disponible"
            anuncio.save()
            msg = "Anuncio reactivado correctamente."
        else:
            msg = "El inmueble ya estaba publicado."
    else:
        msg = "Inmueble publicado correctamente."

    # 🟩 Registrar acción en bitácora (mantienes tu lógica)
    registrar_accion(
        usuario=agente,
        accion=f"Publicó o reactivó el inmueble ID {inmueble.id}",
        ip=request.META.get("REMOTE_ADDR")
    )

    # 🟩 Respuesta estandarizada
    return Response({
        "status": 1,
        "error": 0,
        "message": msg,
        "values": {
            "inmueble_id": inmueble.id,
            "anuncio_id": anuncio.id,
            "estado_anuncio": anuncio.estado,
            "publicado": anuncio.is_active  # 🟩 agregado para claridad
        }
    })


@api_view(['GET'])
@requiere_permiso("Inmueble", "leer")
def mis_inmuebles(request):
    """
    ?estado = pendiente | aprobado | rechazado | publicados | todos
    - 'aprobado'    => aprobados SIN anuncio activo/disponible
    - 'publicados'  => aprobados CON anuncio activo/disponible
    """
    estado = (request.GET.get('estado') or 'todos').lower()

    qs = (
        InmuebleModel.objects
        .filter(agente=request.user, is_active=True)
        .select_related('tipo_inmueble')
        .prefetch_related('fotos')
        .order_by('-id')
    )

    if estado == 'pendiente':
        qs = qs.filter(estado='pendiente')
    elif estado == 'rechazado':
        qs = qs.filter(estado='rechazado')
    elif estado == 'aprobado':
        # 👇 aprobados, pero NO publicados
        qs = qs.filter(estado='aprobado')\
               .exclude(anuncio__is_active=True, anuncio__estado='disponible')
    elif estado == 'publicados':
        # 👇 aprobados y publicados
        qs = qs.filter(estado='aprobado', anuncio__is_active=True, anuncio__estado='disponible')
    # else: 'todos' => sin filtro extra

    serializer = InmuebleSerializer(qs, many=True)
    return Response({
        "status": 1, "error": 0,
        "message": f"MIS INMUEBLES ({estado.upper()})",
        "values": {"inmuebles": serializer.data}
    })

# Resumen de mis inmuebles (agente)
@api_view(['GET'])
@requiere_permiso("Inmueble", "leer")
def resumen_mis_inmuebles(request):
    base = InmuebleModel.objects.filter(agente=request.user, is_active=True)

    aprobados_sin_publicar = Q(estado='aprobado') & ~Q(
        anuncio__is_active=True, anuncio__estado='disponible'
    )
    publicados_q = Q(estado='aprobado', anuncio__is_active=True, anuncio__estado='disponible')

    agg = base.aggregate(
        pendientes=Count('id', filter=Q(estado='pendiente')),
        aprobados=Count('id', filter=aprobados_sin_publicar),   # 👈
        rechazados=Count('id', filter=Q(estado='rechazado')),
        publicados=Count('id', filter=publicados_q),
        todos=Count('id'),
    )
    return Response({
        "status": 1, "error": 0,
        "message": "RESUMEN MIS INMUEBLES",
        "values": agg
    })

@api_view(['GET'])
@requiere_permiso("Anuncio", "leer")
def admin_listar_anuncios(request):
    """
    Lista TODOS los anuncios con filtros
    ?estado=disponible&prioridad=destacado&agente_id=1&show_all=true
    """
    estado = request.GET.get('estado')
    prioridad = request.GET.get('prioridad')
    agente_id = request.GET.get('agente_id')
    show_all = request.GET.get('show_all')
    
    if show_all and show_all.lower() == 'true':
        anuncios = AnuncioModel.objects.all()  #TODOS 
    else:
        anuncios = AnuncioModel.objects.filter(is_active=True)  #activos
    
    # Filtros opcionales
    if estado:
        anuncios = anuncios.filter(estado=estado)
    if prioridad:
        anuncios = anuncios.filter(prioridad=prioridad)
    if agente_id:
        anuncios = anuncios.filter(inmueble__agente_id=agente_id)
    
    anuncios = anuncios.select_related('inmueble', 'inmueble__agente')
    
    serializer = AnuncioSerializer(anuncios, many=True)
    return Response({
        "status": 1,
        "error": 0,
        "message": "LISTADO DE ANUNCIOS", 
        "values": {"anuncios": serializer.data}
    })

@api_view(['POST'])
@requiere_permiso("Anuncio", "crear")
def admin_crear_anuncio(request, inmueble_id):
    """
    Crea anuncio para inmueble aprobado
    """
    inmueble = get_object_or_404(InmuebleModel, id=inmueble_id)
    
    if inmueble.estado != "aprobado":
        return Response({
            "status": 0, "error": 1,
            "message": "Solo inmuebles aprobados pueden tener anuncio."
        }, status=400)

    if hasattr(inmueble, 'anuncio') and inmueble.anuncio.is_active:
        return Response({
            "status": 0, "error": 1,
            "message": "Ya existe un anuncio activo para este inmueble."
        }, status=400)

    anuncio = AnuncioModel.objects.create(
        inmueble=inmueble,
        estado=request.data.get('estado', 'disponible'),
        prioridad=request.data.get('prioridad', 'normal')  # 🆕 Prioridad
    )

    serializer = AnuncioSerializer(anuncio)
    return Response({
        "status": 1,
        "error": 0,
        "message": "Anuncio creado exitosamente",
        "values": {"anuncio": serializer.data}
    })

@api_view(['PATCH'])
@requiere_permiso("Anuncio", "actualizar")
def admin_actualizar_anuncio(request, anuncio_id):
    anuncio = get_object_or_404(AnuncioModel, id=anuncio_id)
    
    serializer = AnuncioSerializer(anuncio, data=request.data, partial=True)
    if serializer.is_valid():
        serializer.save()  # 🎪 La lógica automática se ejecuta en el modelo
        return Response({
            "status": 1,
            "error": 0,
            "message": "Anuncio actualizado correctamente",
            "values": {"anuncio": serializer.data}
        })
    
    return Response({
        "status": 0,
        "error": 1,
        "message": "Error al actualizar anuncio",
        "values": serializer.errors
    })

@api_view(['GET'])
@requiere_permiso("Anuncio", "crear")
def admin_inmuebles_sin_anuncio(request):
    """
    Inmuebles aprobados que NO tienen anuncio activo
    Perfecto para crear nuevos anuncios
    """
    inmuebles = InmuebleModel.objects.filter(
        estado="aprobado",
        is_active=True
    ).exclude(
        Q(anuncio__is_active=True) | Q(anuncio__isnull=False)
    ).select_related('agente', 'tipo_inmueble').prefetch_related('fotos')

    serializer = InmuebleSerializer(inmuebles, many=True)
    return Response({
        "status": 1,
        "error": 0,
        "message": "INMUEBLES APROBADOS SIN ANUNCIO",
        "values": {"inmuebles": serializer.data}
    })

@api_view(['GET'])
@requiere_permiso("Anuncio", "leer")
def admin_obtener_anuncio(request, anuncio_id):
    """Obtiene un anuncio específico con información completa"""
    anuncio = get_object_or_404(
        AnuncioModel.objects.select_related(
            'inmueble',
            'inmueble__agente',
            'inmueble__tipo_inmueble'
        ).prefetch_related(
            'inmueble__fotos'  # ✅ Precargar fotos
        ),
        id=anuncio_id
    )
    
    serializer = AnuncioSerializer(anuncio)
    return Response({
        "status": 1,
        "error": 0,
        "message": "DETALLE DEL ANUNCIO",
        "values": {"anuncio": serializer.data}
    })