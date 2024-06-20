from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from .models import UserActivity,Group, GroupMessage, GroupMember, MessageReadTracking, GroupJoinRequest
from django.contrib.auth.models import User


@receiver(post_save, sender = User)
def create_or_update_user_activity(sender, instance , created, **kwargs):
    if created:
        obj =UserActivity.objects.create(user = instance)
        obj.save()

@receiver(post_save, sender=Group)
def ensure_creator_is_admin_and_member(sender, instance, created, **kwargs):
    if created:
        obj = GroupMember.objects.create(group = instance, member = instance.creator , is_admin = True)
        obj.save()


@receiver(post_save, sender=GroupMessage)
def ensure_grup_msg_is_read_by_sender(sender, instance, created, **kwargs):
    if created:
        obj = MessageReadTracking.objects.create(message = instance, read_by_user = instance.sender) 
        obj.save()

@receiver(post_save, sender=GroupMember)
def handle_group_user_save(sender, instance, **kwargs):
    # Delete any existing join requests for this user in the group
    GroupJoinRequest.objects.filter(group=instance.group, user=instance.member).delete()

@receiver(post_delete, sender=GroupMember)
def handle_group_user_delete(sender, instance, **kwargs):
    try:
        # Check if the group exists before proceeding
        group = instance.group
        if group:
            # Check if the group has no members left and delete the group if true
            group.check_and_delete_if_empty()
    except Group.DoesNotExist:
        # The group has already been deleted; no further action needed
        pass
