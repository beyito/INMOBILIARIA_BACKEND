# usuario/permissions.py
# from rest_framework.permissions import BasePermission, SAFE_METHODS
from requests import Response
#from rest_framework.response import Response
from rest_framework import permissions
from usuario.models import Privilegio
from functools import wraps
from rest_framework import status
from rest_framework.permissions import BasePermission


# permissions.py
from rest_framework.response import Response
from rest_framework import status
from functools import wraps

def requiere_permiso(componente, accion):
    """
    Decorador genérico para cualquier permiso
    """
    def decorator(view_func):
        @wraps(view_func)
        def _wrapped_view(request, *args, **kwargs):
            if has_permission(request.user, componente, accion):
                return view_func(request, *args, **kwargs)
            else:
                mensajes = {
                    "leer": "LEER",
                    "crear": "CREAR", 
                    "actualizar": "ACTUALIZAR",
                    "eliminar": "ELIMINAR"
                }
                accion_texto = mensajes.get(accion, accion.upper())
                
                # ✅ CORRECCIÓN: status como segundo argumento posicional
                return Response({
                    "status": 2,
                    "error": 1,
                    "message": f"NO TIENE PERMISOS PARA {accion_texto} {componente.upper()}"
                })  # Sin 'status='
        return _wrapped_view
    return decorator

def has_permission(usuario, componente_nombre, accion):
    """Función auxiliar para verificar permisos"""
    if not usuario.is_authenticated:
        return False
    
    # Si es administrador, tiene todos los permisos
    if hasattr(usuario, "grupo") and usuario.grupo and usuario.grupo.nombre == "administrador":
        return True

    try:
        privilegio = Privilegio.objects.get(
            grupo=usuario.grupo,
            #componente__nombre=componente_nombre
            componente__nombre__iexact=componente_nombre

        )
    except Privilegio.DoesNotExist:
        return False
    
    mapping = {
        "leer": privilegio.puede_leer,
        "crear": privilegio.puede_crear,
        "actualizar": privilegio.puede_actualizar,
        "eliminar": privilegio.puede_eliminar,
    }
    
    return mapping.get(accion, False)

# Alias para mayor claridad
requiere_lectura = lambda componente: requiere_permiso(componente, "leer")
requiere_creacion = lambda componente: requiere_permiso(componente, "crear")
requiere_actualizacion = lambda componente: requiere_permiso(componente, "actualizar")
requiere_eliminacion = lambda componente: requiere_permiso(componente, "eliminar")