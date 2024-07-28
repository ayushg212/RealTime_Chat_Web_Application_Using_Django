from django.urls import path,include
from .views import home_view, private_chat_view,group_chat_view , create_group_view, pending_requests_view
from .views import about_group_view,admin_access_view,private_chats_list_view , group_chats_list_view
from .views import messaage_seen_detail_view, user_profile_view, about_view

urlpatterns = [
    path('', home_view, name= 'home'),
    path('private_chats/', private_chats_list_view, name = 'private_chats_list'),
    path('private_chat/<str:chat_username>/', private_chat_view, name = 'private_chat'),
    path('group/<int:group_id>/chat/', group_chat_view, name='group_chat' ),
    path('group/<int:group_id>/about/',about_group_view , name= 'about_group' ),
    path('group/<int:group_id>/admin/',admin_access_view, name= 'admin_access'),
    path('create_group/', create_group_view, name='create_group'),
    path('group_chats/', group_chats_list_view, name='group_chats_list'),
    path('pending_requests/', pending_requests_view, name='pending_requests'),
    path('message/<int:message_id>/', messaage_seen_detail_view, name='message_seen_details'),
    path('profile/<int:user_id>/', user_profile_view , name='user_profile_view'),
    path('about/', about_view, name='about'),
]
