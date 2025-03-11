from django.http import JsonResponse
from django.contrib.auth import authenticate
from asgiref.sync import sync_to_async
from django.db.models import Q

from chat_app.models import FriendRequest, ChatMsg, Group, GroupRequests, GroupChat
from chat_app.models import CustomUser as User

from django.middleware.csrf import get_token

import json
import jwt
import datetime
from django.conf import settings



# Create your views here.


async def set_csrf_cookie(request):
    # Generate and set the CSRF token manually
    get_token(request)
    return JsonResponse({'set': True})


def generate_jwt_token(userid, username):
    payload = {
        'user_id': userid,
        'username': username,
        'exp': datetime.datetime.now(datetime.UTC) + datetime.timedelta(days=30)
    }
    token = jwt.encode(payload, settings.JWT_SECRET_KEY, algorithm='HS256')
    return token

def verify_jwt_token(token):
    try:
        payload = jwt.decode(token, settings.JWT_SECRET_KEY, algorithms=['HS256'])
        return payload
    except jwt.ExpiredSignatureError:   # Expired token
        return None
    except:     # Invalid token
        return None


def search_user(query, user_id):
    if query:
        users_list = []
        groups_list = []

        # Fetch all users that match the query (username or first name)
        users = User.objects.filter(Q(username__icontains=query) | Q(first_name__icontains=query))

        # Fetch all groups that match the query (group name)
        groups = Group.objects.filter(name__icontains=query)

        # Fetch all friend requests related to the current user
        friend_requests = FriendRequest.objects.filter(Q(from_user__id=user_id) | Q(to_user__id=user_id)).select_related('from_user', 'to_user')

        # Create a dictionary with friend_requests objects
        friend_request_map = {
            (req.from_user.id, req.to_user.id): req for req in friend_requests
        }

        # Loop through the users and append details to users_list
        for user in users:
            if user.id == int(user_id):
                continue  # Skip the current user

            user_details = {
                'id': user.id,
                'email': user.username,
                'name': user.first_name,
                'image': user.image.url,
                'request_send': False,
                # 'request_received': False,
                # 'request_accepted': False
            }

            # Check if there's a friend request between the current user and this search_user
            friend_request_status = friend_request_map.get((user_id, user.id)) or friend_request_map.get((user.id, user_id))
            if friend_request_status:
                if friend_request_status.from_user.id == int(user_id):
                    user_details['request_send'] = True
                else:
                    user_details['request_received'] = True
                user_details['request_accepted'] = friend_request_status.accepted

            users_list.append(user_details)

        # Fetch all group requests related to the user 
        group_requests = GroupRequests.objects.filter(group__in=groups, requested_user__id=user_id)
        group_request_map = {req.group.id: req for req in group_requests}

        # Loop through the groups and append details to groups_list
        for group in groups:
            group_details = {
                'id': group.id,
                'name': group.name,
                'image': group.group_image.url,
                'request_send': False,
                # 'request_accepted': False
            }

            # Check if there's a group request for this user in the group
            group_request_status = group_request_map.get(group.id)
            if group_request_status:
                group_details['request_send'] = True
                group_details['request_accepted'] = group_request_status.accepted

            groups_list.append(group_details)

        # Return the lists of users and groups
        return {'users_list': users_list, 'groups_list': groups_list}

# Search function
async def search(request):
    if request.method == "POST":
        query = request.POST.get('search')
        tk = request.POST.get('tk')

        verify_token = await sync_to_async(verify_jwt_token)(tk)

        if verify_token:
            user_id = verify_token.get('user_id')
            search_query = sync_to_async(search_user)
            data = await search_query(query, user_id)  
            return JsonResponse(data)


# Checking if current user already made a request to another user
def is_requested_user(from_user_id, to_user_id):
    user_requested = FriendRequest.objects.select_related('from_user', 'to_user').filter( (Q(from_user__id=from_user_id) & Q(to_user__id=to_user_id)) | (Q(from_user__id=to_user_id) & Q(to_user__id=from_user_id)) )
    if user_requested:
        return user_requested
    return None

# Checking if the current user already made a request to the group
def is_requested_group(from_user_id, group_id):
    user_requested = GroupRequests.objects.filter(group__id=group_id, requested_user__id=from_user_id)
    if user_requested:
        return user_requested
    return None


