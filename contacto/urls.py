# contacto/urls.py

from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import ChatViewSet, MensajeViewSet, marcar_leidos
# Creamos el router para manejar las rutas de DRF
router = DefaultRouter()
router.register(r'chats', ChatViewSet, basename='chat')
router.register(r'mensajes', MensajeViewSet, basename='mensaje')

urlpatterns = [
    path('', include(router.urls)),
    path('mensaje/marcar-leidos/', marcar_leidos, name='marcar-leidos'),
]
