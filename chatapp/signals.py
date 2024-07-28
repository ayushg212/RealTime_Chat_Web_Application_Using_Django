from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from .models import UserActivity, ChatGroup, GroupMessage, GroupMember, MessageReadTracking
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

@receiver(post_save, sender=ChatGroup)
def ensure_creator_is_admin_and_member(sender, instance, created, **kwargs):
    if created:
        obj = GroupMember.objects.create(group = instance, member = instance.creator , is_admin = True)
        obj.save()
        channel_layer = get_channel_layer()
        async_to_sync(channel_layer.group_send)(
            f'profile_{instance.creator.id}',
            {
                'type': 'group_added',
                'group': {
                    'id': instance.id,
                    'name': instance.name,
                },
                'list_type': 'created'
            }
        )

@receiver(post_save, sender=GroupMessage)
def update_group_last_activity(sender, instance: GroupMessage, created, **kwargs):
    channel_layer = get_channel_layer()
    if created:
        instance.group.last_activity = instance.timestamp 
        instance.save()
        group = instance.group
        group.msg_count = F('msg_count') + 1
        group.save()
        group_member = GroupMember.objects.get(group = instance.group , member = instance.sender)
        group_member.msg_send_count = F('msg_send_count') + 1
        group_member.save()
        async_to_sync(channel_layer.group_send)(
            'homepage_group',
            {
                'type': 'message_count_increased',
                'group_id' : instance.group.id
            }
        )
        async_to_sync(channel_layer.group_send)(
            "group_chats_list",
            {
                'type': 'unread_count_incremented',
                'group_id': instance.group.id
            }
        )
        async_to_sync(channel_layer.group_send)(
            "group_chats_list",
            {
                'type': 'last_activity_updated',
                'group_id': instance.group.id,
                'last_activity': group.last_activity.isoformat()
            }
        )

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
def post_delete_GroupMessage(sender, instance: GroupMessage , **kwargs):
    try:
        group = instance.group
        group.msg_count = F('msg_count') - 1
        group.save()
        group_member = GroupMember.objects.get(group = instance.group , member = instance.sender)
        group_member.msg_send_count = F('msg_send_count') - 1
        group_member.save()
    except Exception as e:
        print(e)
    try:
        channel_layer = get_channel_layer()
        async_to_sync(channel_layer.group_send)(
            'homepage_group',
            {
                'type': 'message_count_decreased',
                'group_id' : instance.group.id
            }
        )
    except Exception as e:
        print(e)

@receiver(post_save, sender = MessageReadTracking)
def post_save_message_read_tracking(sender, instance: MessageReadTracking, created, **kwargs):
    if created:
        message = instance.message
        message.seen_count = F('seen_count') + 1
        message.save()
        grp_member_obj = GroupMember.objects.get(group = instance.group , member = instance.read_by_user)
        grp_member_obj.seen_count = F('seen_count') + 1
        grp_member_obj.save()
        channel_layer = get_channel_layer()
        async_to_sync(channel_layer.group_send)(
            f'seen_message_{instance.message.id}',
            {
                'type': 'seen_update',
                'username': instance.read_by_user.username,
                'timestamp': instance.timestamp.isoformat()
            }
        )


@receiver(post_delete, sender = MessageReadTracking)
def post_delete_message_read_tracking(sender, instance: MessageReadTracking, **kwargs):
    try:
        message = instance.message
        message.seen_count = F('seen_count') - 1
        message.save()
        grp_member_obj = GroupMember.objects.get(group = instance.group , member = instance.read_by_user)
        grp_member_obj.seen_count = F('seen_count') - 1
        grp_member_obj.save()
    except Exception as e:
        print(e)


@receiver(post_save, sender=GroupMember)
def handle_group_user_save(sender, instance: GroupMember, created, **kwargs):
    # Delete any existing join requests for this user in the group
    GroupJoinRequest.objects.filter(group=instance.group, user=instance.member).delete()
    channel_layer = get_channel_layer()
    if created:
        # A new member was added
        instance.seen_count = MessageReadTracking.objects.filter(group = instance.group, read_by_user = instance.member).count()
        instance.msg_send_count = GroupMessage.objects.filter(group = instance.group , sender = instance.member).count()
        instance.save()
        async_to_sync(channel_layer.group_send)(
            f'profile_{instance.member.id}',
            {
                'type': 'group_added',
                'group': {
                    'id': instance.group.id,
                    'name': instance.group.name,
                },
                'list_type': 'member'
            }
        )
        async_to_sync(channel_layer.group_send)(
            f"group_chats_list_user{instance.member.id}",
            {
                'type': 'group_member_added',
                'group': {
                    'id': instance.group.id,
                    'name': instance.group.name,
                    'description': instance.group.description,
                    'last_activity': instance.group.last_activity.isoformat(),
                    'unread_count': instance.group.msg_count - instance.seen_count - instance.msg_send_count
                }
            }
        )
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
def handle_group_user_delete(sender, instance: GroupMember, **kwargs):
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
        f'profile_{instance.member.id}',
        {
            'type': 'group_removed',
            'group_id': instance.group.id,
            'list_type': 'member'
        }
    )
    async_to_sync(channel_layer.group_send)(
            f"group_chats_list_user{instance.member.id}",
            {
                'type': 'group_member_removed',
                'group_id': instance.group.id
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
def post_save_group_join_request(sender, instance, created, **kwargs):
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
        group_data = {
            'id': instance.group.id,
            'name': instance.group.name,
            'description': instance.group.description,
            'creator': instance.group.creator.username
        }
        async_to_sync(channel_layer.group_send)(
            f'pending_requests_{instance.user.id}',
            {
                'type': 'request_added',
                'request_id': instance.id,
                'group': group_data
            }
        )

@receiver(post_delete, sender=GroupJoinRequest)
def post_delete_group_join_request(sender, instance, **kwargs):
    try:
        channel_layer = get_channel_layer()
        async_to_sync(channel_layer.group_send)(
            f'about_group_{instance.group.id}',
            {
                'type': 'request_removed',
                'request_id': instance.id
            }
        )
        if not GroupMember.objects.filter(group=instance.group, member=instance.user).exists():
            async_to_sync(channel_layer.group_send)(
                f'homepage_user_{instance.user.id}',
                {
                    'type': 'update_status',
                    'group_id': instance.group.id,
                    'status': 'not_member'
                }
            )
        async_to_sync(channel_layer.group_send)(
            f'pending_requests_{instance.user.id}',
            {
                'type': 'request_removed',
                'request_id': instance.id
            }
        )
    except Exception as e:
        print(e)


@receiver(post_delete, sender=ChatGroup)
def remove_created_group(sender, instance, **kwargs):
    channel_layer = get_channel_layer()
    async_to_sync(channel_layer.group_send)(
        f'profile_{instance.creator.id}',
        {
            'type': 'group_removed',
            'group_id': instance.id,
            'list_type': 'created'
        }
    )