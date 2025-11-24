# inmueble/views.py
from django.shortcuts import render
from rest_framework.decorators import api_view
from rest_framework.response import Response
from rest_framework import status
from django.shortcuts import get_object_or_404
from .models import InmuebleModel, CambioInmuebleModel, TipoInmuebleModel, AnuncioModel, FotoModel
from .serializers import InmuebleSerializer, CambioInmuebleSerializer, TipoInmuebleSerializer, InmuebleMapaSerializer
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
    """
    El agente solicita una corrección sobre un inmueble rechazado.
    Crea un registro de cambio y marca el inmueble nuevamente como pendiente.
    """
    inmueble = get_object_or_404(InmuebleModel, id=inmueble_id)
    agente = request.user

    # Solo el agente dueño puede solicitar cambios
    if inmueble.agente != agente:
        return Response({
            "status": 0,
            "error": 1,
            "message": "Solo el agente asignado puede solicitar cambios para este inmueble."
        }, status=status.HTTP_403_FORBIDDEN)

    # Solo se puede reenviar si fue rechazado
    if inmueble.estado != "rechazado":
        return Response({
            "status": 0,
            "error": 1,
            "message": "Solo puedes reenviar inmuebles rechazados."
        }, status=status.HTTP_400_BAD_REQUEST)

    # Crear registro de cambio con los campos corregidos
    cambio_data = request.data.copy()
    cambio_data['agente'] = agente.id
    cambio_data['inmueble'] = inmueble.id

    serializer = CambioInmuebleSerializer(data=cambio_data)
    if serializer.is_valid():
        serializer.save()

        # Limpiar motivo de rechazo y poner el inmueble como pendiente
        inmueble.motivo_rechazo = ""
        inmueble.estado = "pendiente"
        inmueble.save()

        registrar_accion(
            usuario=agente,
            accion=f"Reenvió el inmueble ID {inmueble.id} para revisión (Cambio ID {serializer.instance.id})",
            ip=request.META.get("REMOTE_ADDR")
        )

        return Response({
            "status": 1,
            "error": 0,
            "message": "Cambio reenviado correctamente. El inmueble vuelve a revisión del administrador.",
            "values": {"cambio": serializer.data}
        })

    return Response({
        "status": 0,
        "error": 1,
        "message": "Error al reenviar la solicitud de cambio.",
        "values": serializer.errors
    })


# ADMIN ACEPTA INMUEBLE DEL AGENTE
@api_view(["PATCH"])
@requiere_permiso("Inmueble", "actualizar")
def rechazar_inmueble(request, inmueble_id):
    """
    Permite al administrador rechazar un inmueble con un motivo de rechazo.
    """
    inmueble = get_object_or_404(InmuebleModel, pk=inmueble_id)

    # Obtener el motivo del body
    motivo = request.data.get("motivo", "").strip()

    # Cambiar estado y guardar motivo
    inmueble.estado = "rechazado"
    inmueble.motivo_rechazo = motivo or "Sin motivo especificado"
    inmueble.save()

    registrar_accion(
        usuario=request.user,
        accion=f"Rechazó el inmueble ID {inmueble.id} (Motivo: {motivo})",
        ip=request.META.get("REMOTE_ADDR")
    )

    return Response({
        "status": 1,
        "error": 0,
        "message": "Inmueble rechazado correctamente.",
        "values": {
            "id": inmueble.id,
            "titulo": inmueble.titulo,
            "estado": inmueble.estado,
            "motivo_rechazo": inmueble.motivo_rechazo
        }
    })

