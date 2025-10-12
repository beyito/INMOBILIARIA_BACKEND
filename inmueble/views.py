# inmueble/views.py
from django.shortcuts import render
from rest_framework.decorators import api_view
from rest_framework.response import Response
from rest_framework import status
from django.shortcuts import get_object_or_404
from .models import InmuebleModel, CambioInmuebleModel, TipoInmuebleModel, AnuncioModel, FotoModel
from .serializers import InmuebleSerializer, CambioInmuebleSerializer, TipoInmuebleSerializer
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

# INMUEBLES
#PARA EL AGENTE Y ADMIN, SI LO HACE EL AGENTE NO ENVIA EL ESTADO, PORQUE SERÁ PENDIENTE

# @api_view(['POST'])
# @requiere_permiso("Inmueble", "crear")
# def agente_registrar_inmueble(request):
#     data = request.data.copy()
#     data['agente'] = request.user.id

#     serializer = InmuebleSerializer(data=data)
#     if serializer.is_valid():
#         inmueble = serializer.save()

#         # 👇 CAMBIO MÍNIMO: crear fotos desde URLs si vinieron
#         urls = request.data.get('fotos_urls', [])
#         if isinstance(urls, list) and urls:
#             FotoModel.objects.bulk_create(
#                 [FotoModel(inmueble=inmueble, url=u.strip()) for u in urls if isinstance(u, str) and u.strip()]
#             )

#         # re-serializa para incluir fotos recién creadas
#         out = InmuebleSerializer(inmueble)
#         return Response({
#             "status": 1,
#             "error": 0,
#             "message": "INMUEBLE REGISTRADO CORRECTAMENTE ESPERANDO APROBACION DEL ADMINISTRADOR",
#             "values": {"inmueble": out.data}
#         })

#     return Response({
#         "status": 0,
#         "error": 1,
#         "message": "ERROR AL REGISTRAR EL INMUEBLE",
#         "values": serializer.errors
#     })
# inmueble/views.py
from usuario.models import Usuario

@api_view(['POST'])
@requiere_permiso("Inmueble", "crear")
def agente_registrar_inmueble(request):
    data = request.data.copy()

    # ¿El que crea es admin?
    grupo_nombre = getattr(getattr(request.user, 'grupo', None), 'nombre', '') or ''
    es_admin = grupo_nombre.lower() == 'administrador'

    if es_admin:
        # El admin DEBE enviar el id del agente dueño del inmueble
        agente_id = data.get('agente')
        if not agente_id:
            return Response({
                "status": 0, "error": 1,
                "message": "Como administrador debes enviar el campo 'agente' (id del agente dueño).",
                "values": None
            }, status=status.HTTP_400_BAD_REQUEST)
        # valida que exista el usuario y opcionalmente que sea del grupo 'agente'
        try:
            agente = Usuario.objects.get(id=agente_id)
            if getattr(getattr(agente, 'grupo', None), 'nombre', '').lower() != 'agente':
                return Response({
                    "status": 0, "error": 1,
                    "message": "El usuario indicado en 'agente' no pertenece al grupo Agente."
                }, status=status.HTTP_400_BAD_REQUEST)
        except Usuario.DoesNotExist:
            return Response({
                "status": 0, "error": 1,
                "message": "El 'agente' indicado no existe."
            }, status=status.HTTP_400_BAD_REQUEST)

        data['agente'] = agente.id
    else:
        # Si NO es admin, el agente autenticado es el dueño
        data['agente'] = request.user.id

    serializer = InmuebleSerializer(data=data)
    if serializer.is_valid():
        inmueble = serializer.save()

        # Crear fotos desde URLs si vinieron
        urls = request.data.get('fotos_urls', [])
        if isinstance(urls, list) and urls:
            FotoModel.objects.bulk_create(
                [FotoModel(inmueble=inmueble, url=u.strip())
                 for u in urls if isinstance(u, str) and u.strip()]
            )

        out = InmuebleSerializer(inmueble)
        return Response({
            "status": 1, "error": 0,
            "message": "INMUEBLE REGISTRADO CORRECTAMENTE ESPERANDO APROBACION DEL ADMINISTRADOR",
            "values": {"inmueble": out.data}
        })

    return Response({
        "status": 0, "error": 1,
        "message": "ERROR AL REGISTRAR EL INMUEBLE",
        "values": serializer.errors
    }, status=status.HTTP_400_BAD_REQUEST)

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