# For making a friend request to a user or joining request to a group
async def friend_request(request):
    if request.method == "POST":
        request_type = request.POST.get('type')    # will be request to 'user' or 'group'
        id = request.POST.get('id')
        tk = request.POST.get('tk')

        verify_token = await sync_to_async(verify_jwt_token)(tk)
        if verify_token:
            user_id = verify_token.get('user_id')
            from_user = await sync_to_async(User.objects.get)(id=user_id)

            # For friend request
            if request_type == 'user':
                request_to_user = await sync_to_async(User.objects.get)(id=id)

                # Checking if current user already made a request to the user
                user_request_exists = await sync_to_async(is_requested_user)(from_user.id, request_to_user.id)

                if not user_request_exists:
                    make_user_request = await FriendRequest.objects.acreate(from_user=from_user, to_user=request_to_user)
                return JsonResponse({'send': True})
                
            # For group joining request
            else:
                request_to_group = await sync_to_async(Group.objects.select_related('admin').get)(id=id)

                # Checking if user already made a request to the group
                user_request_exist = await sync_to_async(is_requested_group)(from_user.id, request_to_group.id)

                if not user_request_exist:
                    make_group_request = await GroupRequests.objects.acreate(group=request_to_group, requested_user=from_user)
                    return JsonResponse({'send': True})
            

# For accepting/rejecting friend request and for Unfriend request
async def handle_request(request):
    if request.method == "POST":
        req_type = request.POST.get('type')    # will be "accept", "reject" or "unfriend"
        tk = request.POST.get('tk')
        id = request.POST.get('id')

        verify_token = await sync_to_async(verify_jwt_token)(tk)

        if verify_token:
            user_id = verify_token.get('user_id')

            friend_req = await sync_to_async(FriendRequest.objects.select_related('from_user', 'to_user').get)( Q(from_user__id=user_id, to_user__id=id) | Q(from_user__id=id, to_user__id=user_id))

            # Accepting friend request
            if req_type == 'accept':
                friend_req.accepted = True
                await sync_to_async(friend_req.save)()

            # Rejecting request or Deleting friend
            else:
                await sync_to_async(friend_req.delete)()
                # if unfriend the user, deleting all the previous chat's
                if req_type == 'unfriend':
                    await sync_to_async(ChatMsg.objects.filter( Q(sender__id=user_id, receiver__id=id) | Q(sender__id=id, receiver__id=user_id)).delete)()

            return JsonResponse({'status': True})
        


def get_user_connections(user_id):
    friends_list = []
    groups_list = []
    for req in FriendRequest.objects.select_related('from_user', 'to_user').filter(Q(from_user__id=user_id) | Q(to_user__id=user_id), accepted=True):

        friend = req.to_user if req.from_user.id == user_id else req.from_user
        user_details = {
            'id': friend.id,
            'name': friend.first_name,
            'email': friend.username,
            'image': friend.image.url,
        }

        friends_list.append(user_details)

    for group in Group.objects.filter(members__id=user_id):
        group_details = {
            'id': group.id,
            'name': group.name,
            'image': group.group_image.url
        }
        groups_list.append(group_details)

    return {'friends_list': friends_list, 'groups_list': groups_list}

# Sending Friends/Groups list in which current user is a friend/member
async def get_connections(request):
    if request.method == "POST":
        tk = request.POST.get('tk')
        verify_token = await sync_to_async(verify_jwt_token)(tk)
        
        if verify_token:
            user_id = verify_token.get('user_id')
            data = await sync_to_async(get_user_connections)(user_id)

            return JsonResponse(data)



def get_all_chats(request_type, user_id, id):    # id = friend id (or) group id
    messages = []
    
    # Getting the chats between current user and selected user(friend)
    if request_type == "user":

        # Checking if the current user and selected user are actually friends
        user_connection_status = FriendRequest.objects.filter( (Q(from_user__id=user_id) & Q(to_user__id=id)) | (Q(from_user__id=id) & Q(to_user__id=user_id)), accepted=True)

        if user_connection_status:
            user_messages = ChatMsg.objects.select_related('sender', 'receiver').filter( (Q(sender__id=user_id) & Q(receiver__id=id)) | (Q(sender__id=id) & Q(receiver__id=user_id)) ).order_by('time_stamp')
            for message in user_messages:
                msg = {
                    'id': message.id,
                    'message': message.message,
                    'time_stamp': message.time_stamp,
                }
                if message.sender.id == int(user_id):
                    msg['type'] = 'send-msg'
                else:
                    msg['type'] = 'received-msg'
                messages.append(msg)

    # If user selected group getting that group chats
    else:
        # Getting the selected group chats where the current user is a member 
        group_messages = GroupChat.objects.filter(group__id=id, group__members__id=user_id).select_related('sender').order_by('time_stamp')
        for message in group_messages:

            msg = {
                'id': message.id,
                'message': message.message,
                'time_stamp': message.time_stamp,
                'user_id': message.sender.id,
                'name': message.sender.first_name + f' {message.sender.last_name}' 
            }
            if message.sender.id == int(user_id):
                msg['type'] = 'send-msg'
            else:
                msg['user_img'] = message.sender.image.url     # user image url
                msg['type'] = 'received-msg'
            messages.append(msg)
        
    return messages

