from django.db import models
from django.contrib.auth.models import AbstractUser

# Create your models here.

class CustomUser(AbstractUser):
    image = models.ImageField(upload_to='profile_pictures', default='/profile_pictures/default_profile.jpg')  


class FriendRequest(models.Model):
    from_user = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name="req_sender")
    to_user = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name="req_receiver")
    accepted = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    is_read = models.BooleanField(default=False)


class ChatMsg(models.Model):
    sender = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name="msg_sender")
    receiver = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name="msg_receiver")
    message = models.TextField()
    time_stamp = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return str(self.sender)


class Group(models.Model):
    name = models.CharField(max_length=500)
    group_image = models.ImageField(upload_to='profile_pictures', default='/profile_pictures/default_profile.jpg')
    admin = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name="group_admin")
    members = models.ManyToManyField(CustomUser, related_name="group_members")
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name


class GroupRequests(models.Model):
    group = models.ForeignKey(Group, on_delete=models.CASCADE)
    requested_user = models.ForeignKey(CustomUser, on_delete=models.CASCADE)
    accepted = models.BooleanField(default=False)
    time_stamp = models.DateTimeField(auto_now_add=True)


class GroupChat(models.Model):
    group = models.ForeignKey(Group, on_delete=models.CASCADE)
    sender = models.ForeignKey(CustomUser, on_delete=models.CASCADE)
    message = models.TextField()
    time_stamp = models.DateTimeField(auto_now_add=True) 

