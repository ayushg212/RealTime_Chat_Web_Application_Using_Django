from django.urls import path,include
from .views import home_view, private_chat_view,group_chat_view,about_group_view,admin_access_view,private_chats_list_view

urlpatterns = [
    path('', home_view, name= 'home'),
    path('private_chats/', private_chats_list_view, name = 'private_chats_list'),
    path('private_chat/<str:chat_username>/', private_chat_view, name = 'private_chat'),
    path('group/<int:group_id>/chat/', group_chat_view, name='group_chat' ),
    path('group/<int:group_id>/about/',about_group_view , name= 'about_group' ),
    path('group/<int:group_id>/admin/',admin_access_view, name= 'admin_access'),
]
