from django.shortcuts import render, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.http import Http404
from django.db.models import Q
from django.contrib.auth.models import User
from django.utils import timezone
from .models import  Group, GroupMember, GroupJoinRequest,PrivateChatRoom

# Create your views here.
@login_required
def home_view(request):
    return render(request, 'chatapp\\home.html')


@login_required
def private_chat_view(request, chat_username):
    user = request.user
    if user.username == chat_username:
        raise Http404("Page not found.")
    chat_user = get_object_or_404(User, username = chat_username )
    context = {
         'chat_user' : chat_user,
    }
    return render(request, 'chatapp\\private_chat.html', context)


@login_required
def group_chat_view(request, group_id):
    user = request.user
    grp_obj = get_object_or_404(Group, id = group_id)
    grp_member_obj = get_object_or_404(GroupMember, group = grp_obj , member = user)
    context = {
        'group' : grp_obj,
        'is_admin' : grp_member_obj.is_admin
    }
    return render(request, 'chatapp\\group_chat.html', context )


@login_required
def about_group_view(request, group_id):
    group = get_object_or_404(Group, id = group_id)
    creator = group.creator
    admins = GroupMember.objects.filter(group = group, is_admin = True)
    members = GroupMember.objects.filter(group = group, is_admin = False)
    context = {
        'group' : group,
        'creator' : creator,
        'admins' : [admin.member for admin in admins],
        'members' : [member.member for member in members]
    }
    return render(request, 'chatapp\\about_group.html' , context)

@login_required
def admin_access_view(request, group_id):
    group = get_object_or_404(Group, id = group_id)
    grp_member_obj = get_object_or_404(GroupMember, group=group, member=request.user, is_admin = True)
    admins = GroupMember.objects.filter(group = group, is_admin = True)
    members = GroupMember.objects.filter(group= group, is_admin = False)
    join_requests = GroupJoinRequest.objects.filter(group= group)
    context = {
        'group': group,
        'admins': [admin.member for admin in admins],
        'members': [member.member for member in members],
        'join_requests': join_requests,

    }
    return render(request, 'chatapp\\admin_access.html', context)

@login_required
def private_chats_list_view(request):
    chat_rooms = PrivateChatRoom.objects.filter(Q(member1=request.user) | Q(member2=request.user)).order_by('-last_activity')
    chat_data = []
    for chat in chat_rooms:
        last_seen = chat.get_other_user(request.user).useractivity.last_activity
        chat_data.append(
            {
                'id': chat.id,
                'username': chat.get_other_user(request.user).username,
                'last_seen': last_seen.isoformat(),
                'last_seen_human' : time_ago(last_seen),
                'unread_count': chat.get_unread_messages_count(request.user),
                'last_activity': chat.last_activity.isoformat()
            }
        )
    context = {
        'chat_rooms' : chat_data
    }
    return render(request, 'chatapp\\private_chats_list.html',context)

def time_ago(time):
    now = timezone.now()
    seconds = int((now - time).total_seconds())
    if seconds < 60:
        return "Online"
    intervals = (
        ('year', 31536000),
        ('month', 2592000),
        ('day', 86400),
        ('hour', 3600),
        ('minute', 60),
    )
    for name, count in intervals:
        value = seconds // count
        if value:
            return f"{value} {name}{'s' if value > 1 else ''} ago"
    return "Online"