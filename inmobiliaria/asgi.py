"""
ASGI config for inmobiliaria project.

It exposes the ASGI callable as a module-level variable named ``application``.

For more information on this file, see
https://docs.djangoproject.com/en/5.2/howto/deployment/asgi/
"""

import os
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'inmobiliaria.settings')
from django.core.asgi import get_asgi_application
from channels.routing import ProtocolTypeRouter, URLRouter
from contacto.middleware import TokenAuthMiddleware
from contacto import routing # importa el routing de tu app de chat


application = ProtocolTypeRouter({
    "http": get_asgi_application(),  # HTTP normal
    "websocket": TokenAuthMiddleware(
        URLRouter(routing.websocket_urlpatterns)
    ),
})