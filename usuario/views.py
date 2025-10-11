# usuario/views.py
from django.shortcuts import get_object_or_404
from rest_framework.decorators import api_view,authentication_classes,permission_classes 
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.authentication import TokenAuthentication
from rest_framework.response import Response
from rest_framework.authtoken.models import Token
from rest_framework import status
from .serializers import UsuarioSerializer, PrivilegioSerializer, GrupoSerializer, ComponenteSerializer, PasswordResetRequestSerializer, PasswordResetVerifyCodeSerializer, SetNewPasswordSerializer, SolicitudAgenteSerializer
from django.core.mail import send_mail
from django.contrib.auth.models import User
from .models import PasswordResetCode, Usuario, PasswordResetCode, Grupo, SolicitudAgente, Privilegio, Componente
from rest_framework.views import APIView
from django.conf import settings
from reportlab.lib.pagesizes import LETTER
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, HRFlowable
from reportlab.lib.enums import TA_JUSTIFY, TA_CENTER, TA_LEFT, TA_RIGHT  # Agregar TA_LEFT y TA_RIGHT aquí
from reportlab.lib import colors
from django.http import HttpResponse

from inmobiliaria.permissions import requiere_actualizacion,requiere_creacion, requiere_eliminacion, requiere_lectura, requiere_permiso
from utils.encrypted_logger import registrar_accion, leer_logs
import os
import io
# Create your views here.

@api_view(['POST']) 
def login(request):
    try:
        usuario = get_object_or_404(Usuario, username=request.data['username'])
        print(usuario)
    except:
        return Response({
            "status": 0,
            "error": 1,
            "message": "USUARIO NO ENCONTRADO",
            "values": None
        })
    
    if not usuario.check_password(request.data['password']):
        return Response({
            "status": 0,
            "error": 1,
            "message": "CONTRASEÑA INCORRECTA",
            "values": None
        })

    token, created = Token.objects.get_or_create(user=usuario)
    serializer = UsuarioSerializer(instance=usuario)
    registrar_accion(
        usuario=usuario,
        accion="Inició sesión en el sistema",
        ip=request.META.get("REMOTE_ADDR")
    )
    return Response({
        "status": 1,
        "error": 0,
        "message": "LOGIN EXITOSO",
        "values": {"token": token.key, "usuario": serializer.data}
    },)


@api_view(["GET", "POST"])  
@permission_classes([IsAuthenticated])
def profile(request):
    user = request.user
    data = UsuarioSerializer(user).data
    return Response(data, status=status.HTTP_200_OK)


# --------------------------
# USUARIO
# --------------------------

@api_view(['POST'])
# @requiere_permiso("Usuario","crear")  # Este decorador ahora incluye el permission class
def register(request):
    grupo_id = request.data.get('grupo_id')
    print('DATOS ENTRANTES',request.data)
    # Si es agente (grupo_id=2), crear solicitud
    if str(grupo_id) == '2':
        print(request.data)
        serializer = SolicitudAgenteSerializer(data=request.data)
        print('serializer', serializer)
        if serializer.is_valid():
            solicitud = serializer.save()
            return Response({
                "status": 1,
                "error": 0,
                "message": "SOLICITUD DE AGENTE CREADA, PENDIENTE DE APROBACIÓN",
                "values": serializer.data
            })
        print(serializer.errors)
        return Response({
            "status": 0,
            "error": 1,
            "message": "ERROR EN LA SOLICITUD",
            "values": serializer.errors
        })

    # Si es cliente u otro grupo, registrar normalmente
    serializer = UsuarioSerializer(data=request.data)
    print('serializerUsuario', serializer)

    if serializer.is_valid():
        # Asignar grupo_id = 3 antes de guardar
        usuario = serializer.save(grupo_id=3)

        token, created = Token.objects.get_or_create(user=usuario)

        usuario_serializer = UsuarioSerializer(instance=usuario)
        return Response({
            "status": 1,
            "error": 0,
            "message": "REGISTRO EXITOSO",
            "values": {
                "token": token.key,
                "usuario": usuario_serializer.data
            }
        })
    else:
        # Muy recomendable devolver errores si el serializer no es válido
        return Response({
            "status": 0,
            "error": 1,
            "message": "ERROR EN LA SOLICITUD",
            "values": serializer.errors
        }, status=400)

    return Response({
        "status": 0,
        "error": 1,
        "message": "ERROR EN EL REGISTRO",
        "values": serializer.errors
    })

@api_view(['GET'])
@requiere_permiso("Usuario","leer") 
def listar_usuarios(request):
    usuarios = Usuario.objects.all()
    serializer = UsuarioSerializer(usuarios, many=True)
    return Response({
        "status": 1,
        "error": 0,
        "message": "LISTADO DE USUARIOS",
        "values": {"usuarios": serializer.data}
    })



