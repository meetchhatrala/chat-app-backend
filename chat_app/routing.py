from django.urls import path
from chat_app import consumers

websocket_urlpatterns = [
    path('ws/user/<int:id>/', consumers.UserChatConsumer.as_asgi()), 
    path('ws/group/<int:id>/', consumers.GroupChatConsumer.as_asgi()),
    path('ws/notifications/', consumers.NotificationConsumer.as_asgi()),
]