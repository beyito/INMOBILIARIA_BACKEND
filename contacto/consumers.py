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

class UserConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        user = self.scope["user"]
        if user.is_anonymous:
            await self.close()
            return

        # Canal único por usuario
        self.group_name = f"user_{user.id}"
        await self.channel_layer.group_add(self.group_name, self.channel_name)
        await self.accept()
        print(f"[WS conectado] Usuario {user.username} en grupo {self.group_name}")

    async def disconnect(self, close_code):
        if hasattr(self, "group_name"):
            await self.channel_layer.group_discard(self.group_name, self.channel_name)

    async def receive(self, text_data):
        from .models import ChatModel, MensajeModel
        """
        Maneja los mensajes enviados desde el cliente.
        El cliente debe mandar un JSON así:
        {
            "chat_id": 1,
            "mensaje": "Hola!"
        }
        """
        data = json.loads(text_data)
        user = self.scope["user"]

        chat_id = data.get("chat_id")
        mensaje_texto = data.get("mensaje")

        if not chat_id or not mensaje_texto:
            await self.send(json.dumps({"error": "chat_id y mensaje son requeridos"}))
            return

        # Verificar que el usuario pertenezca al chat
        chat = await database_sync_to_async(ChatModel.objects.get)(id=chat_id)
        if user.id not in [chat.cliente_id, chat.agente_id]:
            await self.send(json.dumps({"error": "No autorizado para este chat"}))
            return

        # Guardar el mensaje
        mensaje = await database_sync_to_async(MensajeModel.objects.create)(
            chat=chat,
            usuario=user,
            mensaje=mensaje_texto
        )

        # Armar payload
        payload = {
            "chat_id": chat.id,
            "usuario_id": user.id,
            "usuario_nombre": user.nombre,
            "mensaje": mensaje_texto,
            "fecha_envio": mensaje.fecha_envio.isoformat()
        }

        # Enviar el mensaje a ambos participantes
        await self._notify_chat_participants(chat, payload)

    async def _notify_chat_participants(self, chat, payload):
        """
        Enviar el mensaje a ambos usuarios del chat
        (cliente y agente) usando sus grupos 'user_<id>'
        """
        for uid in [chat.cliente_id, chat.agente_id]:
            await self.channel_layer.group_send(
                f"user_{uid}",
                {"type": "chat_message", "payload": payload}
            )

    async def chat_message(self, event):
        await self.send(text_data=json.dumps(event["payload"]))