@api_view(['PATCH'])
@requiere_permiso("Usuario","actualizar") 
def editar_usuario(request, usuario_id):
    usuario = get_object_or_404(Usuario, id=usuario_id)

    grupo_id = request.data.get('grupo_id')
    if grupo_id:
        grupo = get_object_or_404(Grupo, id=grupo_id)
        usuario.grupo = grupo

    serializer = UsuarioSerializer(usuario, data=request.data, partial=True)
    if serializer.is_valid():
        usuario = serializer.save()
        # Actualizar password si viene
        if 'password' in request.data:
            usuario.set_password(request.data['password'])
            usuario.save()

        return Response({
            "status": 1,
            "error": 0,
            "message": "USUARIO ACTUALIZADO EXITOSAMENTE",
            "values": {"usuario": UsuarioSerializer(usuario).data}
        })
    else:
        return Response({
            "status": 0,
            "error": 1,
            "message": "ERROR AL EDITAR USUARIO",
            "values": serializer.errors
        })


@api_view(['DELETE'])
@requiere_permiso("Usuario","eliminar") 
def eliminar_usuario(request, usuario_id):
    usuario = get_object_or_404(Usuario, id=usuario_id)
    usuario.is_active = False
    usuario.save()
    return Response({
        "status": 1,
        "error": 0,
        "message": "USUARIO DESACTIVADO EXITOSAMENTE",
        "values": None
    })

@api_view(['PATCH'])
@requiere_permiso("Usuario","activar") 
def activar_usuario(request, usuario_id):
    usuario = get_object_or_404(Usuario, id=usuario_id)
    usuario.is_active = True
    usuario.save()
    return Response({
        "status": 1,
        "error": 0,
        "message": "USUARIO ACTIVADO EXITOSAMENTE",
        "values": None
    })


# --------------------------
# GRUPO
# --------------------------

@api_view(['POST'])
@requiere_permiso("Grupo","crear") 
def crear_grupo(request):
    nombre = request.data.get('nombre')
    descripcion = request.data.get('descripcion', '')

    if not nombre:
        return Response({
            "status": 0,
            "error": 1,
            "message": "EL NOMBRE DEL GRUPO ES REQUERIDO",
            "values": None
        })

    grupo, created = Grupo.objects.get_or_create(nombre=nombre, defaults={"descripcion": descripcion})
    if not created:
        return Response({
            "status": 0,
            "error": 1,
            "message": "EL GRUPO YA EXISTE",
            "values": None
        })

    serializer = GrupoSerializer(grupo)
    return Response({
        "status": 1,
        "error": 0,
        "message": "GRUPO CREADO EXITOSAMENTE",
        "values": {"grupo": serializer.data}
    })

@api_view(['PATCH'])
@requiere_permiso("Grupo","actualizar") 
def editar_grupo(request, grupo_id):
    grupo = get_object_or_404(Grupo, id=grupo_id)
    nombre = request.data.get('nombre', grupo.nombre)
    descripcion = request.data.get('descripcion', grupo.descripcion)

    grupo.nombre = nombre
    grupo.descripcion = descripcion
    grupo.save()

    serializer = GrupoSerializer(grupo)
    return Response({
        "status": 1,
        "error": 0,
        "message": "GRUPO ACTUALIZADO EXITOSAMENTE",
        "values": {"grupo": serializer.data}
    })

@api_view(['GET'])
@requiere_permiso("Grupo","leer") 
def listar_grupos(request):
    grupos = Grupo.objects.all()
    serializer = GrupoSerializer(grupos, many=True)
    return Response({
        "status": 1,
        "error": 0,
        "message": "LISTADO DE GRUPOS",
        "values": {"grupos": serializer.data}
    })

@api_view(['DELETE'])
@requiere_permiso("Grupo","eliminar") 
def eliminar_grupo(request, grupo_id):
    grupo = get_object_or_404(Grupo, id=grupo_id)
    grupo.is_active = False
    grupo.save()
    return Response({
        "status": 1,
        "error": 0,
        "message": "GRUPO DESACTIVADO EXITOSAMENTE",
        "values": None
    })

@api_view(['PATCH'])
@requiere_permiso("Grupo","activar") 
def activar_grupo(request, grupo_id):
    grupo = get_object_or_404(Grupo, id=grupo_id)
    grupo.is_active = True
    grupo.save()
    return Response({
        "status": 1,
        "error": 0,
        "message": "GRUPO ACTIVADO EXITOSAMENTE",
        "values": None
    })

# --------------------------
# COMPONENTE
# --------------------------

