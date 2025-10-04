from rest_framework import viewsets
from rest_framework.response import Response
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import IsAuthenticated
from django.shortcuts import get_object_or_404
from rest_framework.decorators import action
from inmobiliaria.permissions import has_permission

from .models import ChatModel, MensajeModel
from .serializer import ChatSerializer, MensajeSerializer
from usuario.models import Usuario

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

    # POST /contacto/chats/
    def perform_create(self, serializer):
        # Verificar permiso de creación en componente Chat
        if not has_permission(self.request.user, "Chat", "crear"):
            raise ValidationError("NO TIENE PERMISOS PARA CREAR CHAT")

        cliente = serializer.validated_data.get('cliente')
        agente = serializer.validated_data.get('agente')

        # Validar que el agente sea realmente un agente
        if not agente.grupo or agente.grupo.nombre.strip().lower() != "agente":
            raise ValidationError("El agente seleccionado no es un agente inmobiliario válido.")

        # Guardar un nuevo chat cada vez
        serializer.save()


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
