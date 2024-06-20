from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
from django.contrib import admin
from django.core.exceptions import ValidationError

# Create your models here.


class UserActivity(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    last_activity = models.DateTimeField(default=timezone.now)

    def __str__(self):
        return f'{self.user.username} - Last activity: {self.last_activity}'

    def update_activity(self):
        self.last_activity = timezone.now()
        self.save()
    
        
class GroupMessage(models.Model):
    sender = models.ForeignKey(User, on_delete=models.CASCADE, related_name='group_messages_sent')
    group = models.ForeignKey('Group', on_delete=models.CASCADE, related_name='messages')
    content = models.TextField()
    timestamp = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f'Message from {self.sender.username} in {self.group.name} at {self.timestamp}'
    
    
class MessageReadTracking(models.Model):
    message = models.ForeignKey(GroupMessage, on_delete=models.CASCADE)
    read_by_user = models.ForeignKey(User, on_delete = models.CASCADE)
    timestamp = models.DateTimeField(auto_now_add=True)


class PrivateMessage(models.Model):
    sender = models.ForeignKey(User, on_delete=models.CASCADE, related_name='sent_messages')
    receiver = models.ForeignKey(User, on_delete=models.CASCADE, related_name='received_messages')
    content = models.TextField()
    timestamp = models.DateTimeField(auto_now_add=True)
    read = models.BooleanField(default=False)

    def __str__(self):
        return f'From: {self.sender.username} To: {self.receiver.username} at {self.timestamp}'
    

class Group(models.Model):
    creator = models.ForeignKey(User, on_delete=models.CASCADE, related_name='created_groups')
    name = models.CharField(max_length=50, unique=True)
    description = models.TextField(blank=True)

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
    

class GroupMember(models.Model):
    group = models.ForeignKey(Group, on_delete= models.CASCADE)
    member = models.ForeignKey(User, on_delete= models.CASCADE)
    is_admin = models.BooleanField(default=False)

    class Meta:
        unique_together = ('group', 'member')

    def __str__(self):
        return f'{self.member.username} in {self.group.name}'
    

class GroupJoinRequest(models.Model):
    group = models.ForeignKey(Group, on_delete=models.CASCADE, related_name='join_requests')
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