# SI EL INMUEBLE ES APROBADO, EL AGENTE PUBLICARÁ EL ANUNCIO ( ANTES HARÁ EL CONTRATO CON EL CLIENTE)

# @api_view(['POST'])
# @requiere_permiso("Anuncio", "crear")
# def publicar_anuncio(request,inmueble_id):
#     data = request.data.copy()
#     data['inmueble'] = inmueble_id # asignamos el agente desde el token
#     # data['estado'] = 'pendiente' # estado inicial siempre pendiente
#     serializer = InmuebleSerializer(data=data)
#     if serializer.is_valid():
#         serializer.save()
#         return Response({
#             "status": 1,
#             "error": 0,
#             "message": "INMUEBLE REGISTRADO CORRECTAMENTE ESPERANDO APROBACION DEL ADMINISTRADOR",
#             "values": {"inmueble": serializer.data}
#         })
    
#     return Response({
#         "status": 0,
#         "error": 1,
#         "message": "ERROR AL REGISTRAR EL INMUEBLE",
#         "values": serializer.errors
#     })


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

# @api_view(['GET'])
# def listar_inmuebles(request):
#     """
#     Filtros soportados (query params):
#     - tipo: venta | alquiler | anticretico
#     - ciudad: string
#     - zona: string
#     - min_precio, max_precio: números
#     - q: término de búsqueda (titulo, descripcion, dirección)
#     - page, page_size: paginación simple
#     """
#     qs = (InmuebleModel.objects
#           .select_related()  # si hay FKs útiles
#           .prefetch_related('fotos')  # related_name='fotos'
#           .all())

#     # Filtros
#     tipo = request.GET.get('tipo')
#     if tipo:
#         qs = qs.filter(tipo_operacion__iexact=tipo)

#     ciudad = request.GET.get('ciudad')
#     if ciudad:
#         qs = qs.filter(ciudad__icontains=ciudad)

#     zona = request.GET.get('zona')
#     if zona:
#         qs = qs.filter(zona__icontains=zona)

#     try:
#         min_precio = request.GET.get('min_precio')
#         if min_precio is not None:
#             qs = qs.filter(precio__gte=float(min_precio))
#         max_precio = request.GET.get('max_precio')
#         if max_precio is not None:
#             qs = qs.filter(precio__lte=float(max_precio))
#     except ValueError:
#         return _err({"precio": "min_precio/max_precio inválidos"})

#     q = request.GET.get('q')
#     if q:
#         qs = qs.filter(
#             Q(titulo__icontains=q) |
#             Q(descripcion__icontains=q) |
#             Q(direccion__icontains=q)
#         )

#     # Orden por defecto (más recientes primero si tienes fecha_creacion)
#     if hasattr(InmuebleModel, 'fecha_creacion'):
#         qs = qs.order_by('-fecha_creacion')
#     else:
#         qs = qs.order_by('-id')

#     # Paginación simple
#     try:
#         page = int(request.GET.get('page', 1))
#         page_size = int(request.GET.get('page_size', 12))
#     except ValueError:
#         return _err({"paginacion": "page/page_size inválidos"})

#     total = qs.count()
#     start = (page - 1) * page_size
#     end = start + page_size
#     page_qs = qs[start:end]

#     data = InmuebleSerializer(page_qs, many=True, context={'request': request}).data
#     return _ok({
#         "inmuebles": data,
#         "total": total,
#         "page": page,
#         "page_size": page_size
#     }, message="LISTA DE INMUEBLES")
    


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


# @api_view(['GET'])
# @requiere_permiso("Inmueble", "leer")
# def resumen_mis_inmuebles(request):
#     """
#     Devuelve contadores para armar las pestañas: pendientes, aprobados, rechazados, publicados, todos.
#     """
#     base = InmuebleModel.objects.filter(agente=request.user, is_active=True)
#     agg = base.aggregate(
#         pendientes=Count('id', filter=Q(estado='pendiente')),
#         aprobados=Count('id', filter=Q(estado='aprobado')),
#         rechazados=Count('id', filter=Q(estado='rechazado')),
#         publicados=Count('id', filter=Q(estado='aprobado', anuncio__is_active=True, anuncio__estado='disponible')),
#         todos=Count('id'),
#     )
#     return Response({
#         "status": 1, "error": 0, "message": "RESUMEN MIS INMUEBLES", "values": agg
#     })
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
