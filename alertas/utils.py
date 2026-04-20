# alertas/utils.py

import firebase_admin
from firebase_admin import messaging
from usuario.models import Dispositivo # Tu modelo de token
from inmobiliaria.utils import initialize_firebase # Importar la función de inicialización corregida
from .models import AlertaModel
from django.utils import timezone
from django.conf import settings
import traceback
import logging

logger = logging.getLogger(__name__)

def enviar_notificacion_push(alerta: AlertaModel):
    """
    Función que maneja la lógica de envío de notificaciones Push (FCM) y Email.
    """
    if not alerta.usuario_receptor:
        alerta.estado_envio = 'fallido'
        alerta.mensaje += " | FALLO: Usuario receptor no definido."
        alerta.save()
        logger.error(f"Alerta ID {alerta.id} fallida: No hay usuario receptor.")
        return False
        
    # 1. Buscar los tokens del dispositivo del usuario
    dispositivos = Dispositivo.objects.filter(usuario=alerta.usuario_receptor)
    tokens = [d.token for d in dispositivos]
    
    if not tokens:
        logger.warning(f"Alerta ID {alerta.id}: No se encontraron tokens para {alerta.usuario_receptor.nombre}. Intentando Email...")
        return enviar_email_alerta(alerta)

    # Intentar inicializar firebase si aún no está listo
    try:
        # Se asume que initialize_firebase() retorna True/False
        fb_ready = initialize_firebase()
        if not fb_ready:
            logger.warning('Firebase no inicializado en este proceso; se usará fallback por email para la alerta %s', alerta.id)
            alerta.estado_envio = 'fallido'
            alerta.mensaje += ' | FALLO FCM: Firebase no inicializado en proceso.'
            alerta.save()
            return enviar_email_alerta(alerta)
    except Exception:
        logger.exception('Error comprobando inicialización de Firebase')
        return enviar_email_alerta(alerta)

    # Configuración de limpieza automática
    # Asegúrate de definir ALERTAS_AUTO_DELETE_INVALID_DEVICE = True en settings.py
    auto_delete = getattr(settings, 'ALERTAS_AUTO_DELETE_INVALID_DEVICE', False)

    try:
        # 2. Intentar usar Multicast si está disponible
        if hasattr(messaging, 'MulticastMessage') and hasattr(messaging, 'send_multicast'):
            message = messaging.MulticastMessage(
                notification=messaging.Notification(
                    title="Recordatorio Inmobiliario",
                    body=alerta.mensaje,
                ),
                data={
                    'contrato_id': str(alerta.contrato.id),
                    'tipo_alerta': alerta.tipo_alerta,
                    'target': 'movil'
                },
                tokens=tokens,
            )

            # 3. Enviar la notificación a todos los tokens (multicast)
            response = messaging.send_multicast(message)

            # 4. Auditoría y actualización del estado de envío
            failure_count = getattr(response, 'failure_count', 0)
            tokens_eliminados = 0
            
            if failure_count > 0:
                alerta.estado_envio = 'fallido'
                
                # 💥 LÓGICA DE LIMPIEZA DE TOKENS INVÁLIDOS (MULTICAST)
                for idx, resp in enumerate(getattr(response, 'responses', [])):
                    if not getattr(resp, 'success', True):
                        exc = getattr(resp, 'exception', None)
                        exc_str = str(exc) if exc is not None else 'unknown error'
                        token = tokens[idx]
                        
                        logger.warning('Token send failed idx=%s token=%s err=%s', idx, token, exc_str)
                        
                        # Detectar errores definitivos, incluyendo el nuevo error "Requested entity was not found"
                        if token and (
                            'NotRegistered' in exc_str or 
                            'not registered' in exc_str or 
                            'InvalidRegistration' in exc_str or 
                            'registration-token-not-registered' in exc_str.lower() or
                            'Requested entity was not found' in exc_str
                        ):
                            if auto_delete:
                                try:
                                    Dispositivo.objects.filter(token=token).delete()
                                    tokens_eliminados += 1
                                    logger.info('Dispositivo con token %s eliminado por error FCM definitivo', token)
                                except Exception:
                                    logger.exception('No se pudo eliminar dispositivo con token %s', token)
                            else:
                                logger.info('ALERTAS_AUTO_DELETE_INVALID_DEVICE=False: no se borra token inválido %s', token)
                
                alerta.mensaje += f" | FALLO FCM: {failure_count} fallidos ({tokens_eliminados} eliminados)."
                logger.error(f"Fallo en FCM para {alerta.id}: {failure_count} fallidos.")
            else:
                alerta.estado_envio = 'enviado'

            alerta.fecha_envio = timezone.now()
            alerta.save()
            return True
        else:
            # Fallback: enviar uno-a-uno si la versión no soporta send_multicast
            failures = 0
            tokens_a_eliminar = []
            
            for token in tokens:
                try:
                    msg = messaging.Message(
                        notification=messaging.Notification(
                            title="Recordatorio Inmobiliario",
                            body=alerta.mensaje,
                        ),
                        data={
                            'contrato_id': str(alerta.contrato.id),
                            'tipo_alerta': alerta.tipo_alerta,
                            'target': 'movil'
                        },
                        token=token,
                    )
                    messaging.send(msg)
                except Exception as e_token:
                    failures += 1
                    exc_str = str(e_token)
                    logger.error(f"Fallo al enviar token {token} para Alerta {alerta.id}: {exc_str}")
                    
                    # 💥 LÓGICA DE DETECCIÓN Y ACUMULACIÓN PARA ELIMINACIÓN (FALLBACK)
                    if 'NotRegistered' in exc_str or 'not registered' in exc_str or 'InvalidRegistration' in exc_str or 'registration-token-not-registered' in exc_str.lower() or 'Requested entity was not found' in exc_str:
                        if auto_delete:
                            try:
                                Dispositivo.objects.filter(token=token).delete()
                                logger.info('Dispositivo con token %s eliminado por error FCM definitivo', token)
                            except Exception:
                                logger.exception('No se pudo eliminar dispositivo con token %s', token)
                        else:
                            logger.info('ALERTAS_AUTO_DELETE_INVALID_DEVICE=False: no se borra token inválido %s', token)
                        tokens_a_eliminar.append(token)


            if failures > 0:
                alerta.estado_envio = 'fallido'
                alerta.mensaje += f" | FALLO FCM: {failures} fallidos. ({len(tokens_a_eliminar)} eliminados)"
                logger.error(f"Fallo en envíos individuales para Alerta {alerta.id}: {failures} fallidos.")
            else:
                alerta.estado_envio = 'enviado'

            alerta.fecha_envio = timezone.now()
            alerta.save()
            return True

    except Exception as e:
        logger.error(f"Error fatal al enviar FCM para Alerta ID {alerta.id}: {e}")
        alerta.estado_envio = 'fallido'
        alerta.mensaje += f" | FALLO FATAL: {str(e)}"
        alerta.save()
        return enviar_email_alerta(alerta)

# --- Opcional: Envío por Email (para WEB o fallos de Push) ---
from django.core.mail import send_mail

def enviar_email_alerta(alerta: AlertaModel):
    """
    Envía la alerta por correo electrónico.
    """
    try:
        send_mail(
            subject=f"Recordatorio Importante: {alerta.get_tipo_alerta_display()}",
            message=alerta.mensaje,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[alerta.usuario_receptor.correo],
        )
        alerta.estado_envio = 'enviado'
        alerta.fecha_envio = timezone.now()
        alerta.save()
        return True
    except Exception as e:
        logger.error(f"Fallo al enviar EMAIL para Alerta ID {alerta.id}: {e}")
        alerta.estado_envio = 'fallido'
        alerta.mensaje += f" | FALLO EMAIL: {str(e)}"
        alerta.save()
        return False