@api_view(['GET'])
@requiere_permiso("Componente","leer") 
def listar_componentes(request):
    componentes = Componente.objects.filter(is_active=True)
    serializer = ComponenteSerializer(componentes, many=True)
    return Response({
        "status": 1,
        "error": 0,
        "message": "LISTADO DE COMPONENTES",
        "values": {"componentes": serializer.data}
    })


@api_view(['POST'])
@requiere_permiso("Componente","crear") 
def crear_componente(request):
    serializer = ComponenteSerializer(data=request.data)
    if serializer.is_valid():
        componente = serializer.save()
        return Response({
            "status": 1,
            "error": 0,
            "message": "COMPONENTE CREADO EXITOSAMENTE",
            "values": {"componente": ComponenteSerializer(componente).data}
        })
    else:
        return Response({
            "status": 0,
            "error": 1,
            "message": "ERROR AL CREAR COMPONENTE",
            "values": serializer.errors
        })


@api_view(['PATCH'])
@requiere_permiso("Componente","actualizar") 
def editar_componente(request, componente_id):
    componente = get_object_or_404(Componente, id=componente_id)
    serializer = ComponenteSerializer(componente, data=request.data, partial=True)
    if serializer.is_valid():
        componente = serializer.save()
        return Response({
            "status": 1,
            "error": 0,
            "message": "COMPONENTE ACTUALIZADO EXITOSAMENTE",
            "values": {"componente": ComponenteSerializer(componente).data}
        })
    else:
        return Response({
            "status": 0,
            "error": 1,
            "message": "ERROR AL EDITAR COMPONENTE",
            "values": serializer.errors
        })


@api_view(['DELETE'])
@requiere_permiso("Componente","eliminar") 
def eliminar_componente(request, componente_id):
    componente = get_object_or_404(Componente, id=componente_id)
    componente.is_active = False
    componente.save()
    return Response({
        "status": 1,
        "error": 0,
        "message": "COMPONENTE DESACTIVADO EXITOSAMENTE",
        "values": None
    })


@api_view(['PATCH'])
@requiere_permiso("Componente","activar") 
def activar_componente(request, componente_id):
    componente = get_object_or_404(Componente, id=componente_id)
    componente.is_active = True
    componente.save()
    return Response({
        "status": 1,
        "error": 0,
        "message": "COMPONENTE ACTIVADO EXITOSAMENTE",
        "values": None
    })


# --------------------------
# PRIVILEGIO
# --------------------------


@api_view(['POST'])
@requiere_permiso("Privilegio","crear") 
def asignar_privilegio(request):
    grupo_id = request.data.get('grupo_id')
    componente_id = request.data.get('componente_id')
    permisos = {
        "puede_leer": request.data.get("puede_leer", False),
        "puede_crear": request.data.get("puede_crear", False),
        "puede_actualizar": request.data.get("puede_actualizar", False),
        "puede_eliminar": request.data.get("puede_eliminar", False),
    }

    if not grupo_id or not componente_id:
        return Response({
            "status": 0,
            "error": 1,
            "message": "GRUPO_ID Y COMPONENTE_ID SON REQUERIDOS",
            "values": None
        })

    grupo = get_object_or_404(Grupo, id=grupo_id)
    componente = get_object_or_404(Componente, id=componente_id)

    privilegio, created = Privilegio.objects.update_or_create(
        grupo=grupo,
        componente=componente,
        defaults=permisos
    )

    serializer = PrivilegioSerializer(privilegio)
    return Response({
        "status": 1,
        "error": 0,
        "message": "PRIVILEGIO ASIGNADO EXITOSAMENTE",
        "values": {"privilegio": serializer.data}
    })


@api_view(['PATCH'])
@requiere_permiso("Privilegio","actualizar") 
def editar_privilegio(request, privilegio_id):
    privilegio = get_object_or_404(Privilegio, id=privilegio_id)
    privilegio.puede_leer = request.data.get("puede_leer", privilegio.puede_leer)
    privilegio.puede_crear = request.data.get("puede_crear", privilegio.puede_crear)
    privilegio.puede_actualizar = request.data.get("puede_actualizar", privilegio.puede_actualizar)
    privilegio.puede_eliminar = request.data.get("puede_eliminar", privilegio.puede_eliminar)
    privilegio.puede_activar = request.data.get("puede_activar", privilegio.puede_activar)

    privilegio.save()

    serializer = PrivilegioSerializer(privilegio)
    return Response({
        "status": 1,
        "error": 0,
        "message": "PRIVILEGIO ACTUALIZADO EXITOSAMENTE",
        "values": {"privilegio": serializer.data}
    })

@api_view(['GET'])
@requiere_permiso("Privilegio","leer") 
def listar_privilegios(request):
    privilegios = Privilegio.objects.all()
    serializer = PrivilegioSerializer(privilegios, many=True)
    return Response({
        "status": 1,
        "error": 0,
        "message": "LISTADO DE PRIVILEGIOS",
        "values": {"privilegios": serializer.data}
    })

