from django.urls import path
from .consumers import PrivateChatConsumer, GroupChatConsumer, AboutGroupConsumer
from .consumers import OnlineGroupUsersConsumer, UserOnlineStatusUpdateConsumer, AdminAccessConsumer
from .consumers import UserConsumer, GroupConsumer, OnlineUserConsumer,PrivateChatsListConsumer


websocket_urlpatterns = [
    path('ws/private_chat/<str:username>/', PrivateChatConsumer.as_asgi()),
    path('ws/group/<int:room_no>/chat/', GroupChatConsumer.as_asgi()),
    path('ws/group/<int:room_no>/online_members/', OnlineGroupUsersConsumer.as_asgi() ),
    path('ws/group/<int:group_id>/about/', AboutGroupConsumer.as_asgi() ),
    path('ws/group/<int:group_id>/admin/', AdminAccessConsumer.as_asgi() ),
    path("ws/imonline/",UserOnlineStatusUpdateConsumer.as_asgi() ),
    path('ws/home/users/', UserConsumer.as_asgi()),
    path('ws/home/groups/', GroupConsumer.as_asgi()),
    path('ws/home/online_users/', OnlineUserConsumer.as_asgi()),
    path('ws/private_chats/', PrivateChatsListConsumer.as_asgi()),
]