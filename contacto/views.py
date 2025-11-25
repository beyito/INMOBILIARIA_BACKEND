from rest_framework import viewsets
from rest_framework.response import Response
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import IsAuthenticated
from django.shortcuts import get_object_or_404
from rest_framework.decorators import action
from inmobiliaria.permissions import has_permission
from rest_framework import status
from rest_framework.decorators import api_view

from .models import ChatModel, MensajeModel
from .serializer import ChatSerializer, MensajeSerializer
from usuario.models import Usuario
from suscripciones.models import Suscripcion
# --------------------------
# CHAT
# --------------------------
class ChatViewSet(viewsets.ModelViewSet):
    queryset = ChatModel.objects.all()
    serializer_class = ChatSerializer
    permission_classes = [IsAuthenticated]

    # GET /contacto/chats/{id}/mensajes/
    @action(detail=True, methods=['get'])
    def mensajes(self, request, pk=None):
        # Verificar permiso de lectura en componente Chat
        if not has_permission(request.user, "Chat", "leer"):
            return Response({
                "status": 2,
                "error": 1,
                "message": "NO TIENE PERMISOS PARA LEER CHAT"
            })

        chat = get_object_or_404(ChatModel, pk=pk)
        mensajes = chat.mensajes.all()
        serializer = MensajeSerializer(mensajes, many=True)
        return Response({
            "status": 1,
            "error": 0,
            "message": "MENSAJES OBTENIDOS",
            "values": serializer.data
        })

    # GET /contacto/chats/
    def list(self, request, *args, **kwargs):
        """
        Devuelve la lista de chats en el formato:
        {
            "status": 1,
            "error": 0,
            "message": "CHATS OBTENIDOS",
            "values": [...]
        }
        """
        queryset = self.get_queryset()
        serializer = self.get_serializer(queryset, many=True)
        return Response({
            "status": 1,
            "error": 0,
            "message": "CHATS OBTENIDOS",
            "values": serializer.data
        }, status=status.HTTP_200_OK)

    # POST /contacto/chats/
    def perform_create(self, serializer):
        # Verificar permiso de creación en componente Chat
        usuario = self.request.user

        # --- 🔒 CANDADO SAAS: Límite de Chats Activos ---
        # Solo aplicamos el límite si es Agente (los clientes suelen ser gratis)
        if usuario.grupo and usuario.grupo.nombre.lower() == 'agente':
            if not (usuario.is_staff or usuario.is_superuser):
                try:
                    sub = usuario.suscripcion
                    if not sub.esta_activa:
                        raise ValidationError("Suscripción vencida. No puedes iniciar nuevos chats.")
                    
                    # Lógica: Si es Plan Básico, solo 5 chats simultáneos
                    # Si tu modelo Plan no tiene 'limite_chats', podemos hardcodearlo por precio o nombre
                    limite_chats = 5 if sub.plan.precio < 50 else 9999
                    
                    chats_actuales = ChatModel.objects.filter(agente=usuario).count()
                    
                    if chats_actuales >= limite_chats:
                         raise ValidationError(f"Límite de chats alcanzado ({limite_chats}). Actualiza a PRO para chats ilimitados.")

                except Suscripcion.DoesNotExist:
                     raise ValidationError("Necesitas una suscripción para contactar clientes.")
        # ------------------------------------------------
        if not has_permission(self.request.user, "Chat", "crear"):
            return Response({
                "status": 2,
                "error": 1,
                "message": "NO TIENE PERMISOS PARA CREAR CHAT"
            })

        cliente = serializer.validated_data.get('cliente')
        agente = serializer.validated_data.get('agente')

        # Validar que el agente sea realmente un agente
        if not agente.grupo or agente.grupo.nombre.strip().lower() != "agente":
            raise ValidationError("El agente seleccionado no es un agente inmobiliario válido.")

        # 🔍 Verificar si ya existe un chat entre cliente y agente
        existing_chat = ChatModel.objects.filter(cliente=cliente, agente=agente).first()

        if existing_chat:
            # Si ya existe, devolver el mismo formato que al crear uno nuevo
            existing_serializer = self.get_serializer(existing_chat)
            self.existing_chat_response = {
                "status": 1,
                "error": 0,
                "message": "CHAT YA EXISTENTE ENTRE CLIENTE Y AGENTE",
                "values": existing_serializer.data
            }
            return  # No crear uno nuevo

        # Guardar un nuevo chat si no existe
        chat = serializer.save()
        self.created_chat_response = {
            "status": 1,
            "error": 0,
            "message": "CHAT CREADO CORRECTAMENTE",
            "values": self.get_serializer(chat).data
        }

    def get_queryset(self):
        user = self.request.user
        # devolver solo chats donde el usuario es cliente o agente
        return ChatModel.objects.filter(cliente=user) | ChatModel.objects.filter(agente=user)

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer)

        if hasattr(self, 'existing_chat_response'):
            return Response(self.existing_chat_response, status=status.HTTP_200_OK)

    # Si se creó uno nuevo, devolver ese body
        return Response(self.created_chat_response, status=status.HTTP_201_CREATED)


# --------------------------
# MENSAJE
# --------------------------
class MensajeViewSet(viewsets.ModelViewSet):
    queryset = MensajeModel.objects.all()
    serializer_class = MensajeSerializer
    permission_classes = [IsAuthenticated]

    # POST /contacto/mensajes/
    def perform_create(self, serializer):
        # Verificar permiso de creación en componente Mensaje
        if not has_permission(self.request.user, "Mensaje", "crear"):
            raise ValidationError("NO TIENE PERMISOS PARA CREAR MENSAJE")

        chat = serializer.validated_data['chat']
        usuario = serializer.validated_data['usuario']

        # Validar que el usuario sea parte del chat
        if chat.cliente != usuario and chat.agente != usuario:
            raise ValidationError("El usuario no es parte de este chat.")

        serializer.save()

@api_view(['POST'])
def marcar_leidos(request):
    """
    Marca como leídos los mensajes que reciban en la lista de IDs.
    Body esperado: { "mensaje_ids": [1,2,3,...] }
    """
    print("llega:",request.data)
    mensaje_ids = request.data.get("mensaje_ids", [])
    if not isinstance(mensaje_ids, list) or not mensaje_ids:
        return Response({
            'success': False,
            'data': None,
            'error': 'No se proporcionaron IDs válidos'
        }, status=400)

    mensajes = MensajeModel.objects.filter(id__in=mensaje_ids)
    mensajes.update(leido=True)

    # Devolver IDs actualizados
    datos = [{"id": m.id, "chat_id": m.chat.id, "leido": True} for m in mensajes]

    return Response({
        'success': True,
        'data': datos,
        'error': None
    })