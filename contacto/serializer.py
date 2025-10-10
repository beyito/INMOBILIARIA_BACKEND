# contacto/serializers.py

from rest_framework import serializers
from .models import ChatModel, MensajeModel
from usuario.models import Usuario
from usuario.serializers import UsuarioSerializer

# --------------------------
# Serializador de Mensajes
# --------------------------
class MensajeSerializer(serializers.ModelSerializer):
    chat = serializers.PrimaryKeyRelatedField(queryset=ChatModel.objects.all())
    usuario = UsuarioSerializer(read_only=True)  # <- cambio importante

    class Meta:
        model = MensajeModel
        fields = ["id", "chat", "usuario", "mensaje", "fecha_envio", "leido"]


# --------------------------
# Serializador de Chats
# --------------------------
class ChatSerializer(serializers.ModelSerializer):
    cliente = UsuarioSerializer(read_only=True)  # <- cambio
    agente = UsuarioSerializer(read_only=True)    # <- cambio
    mensajes = MensajeSerializer(many=True, read_only=True)

    class Meta:
        model = ChatModel
        fields = ["id", "fecha_creacion", "cliente", "agente", "mensajes"]
