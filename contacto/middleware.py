from urllib.parse import parse_qs
from channels.db import database_sync_to_async

class TokenAuthMiddleware:
    """
    Middleware ASGI que añade scope['user'] basado en token DRF.
    """

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        from django.contrib.auth.models import AnonymousUser
        from rest_framework.authtoken.models import Token

        # Obtener token de query string
        query_string = parse_qs(scope.get("query_string", b"").decode())
        token_key = query_string.get("token", [None])[0]

        user = None

        if token_key:
            try:
                # Traer token y usuario dentro de sync_to_async
                @database_sync_to_async
                def get_user_from_token(key):
                    token_obj = Token.objects.get(key=key)
                    return token_obj.user

                user = await get_user_from_token(token_key)
            except Token.DoesNotExist:
                user = AnonymousUser()

        scope["user"] = user or AnonymousUser()

        return await self.app(scope, receive, send)
