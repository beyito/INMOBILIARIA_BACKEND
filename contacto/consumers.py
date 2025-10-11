import json
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async

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
        
        data = json.loads(text_data)
        user = self.scope["user"]

        chat_id = data.get("chat_id")
        mensaje_texto = data.get("mensaje")

        if not chat_id or not mensaje_texto:
            await self.send(json.dumps({"error": "chat_id y mensaje son requeridos"}))
            return

        # Verificar que el usuario pertenezca al chat
        try:
            chat = await database_sync_to_async(ChatModel.objects.get)(id=chat_id)
            if user.id not in [chat.cliente_id, chat.agente_id]:
                await self.send(json.dumps({"error": "No autorizado para este chat"}))
                return
        except ChatModel.DoesNotExist:
            await self.send(json.dumps({"error": "Chat no encontrado"}))
            return

        # Guardar el mensaje
        mensaje = await database_sync_to_async(MensajeModel.objects.create)(
            chat=chat,
            usuario=user,
            mensaje=mensaje_texto
        )

        # Armar payload para ambos formatos
        payload_movil = {
            "chat_id": chat.id,
            "usuario_id": user.id,
            "usuario_nombre": user.nombre,
            "mensaje": mensaje_texto,
            "fecha_envio": mensaje.fecha_envio.isoformat()
        }

        payload_web = {
            "usuario": user.nombre,
            "mensaje": mensaje_texto,
            "chat_id": chat.id,
            "usuario_id": user.id
        }

        # Enviar el mensaje a ambos participantes
        await self._notify_chat_participants(chat, payload_movil, payload_web)

    async def _notify_chat_participants(self, chat, payload_movil, payload_web):
        """
        Enviar el mensaje a ambos usuarios del chat
        """
        for uid in [chat.cliente_id, chat.agente_id]:
            # Para móvil (formato completo)
            await self.channel_layer.group_send(
                f"user_{uid}",
                {
                    "type": "chat_message", 
                    "payload": payload_movil
                }
            )
            
            # Para web (formato simple) - solo si es diferente del remitente
            if uid != self.scope["user"].id:
                await self.channel_layer.group_send(
                    f"user_{uid}",
                    {
                        "type": "web_message", 
                        "payload": payload_web
                    }
                )

    async def chat_message(self, event):
        """Para móvil - formato completo"""
        await self.send(text_data=json.dumps(event["payload"]))

    async def web_message(self, event):
        """Para web - formato simple"""
        await self.send(text_data=json.dumps({
            "usuario": event["payload"]["usuario"],
            "mensaje": event["payload"]["mensaje"]
        }))