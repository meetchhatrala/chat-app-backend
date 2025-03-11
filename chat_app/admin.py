from django.contrib import admin
from chat_app.models import CustomUser, FriendRequest, ChatMsg, Group, GroupRequests, GroupChat

# Register your models here.

admin.site.register(CustomUser)
admin.site.register(FriendRequest)
admin.site.register(ChatMsg)
admin.site.register(Group)
admin.site.register(GroupRequests)
admin.site.register(GroupChat)