@api_view(["PATCH"])
@requiere_permiso("Inmueble", "actualizar")
def aceptar_inmueble(request, inmueble_id):
    """
    Permite al administrador aprobar un inmueble pendiente.
    """
    inmueble = get_object_or_404(InmuebleModel, pk=inmueble_id)

    if inmueble.estado == "aprobado":
        return Response({
            "status": 2,
            "error": 1,
            "message": "El inmueble ya fue aprobado anteriormente."
        })

    inmueble.estado = "aprobado"
    inmueble.motivo_rechazo = ""  # 👈 limpiar motivo al aprobar
    inmueble.save()

    registrar_accion(
        usuario=request.user,
        accion=f"Aprobó el inmueble ID {inmueble.id}",
        ip=request.META.get("REMOTE_ADDR")
    )

    return Response({
        "status": 1,
        "error": 0,
        "message": "Inmueble aprobado correctamente.",
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
    inmueble.motivo_rechazo = ""
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
        .filter(estado="aprobado", is_active=True, anuncio__is_active=True,anuncio__estado='disponible')
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
#Listar inmuebles aprobados no publicados
@api_view(['GET'])
def listar_inmuebles_aprobados_no_publicados(request):
    """
    Lista inmuebles aprobados que NO están publicados.
    Para seleccionar en contratos - inmuebles disponibles pero sin anuncio activo.
    """
    try:
        # Filtrar: aprobados, activos, pero SIN anuncio activo O con anuncio no disponible
        qs = (
            InmuebleModel.objects
            .filter(estado="aprobado", is_active=True)
            .filter(
                Q(anuncio__isnull=True) |  # No tiene anuncio
                Q(anuncio__is_active=False) |  # Anuncio inactivo
                Q(anuncio__estado='no_publicado')  # Anuncio no publicado
            )
            .select_related("tipo_inmueble")
            .prefetch_related("fotos")
            .order_by("-id")
            .distinct()
        )

        # Filtro opcional por búsqueda
        q = request.GET.get("q")
        if q:
            qs = qs.filter(
                Q(titulo__icontains=q) |
                Q(descripcion__icontains=q) |
                Q(direccion__icontains=q) |
                Q(ciudad__icontains=q) |
                Q(zona__icontains=q)
            )

        serializer = InmuebleSerializer(qs, many=True, context={'request': request})
        
        return Response({
            "status": 1,
            "error": 0,
            "message": "LISTA DE INMUEBLES APROBADOS NO PUBLICADOS",
            "values": {"inmuebles": serializer.data}
        })

    except Exception as e:
        return Response({
            "status": 0,
            "error": 1,
            "message": f"Error al cargar inmuebles: {str(e)}",
            "values": {"inmuebles": []}
        }, status=500)


@api_view(['GET'])
def obtener_inmueble(request, pk):
    obj = get_object_or_404(
        InmuebleModel.objects.select_related('anuncio').prefetch_related('fotos'),  # 👈 AÑADIDO
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

        inmuebles = (
        InmuebleModel.objects
        .filter(is_active=True)
        .select_related('anuncio')                    # 👈 AÑADIDO
         )

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
        return Response({
            "status": 0,
            "error": 1,
            "message": f"Error interno: {str(e)}"
        }, status=500)
@api_view(['GET'])
def estado_anuncio_por_inmueble(request):
    inmueble_id = request.GET.get("inmueble")
    if not inmueble_id:
        return Response({"status": 0, "error": 1, "message": "Falta parámetro 'inmueble'."}, status=400)

    try:
        an = AnuncioModel.objects.select_related('inmueble').get(inmueble_id=inmueble_id)
    except AnuncioModel.DoesNotExist:
        return Response({"status": 1, "error": 0, "message": "SIN ANUNCIO", "values": {"tiene_anuncio": False, "anuncio": None, "inmueble": int(inmueble_id)}})

    return Response({
        "status": 1, "error": 0, "message": "ESTADO DE ANUNCIO",
        "values": {"tiene_anuncio": True, "anuncio": {
            "id": an.id, "inmueble": an.inmueble_id,
            "estado": an.estado, "is_active": an.is_active,
            "fecha_publicacion": an.fecha_publicacion,
        }}
    })

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
        .select_related('tipo_inmueble', 'anuncio') 
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



@api_view(['GET'])
@requiere_permiso("Inmueble", "leer")
def todos_mis_inmuebles(request):
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
               .exclude( anuncio__estado='disponible')
    elif estado == 'publicados':
        # 👇 aprobados y publicados
        qs = qs.filter(estado='aprobado',anuncio__isnull=False)
    # else: 'todos' => sin filtro extra

    serializer = InmuebleSerializer(qs, many=True)
    return Response({
        "status": 1, "error": 0,
        "message": f"MIS INMUEBLES ({estado.upper()})",
        "values": {"inmuebles": serializer.data}
    })



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
@requiere_permiso("Inmueble", "leer")
def historial_publicaciones(request):
    inmuebles = InmuebleModel.objects.filter(agente=request.user)
    data = []
    for i in inmuebles:
        anuncio = getattr(i, "anuncio", None)
        data.append({
            "id": i.id,
            "titulo": i.titulo,
            "estado_inmueble": i.estado,
            "estado_publicacion": anuncio.estado if anuncio else None,
            "publicado": bool(anuncio and anuncio.is_active),
            "fecha_publicacion": anuncio.fecha_publicacion if anuncio else None,
            "precio": i.precio,
            "ciudad": i.ciudad,
        })
    return Response({
        "status": 1, "error": 0,
        "message": "HISTORIAL DE PUBLICACIONES",
        "values": data
    })

# ✅ Reenviar inmueble rechazado (Agente corrige y vuelve a enviar)
@api_view(["PATCH"])
@requiere_permiso("Inmueble", "actualizar")
def corregir_y_reenviar_inmueble(request, inmueble_id):
    """
    Permite al agente reenviar un inmueble rechazado después de corregirlo.
    Cambia el estado a 'pendiente' y limpia el motivo de rechazo.
    """
    inmueble = get_object_or_404(InmuebleModel, id=inmueble_id)

    # Solo el agente dueño puede reenviar su inmueble
    if inmueble.agente != request.user:
        return Response({
            "status": 0,
            "error": 1,
            "message": "No puedes reenviar un inmueble que no te pertenece."
        }, status=status.HTTP_403_FORBIDDEN)

    if inmueble.estado != "rechazado":
        return Response({
            "status": 0,
            "error": 1,
            "message": "Solo se pueden reenviar inmuebles rechazados."
        }, status=status.HTTP_400_BAD_REQUEST)

    inmueble.estado = "pendiente"
    inmueble.motivo_rechazo = ""
    inmueble.save()

    registrar_accion(
        usuario=request.user,
        accion=f"Corrigió y reenvió inmueble ID {inmueble.id}",
        ip=request.META.get("REMOTE_ADDR")
    )

    return Response({
        "status": 1,
        "error": 0,
        "message": "Inmueble reenviado para revisión del administrador.",
        "values": {
            "id": inmueble.id,
            "estado": inmueble.estado
        }
    })
@api_view(["GET"])
@requiere_permiso("Inmueble", "leer")
def listar_inmuebles_agente(request):
    """
    Retorna todos los inmuebles registrados por el agente autenticado.
    Incluye los rechazados (con motivo), aprobados y pendientes.
    Protegido por permisos del componente 'Inmueble' → acción 'leer'.
    """
    agente = request.user

    # Filtra solo los inmuebles del agente autenticado
    inmuebles = InmuebleModel.objects.filter(agente=agente).order_by("-id")

    # Serializa los resultados
    serializer = InmuebleSerializer(inmuebles, many=True)

    # Devuelve la respuesta estándar
    return Response({
        "status": 1,
        "error": 0,
        "values": serializer.data
    }, status=status.HTTP_200_OK)

@api_view(['PUT'])
@requiere_permiso("Inmueble", "actualizar")
def solicitar_correccion_inmueble(request, inmueble_id):
    """
    Permite al agente reenviar un inmueble rechazado con los datos corregidos.
    Actualiza el inmueble, lo marca como 'pendiente' y limpia el motivo de rechazo.
    """
    inmueble = get_object_or_404(InmuebleModel, id=inmueble_id)
    agente = request.user

    # Solo el agente dueño puede reenviar su inmueble
    if inmueble.agente != agente:
        return Response({
            "status": 0,
            "error": 1,
            "message": "No tienes permiso para modificar este inmueble."
        }, status=status.HTTP_403_FORBIDDEN)

    # Solo se puede reenviar si estaba rechazado
    if inmueble.estado != "rechazado":
        return Response({
            "status": 0,
            "error": 1,
            "message": "Solo los inmuebles rechazados pueden ser reenviados."
        }, status=status.HTTP_400_BAD_REQUEST)

    # Actualizar los datos corregidos
    serializer = InmuebleSerializer(inmueble, data=request.data, partial=True)
    if serializer.is_valid():
        serializer.save(estado="pendiente", motivo_rechazo="")

        # Registrar acción (opcional)
        registrar_accion(
            usuario=request.user,
            accion=f"Corrigió y reenviò inmueble ID {inmueble.id}",
            ip=request.META.get("REMOTE_ADDR")
        )

        return Response({
            "status": 1,
            "error": 0,
            "message": "Inmueble corregido y reenviado correctamente.",
            "values": serializer.data
        }, status=status.HTTP_200_OK)

    return Response({
        "status": 0,
        "error": 1,
        "message": "Datos inválidos.",
        "details": serializer.errors
    }, status=status.HTTP_400_BAD_REQUEST)
# =========================================================
# 🟢 CREAR / ACTUALIZAR ANUNCIOS con @requiere_permiso
# =========================================================


@api_view(['POST'])
@requiere_permiso("Anuncio", "crear")
def anuncio_crear(request):
    """
    Crea (o actualiza si ya existe) el anuncio del inmueble con un estado comercial:
    'vendido' | 'alquilado' | 'anticretico'
    Body:
    {
      "inmueble": <id>,
      "estado": "alquilado",
      "is_active": true
    }
    """
    VALIDOS = {"vendido", "alquilado", "anticretico","disponible"}

    inmueble_id = request.data.get("inmueble")
    estado = str(request.data.get("estado", "")).lower()
    is_active = bool(request.data.get("is_active", True))
    if not inmueble_id:
        return Response({
            "status": 0, "error": 1,
            "message": "Debe enviar 'inmueble' (id).",
            "values": {"inmueble": ["Este campo es requerido."]}
        }, status=status.HTTP_400_BAD_REQUEST)
    if estado not in VALIDOS:
        return Response({
            "status": 0, "error": 1,
            "message": "Estado inválido.",
            "values": {"estado": [f"Use uno de: {list(VALIDOS)}"]}
        }, status=status.HTTP_400_BAD_REQUEST)
    inmueble = get_object_or_404(InmuebleModel, id=inmueble_id)
    anuncio, created = AnuncioModel.objects.update_or_create(
        inmueble=inmueble,
        defaults={"estado": estado, "is_active": is_active},
    )
    if estado == "disponible":
        anuncio.is_active = True

    anuncio.save()
    return Response({
        "status": 1,
        "error": 0,
        "message": "Anuncio creado correctamente" if created else "Anuncio actualizado correctamente",
        "values": {
            "id": anuncio.id,
            "inmueble": inmueble.id,
            "estado": anuncio.estado,
            "is_active": anuncio.is_active
        }
    }, status=status.HTTP_201_CREATED if created else status.HTTP_200_OK)


@api_view(['PATCH'])
@requiere_permiso("Anuncio", "actualizar")
def anuncio_actualizar(request, anuncio_id):
    """
    Actualiza 'estado' y/o 'is_active' de un anuncio existente.
    Body (cualquiera de ellos):
    { "estado": "vendido" }  |  { "is_active": false }  |  ambos
    """
    VALIDOS = {"vendido", "alquilado", "anticretico","disponible"}

    anuncio = get_object_or_404(AnuncioModel, id=anuncio_id)

    estado = request.data.get("estado")
    if estado is not None:
        estado = str(estado).lower()
        if estado not in VALIDOS:
            return Response({
                "status": 0, "error": 1,
                "message": "Estado inválido.",
                "values": {"estado": [f"Use uno de: {list(VALIDOS)}"]}
            }, status=status.HTTP_400_BAD_REQUEST)
        anuncio.estado = estado

    if "is_active" in request.data:
        anuncio.is_active = bool(request.data.get("is_active"))
    if estado == "disponible":
        anuncio.is_active = True


    anuncio.save()

    return Response({
        "status": 1,
        "error": 0,
        "message": "Anuncio actualizado correctamente",
        "values": {
            "id": anuncio.id,
            "inmueble": anuncio.inmueble_id,
            "estado": anuncio.estado,
            "is_active": anuncio.is_active
        }
    })
# inmueble/views.py
@api_view(['GET'])
#@requiere_permiso("Anuncio", "leer")
def estado_anuncio_por_id(request, anuncio_id):
    """
    GET /inmueble/anuncio/<anuncio_id>/estado/
    Devuelve el estado del anuncio (por ID de anuncio).
    """
    anuncio = get_object_or_404(AnuncioModel.objects.select_related('inmueble'), id=anuncio_id)

    return Response({
        "status": 1,
        "error": 0,
        "message": "ESTADO DE ANUNCIO",
        "values": {
            "tiene_anuncio": True,
            "anuncio": {
                "id": anuncio.id,
                "inmueble": anuncio.inmueble_id,
                "estado": anuncio.estado,
                "is_active": anuncio.is_active,
                "fecha_publicacion": anuncio.fecha_publicacion,
            }
        }
    })


@api_view(['GET'])
@requiere_permiso("Anuncio", "leer")
def estado_anuncio_por_id_inmueble(request, inmueble_id):
    """
    GET /inmueble/<inmueble_id>/anuncio/estado/
    Devuelve el estado del anuncio (por ID de inmueble).
    """
    try:
        inmueble = get_object_or_404(InmuebleModel, id=inmueble_id)
        anuncio = AnuncioModel.objects.filter(inmueble=inmueble).first()

        if anuncio:
            return Response({
                "status": 1,
                "error": 0,
                "message": "ESTADO DE ANUNCIO",
                "values": {
                    "tiene_anuncio": True,
                    "anuncio": {
                        "id": anuncio.id,
                        "inmueble": anuncio.inmueble_id,
                        "estado": anuncio.estado,
                        "is_active": anuncio.is_active,
                        "fecha_publicacion": anuncio.fecha_publicacion,
                    }
                }
            })
        else:
            return Response({
                "status": 1,
                "error": 0,
                "message": "INMUEBLE SIN ANUNCIO",
                "values": {
                    "tiene_anuncio": False
                }
            })

    except InmuebleModel.DoesNotExist:
        return Response({
            "status": 0,
            "error": 1,
            "message": "Inmueble no encontrado"
        }, status=404)
    except Exception as e:
        return Response({
            "status": 0,
            "error": 1,
            "message": f"Error al obtener el estado del anuncio: {str(e)}"
        }, status=500)



@api_view(['GET'])
@requiere_permiso("Anuncio", "leer")  # O el permiso que uses
def obtener_anuncio_por_inmueble(request, inmueble_id):
    """
    Obtiene el anuncio asociado a un inmueble específico.
    GET /inmueble/{inmueble_id}/anuncio/
    """
    try:
        # Verificar que el inmueble existe y pertenece al usuario
        inmueble = get_object_or_404(InmuebleModel, id=inmueble_id)
    
        # Buscar el anuncio asociado al inmueble
        anuncio = AnuncioModel.objects.filter(inmueble=inmueble).first()
        
        if anuncio:
            return Response({
                "status": 1,
                "error": 0,
                "message": "Anuncio encontrado",
                "values": {
                    "id": anuncio.id,
                    "inmueble": anuncio.inmueble_id,
                    "estado": anuncio.estado,
                    "is_active": anuncio.is_active,
                    "fecha_publicacion": anuncio.fecha_publicacion
                }
            })
        else:
            return Response({
                "status": 0,
                "error": 1,
                "message": "No se encontró anuncio para este inmueble",
                "values": None
            })
            
    except InmuebleModel.DoesNotExist:
        return Response({
            "status": 0,
            "error": 1,
            "message": "Inmueble no encontrado",
            "values": None
        })
    except Exception as e:
        return Response({
            "status": 0,
            "error": 1,
            "message": f"Error del servidor: {str(e)}",
            "values": None
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

@api_view(['POST'])
@requiere_permiso("Anuncio", "crear")
def admin_inmuebles_sin_anuncio_tipo_operacion(request):
    """
    Inmuebles aprobados que NO tienen anuncio activo
    Perfecto para crear nuevos anuncios
    """
    inmuebles = InmuebleModel.objects.filter(
        estado="aprobado",
        tipo_operacion=request.data.get('tipo_operacion'),
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

from .nlp_utils import parse_natural_query 
from rest_framework.views import APIView 

class BusquedaNaturalView(APIView):
    # Ajusta los permisos si es una API pública o solo para agentes
    # permission_classes = [IsAuthenticated] 
    
    def get(self, request):
        query_text = request.query_params.get('q', '').strip()
        
        # 1. Lógica por defecto si no hay búsqueda
        if not query_text:
            qs = AnuncioModel.objects.filter(is_active=True, estado='disponible').select_related('inmueble')
            serializer = AnuncioSerializer(qs[:20], many=True)
            return Response({
                "status": 1, 
                "error": 0, 
                "message": "LISTADO DE ANUNCIOS POR DEFECTO",
                "values": {"anuncios": serializer.data, "count": qs.count()}
            }, status=200)

        # 2. Traducir la consulta natural a filtros estructurados (Llama a tu función que ya funciona)
        filters = parse_natural_query(query_text)
        
        # 3. Comprobación de filtros válidos (Si la IA no devolvió nada)
        # Verifica si hay algún valor útil (no vacío, no cero, y no solo la lista de características vacía)
        if not filters or not any(v for k, v in filters.items() if v and k not in ['caracteristicas_clave', 'precio_minimo', 'precio_maximo', 'dormitorios_min'] or (isinstance(v, (int, float)) and v > 0) or (k == 'caracteristicas_clave' and v)):
             return Response({"count": 0, "anuncios": [], "detail": "No se pudieron extraer filtros válidos de la consulta."}, status=422)

        # 4. Construir la consulta Q (Query Object) para el modelo Inmueble
        q_objects = Q()
        
        # --- FILTROS ---
        
        # Tipo de Propiedad (tipo_inmueble__nombre)
        if filters.get('tipo_propiedad'):
            q_objects &= Q(inmueble__tipo_inmueble__nombre__iexact=filters['tipo_propiedad'])
            
        # Tipo de Operación
        if filters.get('tipo_operacion'):
             q_objects &= Q(inmueble__tipo_operacion__iexact=filters['tipo_operacion'])
        
        # Ubicación (ciudad o zona) - (OR lógico)
        ubicacion = filters.get('ciudad') or filters.get('zona')
        if ubicacion:
            q_objects &= (Q(inmueble__ciudad__icontains=ubicacion) | Q(inmueble__zona__icontains=ubicacion))

        # Precio Mínimo / Máximo / Dormitorios Mínimo
        if filters.get('precio_minimo') and filters['precio_minimo'] > 0:
            q_objects &= Q(inmueble__precio__gte=filters['precio_minimo'])
        if filters.get('precio_maximo') and filters['precio_maximo'] > 0:
            q_objects &= Q(inmueble__precio__lte=filters['precio_maximo'])
        if filters.get('dormitorios_min') and filters['dormitorios_min'] > 0:
            q_objects &= Q(inmueble__dormitorios__gte=filters['dormitorios_min'])

        # Filtro de Características Clave (en la descripción)
        caracteristicas = filters.get('caracteristicas_clave')
        if caracteristicas and isinstance(caracteristicas, list):
            desc_q = Q()
            for key in caracteristicas:
                desc_q |= Q(inmueble__descripcion__icontains=key.strip())
            if desc_q:
                q_objects &= desc_q
        
        # 5. Ejecutar la consulta en la base de datos
        resultados_anuncios = AnuncioModel.objects.filter(
            q_objects, 
            is_active=True, 
            estado='disponible' 
        ).select_related('inmueble').prefetch_related('inmueble__fotos')
        
        # 6. Serializar y devolver los resultados
        serializer = AnuncioSerializer(resultados_anuncios, many=True)
        
        return Response({
            "status": 1, 
            "error": 0, 
            "message": "LISTADO DE ANUNCIOS FILTRADO POR NLP",
            "values": {
                 "anuncios": serializer.data,
                 "count": resultados_anuncios.count(),
                 "filtros_nlp": filters
            }
        }, status=200)
        
        
@api_view(['GET'])
def listar_pines_mapa(request):
    # 1. Filtramos inmuebles aprobados y activos
    inmuebles = InmuebleModel.objects.filter(estado="aprobado", is_active=True)
    
    # 2. Excluir los que no tienen coordenadas (para no romper el mapa)
    inmuebles = inmuebles.exclude(latitud__isnull=True).exclude(longitud__isnull=True)

    # 3. OPTIMIZACIÓN CLAVE: Traer las fotos de antemano ("Pre-cargar")
    # Esto evita que el servidor haga una consulta extra por cada casa en el mapa
    inmuebles = inmuebles.prefetch_related('fotos')
    
    # 4. Serializar
    serializer = InmuebleMapaSerializer(inmuebles, many=True)
    
    return Response({
        "status": 1,
        "values": serializer.data
    })