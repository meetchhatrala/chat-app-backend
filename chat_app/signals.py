from django.db.models.signals import post_save, pre_delete, m2m_changed
from django.dispatch import receiver
from chat_app.models import Group, GroupRequests, FriendRequest, CustomUser as User
from asgiref.sync import sync_to_async
from channels.layers import get_channel_layer


channel_layer = get_channel_layer()


# Sending notifications to the user when they are added to or removed from a group.
@receiver(m2m_changed, sender=Group.members.through)
async def group_members_update_notification(sender, instance, action, pk_set, **kwargs):

    admin = await sync_to_async(lambda: instance.admin)() 

    if action == "post_add":
        for i in pk_set:
            if admin.id != int(i):  # The admin is automatically added as a member when the group is created, so no notification is sent to the admin.
                
                # Sending group details via notification WebSocket when the user is added.
                await channel_layer.group_send(
                    f"notifications_{i}", 
                    {
                        "type": "send_notification",
                        "id": instance.id,
                        "name": instance.name,
                        "image": instance.group_image.url,
                        "added_to_group": True,
                    }
                )

    elif action == "post_remove":
        removed_members = await sync_to_async(lambda: list(User.objects.filter(id__in=pk_set)))()
        for i in removed_members:
            # Sending group id via notification WS to remove the group from user connections
            await channel_layer.group_send(
                f"notifications_{i.id}",
                {
                    "type": "send_notification",
                    "id": instance.id,
                    "group_closed": True,
                    "msg": f"You are no longer a member of the {instance.name} group",
                }
            )

            # If the user is connected to the group, send a message to the group WebSocket to disconnect the user from the group WebSocket on the frontend (when the user is on the group's chat page).
            await channel_layer.group_send(
                f"chat_group_{instance.id}",
                {
                    "type": "chat_message",
                    "username": i.username,
                    "group_closed": True,
                    "msg": f"You are no longer a member of the {instance.name} group",
                }
            )

           

# Sending notification to all group members when group is deleted
@receiver(pre_delete, sender=Group)
async def group_deletion_notification(sender, instance, **kwargs):

    members = await sync_to_async(lambda: list(instance.members.all()))()
    for i in members:
        await channel_layer.group_send(
            f"notifications_{i.id}",
            {
                "type": "send_notification",
                "id": instance.id,
                "group_deleted": True,
                "msg": f"The group {instance.name} has been deleted",
            }
        )
    
    # If the user is connected to the group, send a message to the group WebSocket to disconnect the user from the group WebSocket on the frontend (when the user is on the group's chat page).
    await channel_layer.group_send(
        f"chat_group_{instance.id}",
        {
            "type": "chat_message",
            "group_deleted": True,
            "msg": f"The group {instance.name} has been deleted",
        }
    )



# Notifies the group admin when a new group join request is received.
@receiver(post_save, sender=GroupRequests)
async def received_group_request_notification(sender, instance, created, **kwargs):
    
    if created:
        ''' 
        When a new group is created, a "GroupRequests" object is created for the admin with the field accepted=True. Therefore, no notification is sent when a GroupRequest object is created with accepted=True, as it pertains to the admin.
        '''

        if instance.accepted == False:
            requested_user = await sync_to_async(lambda: instance.requested_user)()
            admin = await sync_to_async(lambda: instance.group.admin)()
            group = await sync_to_async(lambda: instance.group)()
            
            await channel_layer.group_send(
                f"notifications_{admin.id}",
                {
                    "type": "send_notification",
                    "group_id": group.id,
                    "group_name": group.name,
                    "group_image": group.group_image.url,
                    "group_req_id": instance.id,
                    "username": requested_user.username,
                    "user_id": requested_user.id,
                    "received_group_request": True,
                }
            )



# Send a notification to the user when they receive a new friend request or when their friend request is accepted by another user.
@receiver(post_save, sender=FriendRequest)
async def friend_request_notification(sender, instance, created, **kwargs):

    if 'from_user' in instance._state.fields_cache and 'to_user' in instance._state.fields_cache:
        # Using preloaded values
        from_user = instance.from_user
        to_user = instance.to_user
    else: 
        # if values are not preloaded, querying the db
        req = await sync_to_async(FriendRequest.objects.select_related('from_user', 'to_user').filter(id=instance.id).first)()
        from_user = req.from_user
        to_user = req.to_user
    
    # When a friend request is created, send a notification to the "to_user" to inform them that they have received a friend request.
    if created:
        await channel_layer.group_send(
            f"notifications_{to_user.id}",
            {
                "type": "send_notification",
                "msg": f"You have received friend request from {from_user.username}",
                "id": from_user.id,  
                "name": from_user.first_name,
                "email": from_user.username,
                "image": from_user.image.url,
                "received_friend_request": True,
            }
        )

    else: 
        # When "to_user" accepts friend request, send notification to the "from_user" and update the "from_user's" connections on the frontend
        if instance.accepted:
            await channel_layer.group_send(
                f"notifications_{from_user.id}",
                {
                    "type": "send_notification",
                    "msg": f"{to_user.username} accepted your friend request",
                    "id": to_user.id,  
                    "name": to_user.first_name,
                    "email": to_user.username,
                    "image": to_user.image.url,
                    "accepted_friend_request": True,
                }
            )
        


  
# Triggered when a user unfriends another user.
@receiver(pre_delete, sender=FriendRequest)
async def unfriend_notification(sender, instance, **kwargs):

    if 'from_user' in instance._state.fields_cache and 'to_user' in instance._state.fields_cache:
        # Using preloaded values
        from_user = instance.from_user
        to_user = instance.to_user
    else:
        # if values are not preloaded, querying the db
        req = await sync_to_async(FriendRequest.objects.select_related('from_user', 'to_user').filter(id=instance.id).first)()
        from_user = req.from_user
        to_user = req.to_user

    # If accepted=True, the user is making an unfriend request.
    if instance.accepted == True:

        # Sending a notification to both the "from_user" and "to_user" when the friend connection is deleted.
        await channel_layer.group_send(
            f"notifications_{from_user.id}",
            {
                "type": "send_notification",
                "msg": f"You are no longer friends with {to_user.username}.",
                "id": to_user.id,  
                "friend_connection_deleted": True,
            }
        )

        await channel_layer.group_send(
            f"notifications_{to_user.id}",
            {
                "type": "send_notification",
                "msg": f"You are no longer friends with {from_user.username}.",
                "id": from_user.id,  
                "friend_connection_deleted": True,
            }
        )

        # Sending a friend connection deleted notification to the chat_room WebSocket so that if either user is on the chat page, the frontend (React) will close the chat WebSocket connection.
        users_id = f"{from_user.id}_{to_user.id}" if int(from_user.id) < int(to_user.id) else f"{to_user.id}_{from_user.id}"
        room_name = 'chat_%s' % users_id

        await channel_layer.group_send(
            room_name,
            {
                "type": "chat_message",
                "msg": f"You are no longer friends with {from_user.username}.",
                "id": from_user.id,  
                "friend_connection_deleted": True,
            }
        )

    # If the friend request object is deleted without accepted=True, it means the "to_user" rejected the friend request from the "from_user," and a notification is sent to the "from_user."
    else:
        await channel_layer.group_send(
            f"notifications_{from_user.id}",
            {
                "type": "send_notification",
                "msg": f"{to_user.username} rejected your friend request",
                "rejected_friend_request": True,
            }
        )