@api_view(['DELETE'])
@requiere_permiso("Privilegio","eliminar") 
def eliminar_privilegio(request, privilegio_id):
    privilegio = get_object_or_404(Privilegio, id=privilegio_id)
    privilegio.delete()
    return Response({
        "status": 1,
        "error": 0,
        "message": "PRIVILEGIO ELIMINADO EXITOSAMENTE",
        "values": {"privilegio_id": privilegio_id}
    })


# --------------------------
# ASIGNAR GRUPO A USUARIO
# --------------------------
@api_view(['POST'])
def asignar_grupo_usuario(request):
    username = request.data.get('username')
    grupo_id = request.data.get('grupo_id')

    if not username or not grupo_id:
        return Response({
            "status": 0,
            "error": 1,
            "message": "USERNAME y GRUPO_ID son requeridos",
            "values": None
        })

    try:
        usuario = get_object_or_404(Usuario, username=username)
        grupo = get_object_or_404(Grupo, id=grupo_id)
    except:
        return Response({
            "status": 0,
            "error": 1,
            "message": "USUARIO O GRUPO NO ENCONTRADO",
            "values": None
        })

    usuario.grupo = grupo
    usuario.save()

    serializer = UsuarioSerializer(usuario)
    return Response({
        "status": 1,
        "error": 0,
        "message": f"Grupo '{grupo.nombre}' asignado correctamente al usuario '{usuario.username}'",
        "values": {"usuario": serializer.data}
    })

# --------------------------
# ASIGNAR PRIVILEGIOS A GRUPO
# --------------------------
@api_view(['POST'])
def asignar_privilegios_grupo(request):
    grupo_id = request.data.get('grupo_id')
    privilegios = request.data.get('privilegios')  # lista de dicts: [{"componente_id": 1, "puede_leer": True,...}]

    if not grupo_id or not privilegios:
        return Response({
            "status": 0,
            "error": 1,
            "message": "GRUPO_ID y PRIVILEGIOS son requeridos",
            "values": None
        })

    try:
        grupo = get_object_or_404(Grupo, id=grupo_id)
    except:
        return Response({
            "status": 0,
            "error": 1,
            "message": "GRUPO NO ENCONTRADO",
            "values": None
        })

    resultados = []
    for priv in privilegios:
        try:
            componente_id = priv.get('componente_id')
            componente = get_object_or_404(Componente, id=componente_id)

            obj, created = Privilegio.objects.update_or_create(
                grupo=grupo,
                componente=componente,
                defaults={
                    "puede_leer": priv.get("puede_leer", False),
                    "puede_crear": priv.get("puede_crear", False),
                    "puede_actualizar": priv.get("puede_actualizar", False),
                    "puede_eliminar": priv.get("puede_eliminar", False),
                }
            )
            resultados.append(PrivilegioSerializer(obj).data)
        except:
            continue  # ignorar componentes inválidos

    return Response({
        "status": 1,
        "error": 0,
        "message": f"Privilegios asignados al grupo '{grupo.nombre}'",
        "values": {"privilegios": resultados}
    })



# @api_view(['GET'])
# @authentication_classes([TokenAuthentication])
# @permission_classes([IsAuthenticated])
# def mostrarUsuarios(request):
#     if not request.user.es_admin():    # ← ahora solo Admin lista
#         return Response({
#             "status": 2,
#             "error": 1,
#             "message": "NO TIENES PERMISO PARA VER LOS USUARIOS",
#             "values": None
#         }, status=status.HTTP_403_FORBIDDEN)
    
#     usuarios = Usuario.objects.all()
#     serializer = UsuarioSerializer(usuarios, many=True)
#     return Response({
#         "status": 1,
#         "error": 0,
#         "message": "USUARIOS OBTENIDOS",
#         "values": serializer.data
#     })


