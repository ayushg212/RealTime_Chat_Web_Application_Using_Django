from django.contrib import admin
from .models import UserActivity, Group, GroupMessage
from .models import PrivateMessage,GroupMember, MessageReadTracking, GroupJoinRequest
from django.core.exceptions import ValidationError

# Register your models here.

# Admin registrations
@admin.register(UserActivity)
class UserActivityAdmin(admin.ModelAdmin):
    list_display = ('user', 'last_activity')
    search_fields = ('user__username',)

@admin.register(Group)
class GroupAdmin(admin.ModelAdmin):
    list_display = ('name', 'creator')
    search_fields = ('name', 'creator__username')

@admin.register(GroupMember)
class GroupUserAdmin(admin.ModelAdmin):
    list_display = ('group', 'member', 'is_admin')
    search_fields = ('group__name', 'member__username')

@admin.register(GroupMessage)
class GroupMessageAdmin(admin.ModelAdmin):
    list_display = ('sender', 'group', 'timestamp')
    search_fields = ('sender__username', 'group__name')

@admin.register(MessageReadTracking)
class MessageReadTrackingAdmin(admin.ModelAdmin):
    list_display = ('message', 'read_by_user', 'timestamp')
    search_fields = ('message__content', 'read_by_user__username')

@admin.register(PrivateMessage)
class PrivateMessageAdmin(admin.ModelAdmin):
    list_display = ('sender', 'receiver', 'timestamp', 'read')
    search_fields = ('sender__username', 'receiver__username', 'content')

@admin.register(GroupJoinRequest)
class GroupJoinRequestAdmin(admin.ModelAdmin):
    list_display = ('group', 'user', 'timestamp')
    search_fields = ('group__name', 'user__username')
    actions = ['accept_requests', 'reject_requests']

    def accept_requests(self, request, queryset):
        for join_request in queryset:
            try:
                join_request.accept()
            except ValidationError as e:
                self.message_user(request, str(e), level='error')
    accept_requests.short_description = 'Accept selected join requests'

    def reject_requests(self, request, queryset):
        for join_request in queryset:
            join_request.reject()
    reject_requests.short_description = 'Reject selected join requests'