from usuario.models import Usuario
from django.db import models

class ChatModel(models.Model):
    fecha_creacion = models.DateTimeField(auto_now_add=True)
    cliente = models.ForeignKey(
        Usuario, 
        on_delete=models.CASCADE, 
        related_name="chats_como_cliente"
    )
    agente = models.ForeignKey(
        Usuario, 
        on_delete=models.CASCADE, 
        related_name="chats_como_agente"
    )

    def __str__(self):
        return f"Chat {self.id} - Cliente: {self.cliente} / Agente: {self.agente}"

    class Meta:
        db_table = "chat"


class MensajeModel(models.Model):
    chat = models.ForeignKey(ChatModel, on_delete=models.CASCADE, related_name="mensajes")
    usuario = models.ForeignKey(Usuario, on_delete=models.CASCADE, related_name="mensajes")
    mensaje = models.TextField()
    fecha_envio = models.DateTimeField(auto_now_add=True)
    leido = models.BooleanField(default=False) 

    def __str__(self):
        return f"Mensaje de {self.usuario} en Chat {self.chat.id}"

    class Meta:
        db_table = "mensaje"

