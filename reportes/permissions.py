# reportes/permissions.py
from rest_framework import permissions

class IsAdminOrAgente(permissions.BasePermission):
    """
    Permite acceso solo a Administradores o Agentes.
    Asume que el usuario está autenticado.
    """
    message = "No tienes permiso para realizar esta acción. Se requiere rol de Administrador o Agente."

    def has_permission(self, request, view):
        # request.user es la instancia de tu modelo Usuario
        if not request.user or not request.user.is_authenticated:
            return False
            
        # Accedemos a la relación 'grupo' y luego al campo 'nombre'
        if not request.user.grupo:
            return False
            
        user_group = request.user.grupo.nombre.lower()
        
        return user_group == 'administrador' or user_group == 'agente'