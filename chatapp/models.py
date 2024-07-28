from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
from django.core.exceptions import ValidationError
from datetime import timedelta
from django.conf import settings
from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync
import random

# Create your models here.

def prob_func_give_10_percent_true():
    return random.random() < 0.2

class UserActivity(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    last_activity = models.DateTimeField(default=timezone.now)

    def __str__(self):
        return f'{self.user.username} - Last activity: {self.last_activity}'

    def update_activity(self):
        self.last_activity = timezone.now()
        self.save()
        if prob_func_give_10_percent_true():
            channel_layer = get_channel_layer()
            async_to_sync(channel_layer.group_send)(
                'homepage_user',
                {
                    'type' : 'last_seen_updated',
                    'user_id' : self.user.id,
                    'last_seen' : self.last_activity.isoformat()
                }
            )
            async_to_sync(channel_layer.group_send)(
                'chatslist',
                {
                    'type' : 'last_seen_updated',
                    'chat_username' : self.user.username,
                    'last_seen' : self.last_activity.isoformat()
                }
            )


    def get_online_users(self):
        time_threshold = timezone.now() - timedelta(seconds = settings.ONLINE_USERS_TIME_DELTA)
        return User.objects.filter( useractivity__last_activity__gte = time_threshold )


class ChatGroup(models.Model):
    creator = models.ForeignKey(User, on_delete=models.CASCADE, related_name='created_groups')
    created_at = models.DateTimeField(auto_now_add=True)
    last_activity = models.DateTimeField(default=timezone.now)
    name = models.CharField(max_length=50, unique=True)
    description = models.TextField(blank=True)
    msg_count = models.IntegerField(default=0)

    def update_last_activity(self):
        self.last_activity = timezone.now()
        self.save()

    def get_online_members(self):
        time_threshold = timezone.now() - timedelta(seconds = settings.ONLINE_USERS_TIME_DELTA)
        online_members = User.objects.filter(
            groupmember__group = self,
            useractivity__last_activity__gte = time_threshold
        )
        return online_members

    def add_member(self, user):
        GroupMember.objects.create(group=self, member=user)

    def remove_member(self, user):
        GroupMember.objects.filter(group=self, member=user).delete()

    def add_admin(self, user):
        group_user, created = GroupMember.objects.get_or_create(group=self, member=user)
        group_user.is_admin = True
        group_user.save()

    def remove_admin(self, user):
        group_user = GroupMember.objects.get(group=self, member=user)
        group_user.is_admin = False
        group_user.save()

    def check_and_delete_if_empty(self):
        if not self.groupmember_set.exists():
            self.delete()

    def __str__(self):
        return self.name
    
        
class GroupMessage(models.Model):
    sender = models.ForeignKey(User, on_delete=models.CASCADE, related_name='group_messages_sent')
    group = models.ForeignKey(ChatGroup, on_delete=models.CASCADE, related_name='messages')
    content = models.TextField()
    timestamp = models.DateTimeField(auto_now_add=True)
    seen_count = models.IntegerField(default=0)

    def clean(self):
        if not GroupMember.objects.filter(group=self.group, member=self.sender ).exists():
            raise ValidationError(f"Sender {self.sender.username} is not the membr of the group {self.group.name}")
        
    def save(self, *args, **kwargs):
        self.clean()
        super().save(*args, **kwargs)

    def __str__(self):
        return f'Message from {self.sender.username} in {self.group.name} at {self.timestamp}'
    
    
class MessageReadTracking(models.Model):
    group = models.ForeignKey(ChatGroup, on_delete = models.CASCADE)
    message = models.ForeignKey(GroupMessage, on_delete=models.CASCADE, related_name="readers")
    read_by_user = models.ForeignKey(User, on_delete = models.CASCADE)
    timestamp = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('message', 'read_by_user')

    def clean(self):
        if not GroupMember.objects.filter(group = self.group, member = self.read_by_user).exists():
            raise ValidationError(f"User {self.read_by_user.username} is not the member of the group {self.message.group.name} and cannot read this message")
        if self.read_by_user == self.message.sender:
            raise ValidationError('Sender can\'t be part of the read_user')
        
    def save(self, *args, **kwargs):
        self.clean()
        super().save(*args, **kwargs)

    
    
class GroupMember(models.Model):
    group = models.ForeignKey(ChatGroup, on_delete= models.CASCADE)
    member = models.ForeignKey(User, on_delete= models.CASCADE)
    is_admin = models.BooleanField(default=False)
    seen_count = models.IntegerField(default=0)
    msg_send_count = models.IntegerField(default=0)

    class Meta:
        unique_together = ('group', 'member')

    def __str__(self):
        return f'{self.member.username} in {self.group.name}'
    

class GroupJoinRequest(models.Model):
    group = models.ForeignKey(ChatGroup, on_delete=models.CASCADE, related_name='join_requests')
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='join_requests')
    timestamp = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('group', 'user')

    def clean(self):
        if GroupMember.objects.filter(group=self.group, member=self.user).exists():
            raise ValidationError(f'User {self.user.username} is already a member of the group {self.group.name}.')

    def save(self, *args, **kwargs):
        self.clean()
        super().save(*args, **kwargs)

    def accept(self):
        if not GroupMember.objects.filter(group=self.group, member=self.user).exists():
            GroupMember.objects.create(group=self.group, member=self.user)
        self.delete()

    def reject(self):
        self.delete()

    def __str__(self):
        return f'Request by {self.user.username} to join {self.group.name}'