class ContratoAgenteView(APIView):
    def post(self, request):
        data = request.data
        print("DATA", data)
        # Ruta del archivo de plantilla
        plantilla_path = os.path.join(settings.BASE_DIR, "usuario/contratoPDF/contrato_agente.txt")
        with open(plantilla_path, "r", encoding="utf-8") as f:
            contrato_text = f.read()

        # Reemplazar variables
        contrato_text = contrato_text.format(
            ciudad=data.get("ciudad", "________________"),
            fecha=data.get("fecha", "____/____/______"),
            inmobiliaria_nombre=data.get("inmobiliaria_nombre", "________________"),
            inmobiliaria_direccion=data.get("inmobiliaria_direccion", "________________"),
            inmobiliaria_representante=data.get("inmobiliaria_representante", "________________"),
            agente_nombre=data.get("agente_nombre", "________________"),
            agente_direccion=data.get("agente_direccion", "________________"),
            agente_ci=data.get("agente_ci", "________________"),
            agente_licencia=data.get("agente_licencia", "________________"),
            comision=data.get("comision", "____"),
            duracion=data.get("duracion", "____"),
        )

        # Crear buffer en memoria
        buffer = io.BytesIO()
        doc = SimpleDocTemplate(
            buffer,
            pagesize=LETTER,
            rightMargin=50,
            leftMargin=50,
            topMargin=50,
            bottomMargin=50
        )

        # Estilos
        styles = getSampleStyleSheet()
        titulo_style = ParagraphStyle(
            'Titulo',
            fontSize=18,
            leading=22,
            alignment=TA_CENTER,
            spaceAfter=20,
            textColor=colors.darkblue,
        )
        clausula_style = ParagraphStyle(
            'Clausula',
            fontSize=12,
            leading=18,
            alignment=TA_JUSTIFY,
        )
        firma_style = ParagraphStyle(
            'Firma',
            fontSize=12,
            leading=6,
            alignment=TA_CENTER,
        )

        story = []

        # Título
        story.append(Paragraph("CONTRATO DE VINCULACIÓN INMOBILIARIA", titulo_style))
        story.append(Spacer(1, 10))

        # Separar por párrafos usando doble salto de línea
        lineas = contrato_text.strip().split("\n\n")

        # Última línea que dice "Las partes aceptan..."
        aceptacion_texto = lineas[-1]
        clausulas = lineas[:-1]

        # Agregar cláusulas con separador
        for i, p in enumerate(clausulas):
            story.append(Paragraph(p.strip(), clausula_style))
            if i != len(clausulas) - 1:
                story.append(Spacer(1, 6))
                story.append(HRFlowable(width="100%", thickness=0.5, color=colors.grey))
                story.append(Spacer(1, 6))

        # Frase de aceptación
        story.append(Spacer(1, 6))
        story.append(Paragraph(aceptacion_texto.strip(), clausula_style))
        # Firmas compactas
        firmas_texto = f"""__________________________  <br/><br/><br/>
        INMOBILIARIA ({data.get('inmobiliaria_nombre','________')})<br/><br/>
        __________________________  <br/><br/><br/>
        AGENTE INMOBILIARIO ({data.get('agente_nombre','________')})
        """
        story.append(Paragraph(firmas_texto, firma_style))

        # Generar PDF
        doc.build(story)
        buffer.seek(0)

        # Devolver PDF
        response = HttpResponse(buffer, content_type='application/pdf')
        response['Content-Disposition'] = f'attachment; filename="contrato_{data.get("agente_nombre","agente")}.pdf"'
        return response


class PasswordResetRequestView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = PasswordResetRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        correo = serializer.validated_data['correo']

        try:
            user = Usuario.objects.get(correo=correo)
        except Usuario.DoesNotExist:
            return Response({
                "status": 2,
                "error": 1,
                "message": "USUARIO NO ENCONTRADO",
                "values": None
            }, status=status.HTTP_404_NOT_FOUND)

        # Crear código de recuperación
        reset_code = PasswordResetCode.objects.create(user=user)

        # Enviar correo con el código
        message = f"Hola {user.username}, tu código de recuperación es: {reset_code.code}\nVálido por 15 minutos."
        send_mail(
            subject="Código de recuperación de contraseña",
            message=message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[user.correo],
        )

        return Response({
            "status": 1,
            "error": 0,
            "message": "CÓDIGO DE RECUPERACIÓN ENVIADO",
            "values": {"correo": user.correo}
        })


class PasswordResetVerifyCodeView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = PasswordResetVerifyCodeSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        correo = serializer.validated_data['correo']
        code = serializer.validated_data['code']

        try:
            user = Usuario.objects.get(correo=correo)
            reset_code = PasswordResetCode.objects.filter(user=user, code=code, is_used=False).last()
            if not reset_code or not reset_code.is_valid():
                return Response({
                    "status": 0,
                    "error": 1,
                    "message": "CÓDIGO INVÁLIDO O EXPIRADO",
                    "values": None
                }, status=status.HTTP_400_BAD_REQUEST)

            # Marcar como verificado
            reset_code.is_verified = True
            reset_code.save()

            return Response({
                "status": 1,
                "error": 0,
                "message": "CÓDIGO VERIFICADO, YA PUEDES CAMBIAR TU CONTRASEÑA",
                "values": {"correo": user.correo, "code": reset_code.code}
            })
        except Usuario.DoesNotExist:
            return Response({
                "status": 0,
                "error": 1,
                "message": "USUARIO NO ENCONTRADO",
                "values": None
            }, status=status.HTTP_404_NOT_FOUND)


