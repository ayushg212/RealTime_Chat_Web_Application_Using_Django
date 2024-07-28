from django.shortcuts import render, get_object_or_404 , redirect
from django.contrib.auth.decorators import login_required
from django.http import Http404
from django.db.models import Q,Count,OuterRef, Subquery
from django.contrib.auth.models import User
from django.utils import timezone
from .models import  ChatGroup, GroupMember, GroupJoinRequest,PrivateChatRoom,GroupMessage
from .models import MessageReadTracking , UserActivity
from .forms import ChatGroupForm

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
    grp_obj = get_object_or_404(ChatGroup, id = group_id)
    grp_member_obj = get_object_or_404(GroupMember, group = grp_obj , member = user)
    context = {
        'group' : grp_obj,
        'is_admin' : grp_member_obj.is_admin
    }
    return render(request, 'chatapp\\group_chat.html', context )


@login_required
def about_group_view(request, group_id):
    group = get_object_or_404(ChatGroup, id = group_id)
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
    group = get_object_or_404(ChatGroup, id = group_id)
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
        return "Just Now"
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
            return f"{value} {name}{'s' if value >= 1 else ''} ago"
    return "Just Now"


@login_required
def create_group_view(request):
    if request.method == 'POST':
        form = ChatGroupForm(request.POST)
        if form.is_valid():
            group = form.save(commit=False)
            group.creator = request.user
            group.save()
            return redirect('group_chat', group_id=group.id)
    else:
        form = ChatGroupForm()
    return render(request, 'chatapp\\create_group.html', {'form': form})


@login_required
def group_chats_list_view(request):
    groups = ChatGroup.objects.filter(groupmember__member=request.user)
    context = []
    for group in groups:
        obj = get_object_or_404(GroupMember, group = group , member = request.user)
        count = group.msg_count - obj.seen_count - obj.msg_send_count
        context.append(
            {
                'id' : group.id,
                'name' : group.name,
                'description' : group.description,
                'last_activity': group.last_activity.isoformat(),
                'last_activity_human' : time_ago(group.last_activity),
                'unread_count' : count
            }
        )
    return render(request, 'chatapp\\group_chats_list.html', {'groups': context})


@login_required
def pending_requests_view(request):
    pending_requests = GroupJoinRequest.objects.filter(user=request.user)
    return render(request, 'chatapp\\pending_requests.html', {'pending_requests': pending_requests})

@login_required
def messaage_seen_detail_view(request, message_id):
    message = get_object_or_404(GroupMessage, id=message_id)
    group = message.group
    
    if not GroupMember.objects.filter(group=group, member=request.user).exists():
        raise Http404("You are not a member of this group.")
    
    seen_users = MessageReadTracking.objects.filter(message=message)
    return render(request, 'chatapp\\message_seen_detail.html', {
        'message': message,
        'seen_users': seen_users,
    })

@login_required
def user_profile_view(request, user_id):
    user = get_object_or_404(User, id=user_id)

    user_activity = get_object_or_404(UserActivity, user=user)
    created_groups = ChatGroup.objects.filter(creator=user)
    member_groups = GroupMember.objects.filter(member=user).values_list('group', flat=True)
    member_groups = ChatGroup.objects.filter(id__in=member_groups)

    return render(request, 'chatapp\\user_profile.html', {
        'profile_user': user,
        'last_activity': user_activity.last_activity.isoformat(),
        'last_seen_human': time_ago(user_activity.last_activity),
        'created_groups': created_groups,
        'member_groups': member_groups,
    })

@login_required
def about_view(request):
    return render(request, 'chatapp\\about.html')