class PrivateChatRoom(models.Model):
    member1 = models.ForeignKey(User, on_delete = models.CASCADE, related_name='private_chat_member1')
    member2 = models.ForeignKey(User, on_delete = models.CASCADE, related_name='private_chat_member2')
    last_activity = models.DateTimeField(default=timezone.now)
    room_name = models.CharField(max_length=255, unique=True, blank=True)

    def update_last_activity(self):
        self.last_activity = timezone.now()
        self.save()
        channel_layer = get_channel_layer()
        async_to_sync(channel_layer.group_send)(
            f'chatslist_user_{self.member1.id}',
            {
                'type' : 'last_activity_updated',
                'chat_id': self.id,
                'last_activity': self.last_activity.isoformat(),
            }
        )
        async_to_sync(channel_layer.group_send)(
            f'chatslist_user_{self.member2.id}',
            {
                'type' : 'last_activity_updated',
                'chat_id': self.id,
                'last_activity': self.last_activity.isoformat(),
            }
        )

    def save(self, *args, **kwargs):
        if self.member1.username > self.member2.username:
            self.member1, self.member2 = self.member2, self.member1
        self.room_name = f'{self.member1.username}_{self.member2.username}'
        super().save(*args, **kwargs)

    def get_other_user(self, user: User):
        if self.member1 == user:
            return self.member2
        elif self.member2 == user:
            return self.member1
        return None
    
    def get_unread_messages_count(self , user: User):
        other_user = self.get_other_user(user)
        return PrivateMessage.objects.filter(room = self, sender = other_user , read = False ).count()
    
    def __str__(self):
        return f'PrivateChatRoom: {self.room_name}'
    

class PrivateMessage(models.Model):
    sender = models.ForeignKey(User, on_delete=models.CASCADE, related_name='sent_messages')
    room = models.ForeignKey(PrivateChatRoom, on_delete=models.CASCADE, related_name= 'messages')
    content = models.TextField()
    timestamp = models.DateTimeField(auto_now_add=True)
    read = models.BooleanField(default=False)
    read_time = models.DateTimeField(blank=True,null=True)

    def clean(self):
        if self.sender.id not in [self.room.member1.id, self.room.member2.id]:
            raise ValidationError(f'{self.sender.username} doesn\'t belong to room {self.room.room_name}')
    
    def save(self, *args, **kwargs):
        self.clean()
        super().save(*args, **kwargs)

    def __str__(self):
        return f'From: {self.sender.username} in {self.room.room_name} at {self.timestamp}'