class SetNewPasswordView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = SetNewPasswordSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        correo = serializer.validated_data['correo']
        new_password = serializer.validated_data['password']

        try:
            user = Usuario.objects.get(correo=correo)
            # Buscar el último código verificado
            reset_code = PasswordResetCode.objects.filter(user=user, is_verified=True, is_used=False).last()
            if not reset_code or not reset_code.is_valid():
                return Response({
                    "status": 0,
                    "error": 1,
                    "message": "NO TIENES UN CÓDIGO VERIFICADO VÁLIDO",
                    "values": None
                }, status=status.HTTP_400_BAD_REQUEST)

            # Cambiar la contraseña
            user.set_password(new_password)
            user.save()

            # Marcar el código como usado
            reset_code.is_used = True
            reset_code.save()

            return Response({
                "status": 1,
                "error": 0,
                "message": "CONTRASEÑA CAMBIADA CON ÉXITO",
                "values": {"correo": user.correo}
            })
        except Usuario.DoesNotExist:
            return Response({
                "status": 0,
                "error": 1,
                "message": "USUARIO NO ENCONTRADO",
                "values": None
            }, status=status.HTTP_404_NOT_FOUND)



@api_view(['POST'])
def registerAgente(request):
    correo = request.data.get('correo')

    # Verificar si ya existe un usuario con rol 'Agente'
    if Usuario.objects.filter(correo=correo, idRol__nombre='Agente').exists():
        return Response({
            "status": 2,
            "error": 1,
            "message": "Usted ya es un agente registrado",
            "values": {}
        })

    # Crear o actualizar la solicitud pendiente
    solicitud, created = SolicitudAgente.objects.update_or_create(
        correo=correo,
        estado='pendiente',
        defaults=request.data
    )

    serializer = SolicitudAgenteSerializer(solicitud)

    return Response({
        "status": 1,
        "error": 0,
        "message": "SOLICITUD ENVIADA, TE ENVIAREMOS UN MENSAJE CUANDO SEA APROBADA",
        "values": {"solicitud_id": solicitud.idSolicitud, "solicitud": serializer.data}
    })


class BitacoraView(APIView):
    # permission_classes = [IsAuthenticated]  # Solo usuarios autenticados

    def post(self, request):
        """
        Listar bitácora (requiere llave del desarrollador)
        """
        llave = request.data.get("llave", None)

        if not llave:
            return Response({
                "status": 2,
                "error": 1,
                "message": "Debe proporcionar la llave del desarrollador"
            })

        try:
            registros = leer_logs(llave)
            return Response({
                "status": 1,
                "error": 0,
                "message": "Bitácora desencriptada correctamente",
                "values": registros
            })
        except Exception as e:
            return Response({
                "status": 2,
                "error": 1,
                "message": "Llave inválida o error al desencriptar"
            })
        

@api_view(['GET'])
def get_privilegios(request):
    user = request.user

    # Si el grupo del usuario es administrador
    if user.grupo.nombre.lower() == 'administrador':
        # Devuelve todos los componentes con permisos en True
        componentes = Componente.objects.all()
        privilegios_list = []
        for c in componentes:
            privilegios_list.append({
                "componente": c.nombre.lower(),
                "puede_crear": True,
                "puede_actualizar": True,
                "puede_eliminar": True,
                "puede_leer": True,
                "puede_activar": True
            })
    else:
        # Filtrar privilegios reales según el grupo del usuario
        privilegios = Privilegio.objects.filter(grupo=user.grupo.id)
        privilegios_list = []
        for p in privilegios:
            privilegios_list.append({
                "componente": p.componente.nombre.lower(),
                "puede_crear": p.puede_crear,
                "puede_actualizar": p.puede_actualizar,
                "puede_eliminar": p.puede_eliminar,
                "puede_leer": p.puede_leer,
                "puede_activar": getattr(p, "puede_activar", False)
            })

    return Response({
        "status": 1,
        "error": 0,
        "message": "LISTADO DE PRIVILEGIOS",
        "values": privilegios_list
    })

# --------------------------
# SOLICITUDES DE AGENTES
# --------------------------

@api_view(['GET'])
@requiere_permiso("Usuario", "leer")
def listar_solicitudes_agentes(request):
    """
    Muestra todas las solicitudes de agentes (pendientes, aceptadas o rechazadas)
    """
    solicitudes = SolicitudAgente.objects.all().order_by('-fecha_solicitud')
    serializer = SolicitudAgenteSerializer(solicitudes, many=True)
    return Response({
        "status": 1,
        "error": 0,
        "message": "LISTADO DE SOLICITUDES DE AGENTES",
        "values": serializer.data
    })