# For getting previous chat's with a friend/group 
async def get_chats(request):
    if request.method == "POST":
        request_type = request.POST.get('type')     # will be user/group
        id = request.POST.get('id')
        tk = request.POST.get('tk')

        verify_token = await sync_to_async(verify_jwt_token)(tk)
        if verify_token:
            user_id = verify_token.get('user_id')
            username = verify_token.get('username')
            chat_func = sync_to_async(get_all_chats)
            chats = await chat_func(request_type, user_id, id)
            return JsonResponse({'username': username, 'chats': chats})


# Handle's group creation
async def create_group(request):
    if request.method == "POST":
        group_name = request.POST.get('group_name')
        img = request.FILES.get('image')
        tk = request.POST.get('tk')
        verify_token = await sync_to_async(verify_jwt_token)(tk)

        if verify_token:
            user_id = verify_token.get('user_id')
            user = await sync_to_async(User.objects.get)(id=user_id)
            
            if img:
                group = await Group.objects.acreate(name=group_name, group_image=img, admin=user)
            else: 
                group = await Group.objects.acreate(name=group_name, admin=user)
                
            await sync_to_async(group.members.add)(user)    # add admin(current user) to members field of the newly created group

            # Creating GroupRequest object and passing admin as requested user with accepted field to True, as the "search" function results are based on "GroupRequests"
            await GroupRequests.objects.acreate(group=group, requested_user=user, accepted=True)  

            return JsonResponse({'created': True, 'id': group.id, 'name': group.name, 'image': group.group_image.url})


def get_notify(user_id):
    friend_requests = []
    group_requests = []

    for req in FriendRequest.objects.select_related('from_user', 'to_user').filter(to_user__id=user_id, accepted=False):
        friend = req.from_user
        user_details = {
            'id': friend.id,
            'name': friend.first_name,
            'email': friend.username,
            'image': friend.image.url,
        }
        friend_requests.append(user_details)

    for req in  GroupRequests.objects.filter(group__admin__id=user_id, accepted=False).select_related('requested_user', 'group').order_by('group__id'):
        group_request = {
            'group_id': req.group.id,
            'group_name': req.group.name,
            'group_image': req.group.group_image.url,
            'group_req_id': req.id,
            'username': req.requested_user.username,
            'user_id': req.requested_user.id,
        }
        group_requests.append(group_request)

    return {'friend_requests': friend_requests, 'group_requests': group_requests}

# To send all notifications of the current user when page loads
async def get_notifications(request):
    if request.method == "POST":
        tk = request.POST.get('tk')
        verify_token = await sync_to_async(verify_jwt_token)(tk)

        if verify_token:
            user_id = verify_token.get('user_id')
            # friend_requests, group_requests
            data = await sync_to_async(get_notify)(user_id)
            return JsonResponse(data)
            


# Accept/Reject user group joining request by admin of the group
async def handle_group_request(request):
    if request.method == "POST":
        req_type = request.POST.get('type')
        req_id = request.POST.get('id')
        tk = request.POST.get('tk')

        verify_token = await sync_to_async(verify_jwt_token)(tk)
        if verify_token:
            user_id = verify_token.get('user_id')

            group_request = await sync_to_async(GroupRequests.objects.select_related('group__admin', 'requested_user').get)(id=req_id)

            group = group_request.group

            if int(group.admin.id) == int(user_id):    # Check if request is made by group admin

                if req_type == 'accept':

                    requested_user = group_request.requested_user    # requested user object
                    group_request.accepted = True   # accepting the request
                    await group_request.asave()    # saving the group request object

                    # Adding the user to members field of the group
                    await sync_to_async(group.members.add)(requested_user)

                # for rejecting request
                else:
                    await group_request.adelete()

                return JsonResponse({'status': True})


