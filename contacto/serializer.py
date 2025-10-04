# contacto/serializers.py

from rest_framework import serializers
from .models import ChatModel, MensajeModel
from usuario.models import Usuario


# --------------------------
# Serializador de Mensajes
# --------------------------
class MensajeSerializer(serializers.ModelSerializer):
    chat = serializers.PrimaryKeyRelatedField(queryset=ChatModel.objects.all())
    usuario = serializers.PrimaryKeyRelatedField(queryset=Usuario.objects.all())

    class Meta:
        model = MensajeModel
        fields = ["id", "chat", "usuario", "mensaje", "fecha_envio"]


# --------------------------
# Serializador de Chats
# --------------------------
class ChatSerializer(serializers.ModelSerializer):
    cliente = serializers.PrimaryKeyRelatedField(queryset=Usuario.objects.all())
    agente = serializers.PrimaryKeyRelatedField(queryset=Usuario.objects.all())
    mensajes = MensajeSerializer(many=True, read_only=True)

    class Meta:
        model = ChatModel
        fields = ["id", "fecha_creacion", "cliente", "agente", "mensajes"]
