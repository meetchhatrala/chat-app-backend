import jwt
from channels.middleware import BaseMiddleware
from django.contrib.auth.models import AnonymousUser
from channels.db import database_sync_to_async
from django.conf import settings
from django.contrib.auth import get_user_model


@database_sync_to_async
def get_user(user_id):
    User = get_user_model()
    try:
        return User.objects.get(id=user_id)
    except User.DoesNotExist:
        return AnonymousUser()

class JWTAuthMiddleware(BaseMiddleware):
    async def __call__(self, scope, receive, send):

        token = None
        for protocol in scope['subprotocols']:
            if protocol == 'token':
                token = scope['subprotocols'][1]
                break
        
        if token:
            try:
                payload = jwt.decode(token, settings.JWT_SECRET_KEY, algorithms=['HS256'])
                user_id = payload.get('user_id')
                scope['user'] = await get_user(user_id)
            except:
                scope['user'] = AnonymousUser()
        else:
            scope['user'] = AnonymousUser()

        return await super().__call__(scope, receive, send)