# Get group members, only if request made by group admin
async def get_members(request, group_id):
    tk = request.COOKIES.get('tk')
    verify_token = await sync_to_async(verify_jwt_token)(tk)

    if verify_token:
        user_id = verify_token.get('user_id')

        group = await sync_to_async(Group.objects.select_related('admin').prefetch_related('members').get)(id=group_id)

        if int(group.admin.id) == int(user_id):  # verify the request made by group admin
            members = group.members.all()
            members_data = [
                {'id': i.id, 'name': i.first_name, 'email': i.username, 'image': i.image.url} 
                for i in members if i.id != int(user_id)     # not including admin as member
                ]  
            
            return JsonResponse({'members': members_data})




# Remove group members, only if request made by group admin
async def remove_members(request, group_id):
    if request.method == "POST":
        members = json.loads(request.POST.get('members'))   # will be ["1", "2", "3"]
        members_id = set(map(int, members))       # converting id's to integers
        tk = request.POST.get('tk')
        verify_token = await sync_to_async(verify_jwt_token)(tk)

        if verify_token:
            user_id = verify_token.get('user_id')   # admin id

            group = await sync_to_async(Group.objects.select_related('admin').get)(id=group_id, admin__id=user_id)

            if int(group.admin.id) == int(user_id):     # Check if request is made by admin

                members_id.discard(int(user_id))    # Remove admin id from members_id if it was present (Security check: The admin cannot remove their own access from the group)

                await group.members.aremove(*members_id)  # Remove members from the group
                
                group_requests = await sync_to_async(GroupRequests.objects.filter)(requested_user__id__in=members_id, accepted=True)
                await group_requests.adelete()    # Removing Group requests as well

                chat = await sync_to_async(GroupChat.objects.filter)(group__id=group_id, sender__id__in=members_id)
                await chat.adelete()    # Removing all the chat messages send by the removed members from the group

                return JsonResponse({'status': True})



def get_friends_object(user_id, members_id):
    # Returns the FriendRequest objects where admin(user_id) and user's(members_id) are already have friend connection
    friend_req = FriendRequest.objects.select_related('from_user', 'to_user').filter( 
        Q(from_user__id__in=members_id, to_user__id=user_id) | Q(from_user__id=user_id, to_user__id__in=members_id), accepted=True
        )
    # Return user objects
    friends = [i.from_user if i.from_user.id != int(user_id) else i.to_user for i in friend_req]    
    return friends

# For adding members to group, request should made by admin
# Admin can add user's to group as members from friend connections only
async def add_members(request, group_id):
    if request.method == "POST":
        members = json.loads(request.POST.get('members'))   # will be ["1", "2", "3"]
        members_id = set(map(int, members))

        tk = request.POST.get('tk')
        verify_token = await sync_to_async(verify_jwt_token)(tk)

        if verify_token:
            user_id = verify_token.get('user_id')

            group = await sync_to_async(Group.objects.select_related('admin').get)(id=group_id, admin__id=user_id)

            if int(group.admin.id) == int(user_id):

                friends = await sync_to_async(get_friends_object)(user_id, members_id)    # Calls "get_friends_object" function

                # Deleting the old request's made by friends to join the group as the admin adding those friends to the group directly
                prev_group_requests = await sync_to_async(GroupRequests.objects.filter)(group__id=group_id, requested_user__in=friends)
                await prev_group_requests.adelete()

                # Creating "GroupRequests" object's for all the users that are going to be added to the group 
                group_req = [GroupRequests(group=group, requested_user=i, accepted=True) for i in friends]
                await GroupRequests.objects.abulk_create(group_req)

                # Adding user's to members field of the Group
                await sync_to_async(group.members.add)(*friends)

                return JsonResponse({'status': True})



# Returns the details of a specific user
async def get_user_details(request, id):
    tk = request.COOKIES.get('tk')
    verify_token = await sync_to_async(verify_jwt_token)(tk)

    if verify_token:
        user_id = verify_token.get('user_id')
        searched_user = await sync_to_async(User.objects.get)(id=id)
        friend_request = await sync_to_async(is_requested_user)(user_id, id)
        data = {
            'first_name': searched_user.first_name,
            'last_name': searched_user.last_name,
            'email': searched_user.username,
            'image': searched_user.image.url,
        }
        if friend_request:
            data['is_friend'] = friend_request[0].accepted
            if int(friend_request[0].from_user.id) == int(user_id):
                data['request_sent'] = True
            else:
                data['received_request'] = True

        return JsonResponse(data)



