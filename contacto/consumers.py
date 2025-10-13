import json
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from django.conf import settings
import logging

logger = logging.getLogger(__name__)

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
        from inmobiliaria.utils import NotificacionService
        from usuario.models import Dispositivo  # Importar el modelo Dispositivo
        
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
        await self._notify_chat_participants(chat, payload_movil, payload_web, user)

    async def _notify_chat_participants(self, chat, payload_movil, payload_web, remitente):
        """
        Enviar el mensaje a ambos usuarios del chat y notificaciones push
        """
        from inmobiliaria.utils import NotificacionService
        from usuario.models import Dispositivo
        
        # Identificar al receptor (el que NO es el remitente)
        receptor_id = chat.cliente_id if chat.cliente_id != remitente.id else chat.agente_id
        
        # Verificar si el receptor tiene dispositivos registrados
        receptor_tiene_dispositivos = await database_sync_to_async(
            Dispositivo.objects.filter(usuario_id=receptor_id).exists
        )()

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
            if uid != remitente.id:
                await self.channel_layer.group_send(
                    f"user_{uid}",
                    {
                        "type": "web_message", 
                        "payload": payload_web
                    }
                )
        print("enviando mensaje a ambos usuarios del chat")
        # Enviar notificación push al receptor SOLO si tiene dispositivos registrados
        if receptor_id != remitente.id and receptor_tiene_dispositivos:
            await self._enviar_notificacion_push(receptor_id, remitente.nombre, payload_movil["mensaje"], chat.id)

    async def _enviar_notificacion_push(self, usuario_id, nombre_remitente, mensaje, chat_id):
        """
        Enviar notificación push al usuario receptor
        """
        from inmobiliaria.utils import NotificacionService
        
        try:
            # Preparar el título y mensaje de la notificación
            titulo = f"Nuevo mensaje de {nombre_remitente}"
            mensaje_notificacion = mensaje[:100] + "..." if len(mensaje) > 100 else mensaje
            
            # Data extra para manejar la navegación en la app móvil
            data_extra = {
                "tipo": "nuevo_mensaje",
                "chat_id": str(chat_id),
                "usuario_remitente": nombre_remitente
            }
            
            # Enviar notificación usando el servicio
            success = await database_sync_to_async(NotificacionService.enviar_a_usuario)(
                usuario_id, 
                titulo, 
                mensaje_notificacion, 
                data_extra
            )
            
            if success:
                logger.info(f"Notificación push enviada a usuario {usuario_id}")
            else:
                logger.warning(f"No se pudo enviar notificación push a usuario {usuario_id} (aunque tiene dispositivos registrados)")
                
        except Exception as e:
            logger.error(f"Error enviando notificación push a usuario {usuario_id}: {e}")

    async def chat_message(self, event):
        """Para móvil - formato completo"""
        await self.send(text_data=json.dumps(event["payload"]))

    async def web_message(self, event):
        """Para web - formato simple"""
        await self.send(text_data=json.dumps({
            "usuario": event["payload"]["usuario"],
            "mensaje": event["payload"]["mensaje"]
        }))