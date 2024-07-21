from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from .models import UserActivity, Group, GroupMessage, GroupMember, MessageReadTracking
from .models import GroupJoinRequest, PrivateMessage , PrivateChatRoom
from django.db.models import F
from django.contrib.auth.models import User
from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync


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
def update_group_last_activity(sender, instance: GroupMessage, created, **kwargs):
    channel_layer = get_channel_layer()
    if created:
        async_to_sync(channel_layer.group_send)(
            'homepage_group',
            {
                'type': 'message_count_increased',
                'group_id' : instance.group.id
            }
        )
        instance.group.last_activity = instance.timestamp 
        instance.save()

@receiver(post_save, sender = PrivateChatRoom)
def post_save_privatechatroom(sender, instance: PrivateChatRoom, created , **kwargs):
    if created:
        channel_layer = get_channel_layer()
        async_to_sync(channel_layer.group_send)(
            f'chatslist_user_{instance.member1.id}',
            {
                'type' : 'new_chat_added',
                'chat' : {
                    'id': instance.id,
                    'username' : instance.member2.username,
                    'last_seen' : instance.member2.useractivity.last_activity.isoformat(),
                    'last_activity' : instance.last_activity.isoformat(),
                    'unread_count' : 0
                }
            }
        )
        async_to_sync(channel_layer.group_send)(
            f'chatslist_user_{instance.member2.id}',
            {
                'type' : 'new_chat_added',
                'chat' : {
                    'id': instance.id,
                    'username' : instance.member1.username,
                    'last_seen' : instance.member1.useractivity.last_activity.isoformat(),
                    'last_activity' : instance.last_activity.isoformat(),
                    'unread_count' : 0
                }
            }
        )

@receiver(post_delete, sender = GroupMessage)
def post_delete_GroupMessage(sender, instance , **kwargs):
    channel_layer = get_channel_layer()
    async_to_sync(channel_layer.group_send)(
        'homepage_group',
        {
            'type': 'message_count_decreased',
            'group_id' : instance.group.id
        }
    )

@receiver(post_save, sender = MessageReadTracking)
def update_seen_count(sender, instance: MessageReadTracking, created, **kwargs):
    if created:
        message = instance.message
        message.seen_count = F('seen_count') + 1
        message.save()

@receiver(post_save, sender=GroupMember)
def handle_group_user_save(sender, instance, created, **kwargs):
    # Delete any existing join requests for this user in the group
    GroupJoinRequest.objects.filter(group=instance.group, user=instance.member).delete()
    channel_layer = get_channel_layer()
    if created:
        # A new member was added
        async_to_sync(channel_layer.group_send)(
            f'homepage_user_{instance.member.id}',
            {
                'type' : 'update_status',
                'group_id': instance.group.id,
                'status': 'member'
            }
        )
        async_to_sync(channel_layer.group_send)(
            'homepage_group',
            {
                'type': 'member_count_increased',
                'group_id' : instance.group.id
            }
        )
        member = instance.member
        if instance.is_admin == False:
            async_to_sync(channel_layer.group_send)(
                f'about_group_{instance.group.id}',
                {
                    'type' : 'member_added',
                    'member' : {
                        'id' : member.id,
                        'username' : member.username
                    }
                }
            )
        else:
            async_to_sync(channel_layer.group_send)(
                f'about_group_{instance.group.id}',
                {
                    'type' : 'admin_added',
                    'admin' : {
                        'id' : instance.member.id,
                        'username' : instance.member.username
                    }
                }
            )
    else:
        # existing member was updated
        if instance.is_admin:
            async_to_sync(channel_layer.group_send)(
                f'about_group_{instance.group.id}',
                {
                    'type' : 'admin_added',
                    'admin' : {
                        'id' : instance.member.id,
                        'username' : instance.member.username
                    }
                }
            )
            async_to_sync(channel_layer.group_send)(
            f'about_group_{instance.group.id}',
            {
                'type': 'member_removed',
                'member_id': instance.member.id
            }
        )
        else:
            member_id = instance.member.id
            async_to_sync(channel_layer.group_send)(
                f'about_group_{instance.group.id}',
                {
                    'type': 'admin_removed',
                    'admin_id': member_id
                }
            )
            async_to_sync(channel_layer.group_send)(
                f'about_group_{instance.group.id}',
                {
                    'type' : 'member_added',
                    'member' : {
                        'id' : instance.member.id,
                        'username' : instance.member.username
                    }
                }
            )

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
    channel_layer = get_channel_layer()
    member_id = instance.member.id
    if instance.is_admin:
        async_to_sync(channel_layer.group_send)(
            f'about_group_{instance.group.id}',
            {
                'type': 'admin_removed',
                'admin_id': member_id
            }
        )
    else:
        async_to_sync(channel_layer.group_send)(
            f'about_group_{instance.group.id}',
            {
                'type': 'member_removed',
                'member_id': member_id
            }
        )
    async_to_sync(channel_layer.group_send)(
        f'homepage_user_{instance.member.id}',
        {
            'type' : 'update_status',
            'group_id': instance.group.id,
            'status' : 'not_member'
        }
    )
    async_to_sync(channel_layer.group_send)(
        'homepage_group',
        {
            'type': 'member_count_decreased',
            'group_id' : instance.group.id
        }
    )

@receiver(post_save, sender = PrivateMessage)
def update_private_chat_room_last_activity(sender, instance: PrivateMessage, created, **kwargs):
    if created:
        instance.room.update_last_activity()
        channel_layer = get_channel_layer()
        if instance.sender == instance.room.member2:
            async_to_sync(channel_layer.group_send)(
            f'chatslist_user_{instance.room.member1.id}',
            {
                'type': 'unread_count_incremented',
                'chat_id' : instance.room.id
            }
            )
        else:
            async_to_sync(channel_layer.group_send)(
            f'chatslist_user_{instance.room.member2.id}',
            {
                'type': 'unread_count_incremented',
                'chat_id' : instance.room.id
            }
            )

@receiver(post_save, sender = GroupJoinRequest)
def inform_admin_access_page_about_incoming_request(sender, instance, created, **kwargs):
    if created:
        channel_layer = get_channel_layer()
        async_to_sync(channel_layer.group_send)(
            f'about_group_{instance.group.id}',
            {
                'type' : 'request_added',
                'request_id' : instance.id,
                'user': {
                    'id' : instance.user.id,
                    'username': instance.user.username
                }
            }
        )
        async_to_sync(channel_layer.group_send)(
            f'homepage_user_{instance.user.id}',
            {
                'type' : 'update_status',
                'group_id' : instance.group.id,
                'status' : 'requested'
            }
        )

@receiver(post_delete, sender = GroupJoinRequest)
def inform_admin_access_page_about_removing_request(sender, instance, **kwargs):
    channel_layer = get_channel_layer()
    async_to_sync(channel_layer.group_send)(
        f'about_group_{instance.group.id}',
        {
            'type' : 'request_removed',
            'request_id': instance.id
        }
    )
    if not GroupMember.objects.filter(group = instance.group , member = instance.user).exists():
        async_to_sync(channel_layer.group_send)(
            f'homepage_user_{instance.user.id}',
            {
                'type' : 'update_status',
                'group_id' : instance.group.id,
                'status' : 'not_member'
            }
        )