@api_view(['PATCH'])
def cambiar_estado_solicitud_agente(request, solicitud_id):
    """
    Cambia el estado de una solicitud de agente a 'aceptado' o 'rechazado'
    """
    solicitud = get_object_or_404(SolicitudAgente, idSolicitud=solicitud_id)
    nuevo_estado = request.data.get('estado')
    if nuevo_estado not in ['aceptado', 'rechazado']:
        return Response({
            "status": 0,
            "error": 1,
            "message": "Estado inválido. Debe ser 'aceptado' o 'rechazado'.",
            "values": None
        }, status=status.HTTP_400_BAD_REQUEST)

    solicitud.estado = nuevo_estado
    solicitud.save()

    # Si se aprueba, crear el usuario automáticamente
    if nuevo_estado == 'aceptado':
        usuario_existente = Usuario.objects.filter(correo=solicitud.correo).first()
        grupo_agente = Grupo.objects.filter(nombre__iexact='agente').first()
        if usuario_existente:
            if grupo_agente and usuario_existente.grupo != grupo_agente:
                usuario_existente.grupo = grupo_agente
                usuario_existente.save()
        else:
            # Crear usuario
            usuario = Usuario.objects.create_user(
                username=solicitud.correo.split('@')[0],
                correo=solicitud.correo,
                nombre=solicitud.nombre,
                telefono=solicitud.telefono,
                password="123456",
                grupo=grupo_agente
            )
            registrar_accion(
                usuario= request.user,
                accion="Registro de agente",
                ip=request.META.get("REMOTE_ADDR")
            )
            Token.objects.create(user=usuario)


    serializer = SolicitudAgenteSerializer(solicitud)
    return Response({
        "status": 1,
        "error": 0,
        "message": f"Solicitud actualizada correctamente a '{nuevo_estado}'",
        "values": serializer.data
    })
# --------------------------
# Listar Usuarios del grupo Agente
# --------------------------

@api_view(['GET'])
@requiere_permiso("Usuario", "leer")
def listar_usuarios_agente(request):
    usuarios = Usuario.objects.filter(grupo__nombre__iexact='agente')
    serializer = UsuarioSerializer(usuarios, many=True)
    return Response({
        "status": 1,
        "error": 0,
        "message": "LISTADO DE USUARIOS DEL GRUPO AGENTE",
        "values": serializer.data
    })
# --------------------------
# Contrato de Servicios Inmobiliarios
# --------------------------

