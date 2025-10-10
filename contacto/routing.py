# contacto/routing.py
from django.urls import path
from .consumers import UserConsumer

websocket_urlpatterns = [
    path("ws/user/<int:user_id>/", UserConsumer.as_asgi()),
]
