from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from chat_app.models import FriendRequest, Group, CustomUser, ChatMsg, GroupChat
from django.db.models import Q
import json


# Chat between two friends
class UserChatConsumer(AsyncWebsocketConsumer):
    
    @database_sync_to_async
    def are_friends(self, user_id, friend_id):
        status = FriendRequest.objects.filter( (Q(from_user__id=user_id) & Q(to_user__id=friend_id)) | (Q(from_user__id=friend_id) & Q(to_user__id=user_id)), accepted=True ).exists()
        return status  # bool
    
    async def connect(self):
        self.friend_id = self.scope['url_route']['kwargs']['id']
        self.user = self.scope['user']

        self.friend = await database_sync_to_async(CustomUser.objects.get)(id=self.friend_id)

        # Ensure user is authenticated
        if self.user.is_authenticated:

            # The room_name will follow the format "chat_<smaller_user_id>_<greater_user_id>".
            # For example, if user.id = 5 and friend_id = 1, the room_name will be "chat_1_5".
            self.users_id = f'{self.user.id}_{self.friend_id}' if int(self.user.id) < int(self.friend_id) else f'{self.friend_id}_{self.user.id}'
            self.room_name = 'chat_%s' % self.users_id

            areFriends = await self.are_friends(self.user.id, self.friend_id)
            if areFriends:  

                await self.channel_layer.group_add(
                    self.room_name,
                    self.channel_name,
                )
                await self.accept('token') 
            else:
                await self.close()
        else:
            await self.close()

    async def receive(self, text_data):
        text_data_json = json.loads(text_data)
        message = text_data_json.strip()

        if len(message) == 0:
            return
            
        msg = await ChatMsg.objects.acreate(sender=self.user, receiver=self.friend, message=message)
        username = self.user.username

        await self.channel_layer.group_send(
            self.room_name,
            {
                'type': 'chat_message',
                'id': msg.id, 
                'message': message,
                'username': username,
                'time_stamp': 'message_time_stamp'
            }
        )

    async def chat_message(self, event):
        await self.send(text_data=json.dumps(event))

    async def disconnect(self, close_code):
        await self.channel_layer.group_discard(
            self.room_name, 
            self.channel_name
            )



# For group chatting
class GroupChatConsumer(AsyncWebsocketConsumer):

    @database_sync_to_async
    def is_groupmember(self, user_id, group_id):
        request_status = Group.objects.filter(id=group_id, members__id=user_id).exists()
        return request_status  # returns bool true/false

    async def connect(self):
        self.group_id = self.scope['url_route']['kwargs']['id']
        self.user = self.scope['user']
        self.current_group = await database_sync_to_async(Group.objects.get)(id=self.group_id)

        # Ensure user is authenticated
        if self.user.is_authenticated:
            self.room_name = f'group_{self.group_id}'
            self.room_group_name = 'chat_%s' % self.room_name

            is_member = await self.is_groupmember(self.user.id, self.group_id)

            if is_member:
                await self.channel_layer.group_add(
                    self.room_group_name,
                    self.channel_name
                )

                await self.accept('token')
            else:
                await self.close()
        else:
            await self.close()

    
    async def receive(self, text_data):
        text_data_json = json.loads(text_data)
        message = text_data_json.strip()

        if len(message) == 0:
            return

        msg = await GroupChat.objects.acreate(group=self.current_group, sender=self.user, message=message)

        await self.channel_layer.group_send(
            self.room_group_name,
            {
                'type': 'chat_message',
                'id': msg.id, 
                'message': message,
                'username': self.user.username,
                'name': self.user.first_name + f' {self.user.last_name}',
                'user_id': self.user.id,
                'user_img': self.user.image.url,
                # 'time_stamp': 'message_time_stamp'
            }
        )

    async def chat_message(self, event):
        await self.send(text_data=json.dumps(event))


    async def disconnect(self, close_code):
        await self.channel_layer.group_discard(
            self.room_group_name, 
            self.channel_name
            )



# For realtime notifications        
class NotificationConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.user = self.scope['user']
        self.group_name = f"notifications_{self.user.id}"

        if self.user.is_authenticated:

            await self.channel_layer.group_add(
                self.group_name,
                self.channel_name
            )
            await self.accept('token')

    # Since this is a notification consumer, no data is being received from the client (frontend).
    async def receive(self, text_data):
        pass

    async def send_notification(self, event):
        await self.send(text_data=json.dumps(event))

    async def disconnect(self, close_code):
        await self.channel_layer.group_discard(
            self.group_name, 
            self.channel_name
        )