class ContratoServiciosInmobiliariosView(APIView):
    def post(self, request):
        data = request.data
        print("DATA CONTRATO SERVICIOS INMOBILIARIOS", data)
        
        # Ruta del archivo de plantilla
        plantilla_path = os.path.join(settings.BASE_DIR, "usuario/contratoPDF/contrato_servicios_inmobiliarios.txt")
        with open(plantilla_path, "r", encoding="utf-8") as f:
            contrato_text = f.read()

        # Reemplazar variables
        contrato_text = contrato_text.format(
            ciudad=data.get("ciudad", "________________"),
            fecha=data.get("fecha", "____/____/______"),
            empresa_nombre=data.get("empresa_nombre", "________________"),
            empresa_representante=data.get("empresa_representante", "________________"),
            empresa_ci=data.get("empresa_ci", "________________"),
            empresa_domicilio=data.get("empresa_domicilio", "________________"),
            
            cliente_nombre=data.get("cliente_nombre", "________________"),
            cliente_ci=data.get("cliente_ci", "________________"),
            cliente_estado_civil=data.get("cliente_estado_civil", "________________"),
            cliente_profesion=data.get("cliente_profesion", "________________"),
            cliente_domicilio=data.get("cliente_domicilio", "________________"),
            
            agente_nombre=data.get("agente_nombre", "________________"),
            agente_ci=data.get("agente_ci", "________________"),
            agente_estado_civil=data.get("agente_estado_civil", "________________"),
            agente_domicilio=data.get("agente_domicilio", "________________"),
            
            inmueble_direccion=data.get("inmueble_direccion", "________________"),
            inmueble_superficie=data.get("inmueble_superficie", "________________"),
            inmueble_distrito=data.get("inmueble_distrito", "________________"),
            inmueble_manzana=data.get("inmueble_manzana", "________________"),
            inmueble_lote=data.get("inmueble_lote", "________________"),
            inmueble_zona=data.get("inmueble_zona", "________________"),
            inmueble_matricula=data.get("inmueble_matricula", "________________"),
            precio_inmueble=data.get("precio_inmueble", "________________"),
            comision=data.get("comision", "____"),
            vigencia_dias=data.get("vigencia_dias", "____"),
            direccion_oficina=data.get("direccion_oficina", "________________"),
            telefono_oficina=data.get("telefono_oficina", "________________"),
            email_oficina=data.get("email_oficina", "________________"),
        )

        # Crear buffer en memoria
        buffer = io.BytesIO()
        doc = SimpleDocTemplate(
            buffer,
            pagesize=LETTER,
            rightMargin=40,
            leftMargin=40,
            topMargin=40,
            bottomMargin=40
        )

        # Estilos
        styles = getSampleStyleSheet()
        titulo_style = ParagraphStyle(
            'Titulo',
            parent=styles['Heading1'],
            fontSize=14,
            leading=18,
            alignment=TA_CENTER,
            spaceAfter=20,
            textColor=colors.black,
            fontName='Helvetica-Bold'
        )
        clausula_titulo_style = ParagraphStyle(
            'ClausulaTitulo',
            parent=styles['Normal'],
            fontSize=11,
            leading=14,
            alignment=TA_LEFT,
            spaceAfter=6,
            textColor=colors.black,
            fontName='Helvetica-Bold'
        )
        clausula_style = ParagraphStyle(
            'Clausula',
            fontSize=10,
            leading=13,
            alignment=TA_JUSTIFY,
            spaceAfter=8,
        )
        firma_style = ParagraphStyle(
            'Firma',
            fontSize=10,
            leading=12,
            alignment=TA_CENTER,
        )
        footer_style = ParagraphStyle(
            'Footer',
            fontSize=8,
            leading=10,
            alignment=TA_CENTER,
            textColor=colors.grey,
        )

        story = []

        # Título
        story.append(Paragraph("CONTRATO PRIVADO DE PRESTACIÓN DE SERVICIOS INMOBILIARIOS", titulo_style))
        story.append(Spacer(1, 10))

        # Introducción
        intro_text = f"""Conste por el presente Contrato Privado de Servicios Inmobiliarios, que con el sólo reconocimiento de firmas surtirá los efectos de documento público, conforme al tenor de las siguientes cláusulas y condiciones:"""
        story.append(Paragraph(intro_text, clausula_style))
        story.append(Spacer(1, 15))

        # Separar por párrafos usando doble salto de línea
        lineas = contrato_text.strip().split("\n\n")

        # Agregar cláusulas
        for i, p in enumerate(lineas):
            if p.strip().startswith("PRIMERA:") or p.strip().startswith("SEGUNDA:") or p.strip().startswith("TERCERA:") or p.strip().startswith("CUARTA:") or p.strip().startswith("QUINTA:") or p.strip().startswith("SEXTA:") or p.strip().startswith("SÉPTIMA:") or p.strip().startswith("OCTAVA:") or p.strip().startswith("NOVENA:") or p.strip().startswith("DÉCIMA:") or p.strip().startswith("DÉCIMA PRIMERA:") or p.strip().startswith("DÉCIMA SEGUNDA:") or p.strip().startswith("DÉCIMA TERCERA:") or p.strip().startswith("DÉCIMA CUARTA:"):
                story.append(Paragraph(p.strip(), clausula_titulo_style))
            else:
                story.append(Paragraph(p.strip(), clausula_style))
            
            if i != len(lineas) - 1:
                story.append(Spacer(1, 8))

        # Fecha y lugar
        story.append(Spacer(1, 20))
        fecha_lugar = Paragraph(f"{data.get('ciudad', 'Trinidad')}, {data.get('fecha', '____/____/______')}.", clausula_titulo_style)
        story.append(fecha_lugar)
        story.append(Spacer(1, 25))

        # Firmas
        firmas_texto = f"""
        __________________________<br/>
        <b>{data.get('empresa_representante', '________________')}</b><br/>
        <i>{data.get('empresa_nombre', '________________')}</i><br/><br/><br/>

        __________________________<br/>
        <b>{data.get('cliente_nombre', '________________')}</b><br/>
        <i>PROPIETARIO/A</i><br/><br/><br/>

        __________________________<br/>
        <b>{data.get('agente_nombre', '________________')}</b><br/>
        <i>AGENTE ASOCIADO</i>
        """
        story.append(Paragraph(firmas_texto, firma_style))

        # Footer
        story.append(Spacer(1, 20))
        footer_text = f"""
        {data.get('direccion_oficina', '________________')}<br/>
        {data.get('telefono_oficina', '________________')}<br/>
        {data.get('email_oficina', '________________')}<br/>
        <i>Cada oficina es de propiedad y operación independiente</i>
        """
        story.append(Paragraph(footer_text, footer_style))

        # Generar PDF
        doc.build(story)
        buffer.seek(0)

        # Devolver PDF
        response = HttpResponse(buffer, content_type='application/pdf')
        response['Content-Disposition'] = f'attachment; filename="contrato_servicios_inmobiliarios_{data.get("cliente_nombre","cliente")}.pdf"'
        return response