# Returns the details of a specific group
async def get_group_details(request, id):
    tk = request.COOKIES.get('tk')
    verify_token = await sync_to_async(verify_jwt_token)(tk)

    if verify_token:
        user_id = verify_token.get('user_id')
        group = await sync_to_async(Group.objects.select_related('admin').get)(id=id)
        data = {
            'name': group.name,
            'group_admin': group.admin.username,
            'image': group.group_image.url,
            'request_sent': False
        }
        if group.admin.id == user_id:
            data['is_admin'] = True
        else:
            group_request = await sync_to_async(GroupRequests.objects.filter(requested_user__id=user_id, group__id=id).first)()
            if group_request:
                data['is_member'] = group_request.accepted
                data['request_sent'] = True

        return JsonResponse(data)



def rm_connection(id, user_id):
    group = Group.objects.filter(id=id).select_related('admin').prefetch_related('members')
    if int(user_id) == group[0].admin.id:  # if requested user is admin, deleting that group
        group[0].delete()    

    # Removing the member from group, if requests made by member
    else:
        group_request = GroupRequests.objects.get(group__id=id, requested_user__id=user_id)   
        group_request.delete()      # Delete group request of the member
        group[0].members.remove(user_id)    # Removes user from members

        # Delete the chat messages made by the user from group
        chat = GroupChat.objects.filter(group__id=id, sender__id=user_id)    
        chat.delete()

    return True

# If the request is made by a member, removes the member from the group
# If the request is made by the group admin, deletes the group
async def remove_connection(request):
    if request.method == "POST":
        id = request.POST.get('id')    # will be group ID
        tk = request.POST.get('tk')

        verify_token = await sync_to_async(verify_jwt_token)(tk)
        if verify_token:
            user_id = verify_token.get('user_id')
            rm_conn = await sync_to_async(rm_connection)(id, user_id)
            if rm_conn:
                return JsonResponse({'status': True}) 



# Account details
async def get_account_details(request):
    if request.method == "POST":
        tk = request.POST.get('tk')
        verify_token = await sync_to_async(verify_jwt_token)(tk)
        
        if verify_token:
            user_id = verify_token.get('user_id')
            user = await sync_to_async(User.objects.get)(id=user_id)

            return JsonResponse({'first_name': user.first_name, 'last_name': user.last_name, 'email': user.username, 'image': user.image.url})



# Updates account details
async def update_account_details(request):
    if request.method == "POST":
        img = request.FILES.get('image')
        first_name = request.POST.get('first_name')
        last_name = request.POST.get('last_name')
        tk = request.POST.get('tk')
        verify_token = await sync_to_async(verify_jwt_token)(tk)

        if verify_token:
            user_id = verify_token.get('user_id')
            user = await sync_to_async(User.objects.get)(id=user_id)

            user.first_name = first_name
            user.last_name = last_name
            
            if img:
                user.image = img 

            await user.asave()

            return JsonResponse({'updated': True})
        else:
            return JsonResponse({'updated': False})


# Login user
async def login(request):
    if request.method == "POST":
        username = request.POST.get('email').lower()
        password = request.POST.get('password')

        user = await sync_to_async(authenticate)(username=username, password=password)

        if user is not None:
            # Generating token
            generate_token = sync_to_async(generate_jwt_token)
            token = await generate_token(user.id, user.username)

            return JsonResponse({'token': token, 'authenticated': True})

        return JsonResponse({'authenticated': False})



def get_user(username):
    user_exist = User.objects.filter(username=username)
    if user_exist:
        return user_exist
    return None

def create_user(first_name, username, password):
    user = User.objects.create_user(username=username, first_name=first_name, password=password)
    return user

# Signup User
async def signup(request):
    if request.method == "POST":
        email = request.POST.get('email').lower()
        first_name = request.POST.get('first_name')
        password1 = request.POST.get('password1')
        password2 = request.POST.get('password2')

        if password1 != password2:
            return JsonResponse({'authenticated': False, 'error': 'Passwords do not match!'})
            
        if len(password1) < 8:
            return JsonResponse({'authenticated': False, 'error': 'Password must be at least 8 characters long.'})
        
        getuser = sync_to_async(get_user)
        user_exist = await getuser(email)

        if user_exist:
            return JsonResponse({'authenticated': False, 'error': 'The email already exists. Please try to log in.'})

        # Creating user
        user_create = sync_to_async(create_user)
        user = await user_create(first_name=first_name, username=email, password=password1)

        # Generates token
        generate_token = sync_to_async(generate_jwt_token)
        token = await generate_token(user.id, user.username)
        return JsonResponse({'authenticated': True, 'token': token})
        


