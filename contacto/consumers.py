import json
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async


class ChatConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.chat_id = self.scope["url_route"]["kwargs"]["chat_id"]

        # Cerrar conexión si usuario es anónimo
        if self.scope["user"].is_anonymous:
            await self.close()
            return

        self.group_name = f"chat_{self.chat_id}"

        # Unirse al grupo
        await self.channel_layer.group_add(self.group_name, self.channel_name)
        await self.accept()
        print(f"Conexión WS: chat_id={self.chat_id}, usuario={self.scope['user']}")

    async def disconnect(self, close_code):
        if hasattr(self, "group_name"):
            await self.channel_layer.group_discard(self.group_name, self.channel_name)

    async def receive(self, text_data):
        from .models import MensajeModel, ChatModel
        
        if self.scope["user"].is_anonymous:
            await self.close()
            return

        try:
            data = json.loads(text_data)
        except json.JSONDecodeError:
            await self.send(text_data=json.dumps({"error": "Formato JSON inválido"}))
            return

        mensaje_texto = data.get("mensaje")
        if not mensaje_texto:
            await self.send(text_data=json.dumps({"error": "Falta el campo 'mensaje'"}))
            return

        # Guardar mensaje en DB
        chat = await database_sync_to_async(ChatModel.objects.get)(id=self.chat_id)
        usuario = self.scope["user"]
        await database_sync_to_async(MensajeModel.objects.create)(
            chat=chat,
            usuario=usuario,
            mensaje=mensaje_texto
        )

        # Enviar a todos los conectados al grupo
        await self.channel_layer.group_send(
            self.group_name,
            {
                "type": "chat_message",
                "usuario": usuario.nombre,
                "mensaje": mensaje_texto
            }
        )

    async def chat_message(self, event):
        await self.send(text_data=json.dumps({
            "usuario": event["usuario"],
            "mensaje": event["mensaje"]
        }))
