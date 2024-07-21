from channels.generic.websocket import AsyncJsonWebsocketConsumer
from channels.db import database_sync_to_async
from .models import PrivateMessage, Group, GroupMessage, MessageReadTracking
from .models import PrivateChatRoom, GroupJoinRequest, GroupMember, UserActivity
from django.contrib.auth.models import User
from django.utils import timezone
from datetime import timedelta
from django.conf import settings
from django.db.models import Q
import asyncio

# in seconds
last_activity_update_interval = 2
online_user_send_interval = 5


class PrivateChatConsumer(AsyncJsonWebsocketConsumer):
    async def connect(self):
        print("PrivateChatConsumer: Browser is trying to connect.....")
        self.user = self.scope["user"]
        self.chat_user_username = self.scope['url_route']['kwargs']['username']
        if self.user.is_anonymous:
            await self.close()
        elif self.user.username == self.chat_user_username:
            await self.close()
        else:
            self.chat_user = await self.get_user(self.chat_user_username)
            self.room_obj = await self.get_private_chat_room_object(self.user,self.chat_user)
            self.room_name = f'private_chat_{self.room_obj.id}'
            await self.channel_layer.group_add(
                self.room_name,
                self.channel_name
            )
            await self.accept()
            print("PrivateChatConsumer : Connected ........ USER: " , self.user.username)
            # Send unread messages
            previous_messages = await self.get_previous_messages()   
            await self.send_json({
                'type' : 'previous_messages',
                'messages' : previous_messages
            })
            print("PrivateChatConsumer: Unread message sent to" , self.chat_user_username)
    
    async def disconnect(self, code):
        # leave room group
        print("DIsonnected to consumer" , self.user.username, code)
        await self.channel_layer.group_discard(
            self.room_name,
            self.channel_name
        )

    async def receive_json(self, content):
        print("PrivateChatConsumer: GOT message from ",self.user.username, content)
        type = content.get('type')
        if type == 'incoming_message':
            message = content.get('message')
            if message:
                msg_obj = await self.save_message(self.user, message)
                msg_dict = {
                    'id' : msg_obj.id,
                    'room_name' : msg_obj.room.room_name,
                    'content' : message,
                    'timestamp' : msg_obj.timestamp.isoformat(),
                    'sender' : self.user.username,
                    'read' : False,
                    'read_time' : None
                }
                await self.channel_layer.group_send(
                    self.room_name,
                    {
                        'type' : 'chat_message',
                        'message' : msg_dict
                    }
                )
        elif type == 'seen_confirmation':
            seen_message_id = content.get('seen_message_id')
            if seen_message_id:
                to_broadcast, read_time = await self.is_mark_as_read(seen_message_id)
                if to_broadcast:
                    await self.broadcast_msg_seen_confirmation(seen_message_id, read_time)

    async def broadcast_msg_seen_confirmation(self, message_id, read_time):
        print("PrivateChatConsumer : Broadcasting Confirmation message,message_id : ", message_id)
        await self.channel_layer.group_send(
            self.room_name,
            {
                'type' : 'seen_confirmation',
                'message_id' : message_id,
                'read_time' : read_time.isoformat()
            }
        )

    async def chat_message(self, message):
        print("PrivateChatConsumer: INSIDE chat_message, message : \n",message)
        await self.send_json(message)

    async def seen_confirmation(self, message):
        print("PrivateChatConsumer: INSIDE SEEN_CONFIRMATION, message : \n",message)
        await self.send_json(message)
        
    @database_sync_to_async
    def get_user(self, username):
        return User.objects.get(username = username)

    @database_sync_to_async
    def save_message(self, sender, message):
        return PrivateMessage.objects.create(
            sender= sender, 
            room = self.room_obj, 
            content = message, 
            read = False
         )
    
    @database_sync_to_async
    def is_mark_as_read(self, message_id):
        msg_obj =  PrivateMessage.objects.get(id = message_id)
        if msg_obj.sender != self.user:
            msg_obj.read = True
            msg_obj.read_time = timezone.now()
            msg_obj.save()
            return (True, msg_obj.read_time)
        return (False, None)

    @database_sync_to_async
    def get_previous_messages(self):
        messages = PrivateMessage.objects.filter(
            room = self.room_obj, 
        ).order_by('timestamp')
        message_list = []
        for msg in messages:
            if msg.read == False:
                read_time = None
            else: 
                read_time = msg.read_time.isoformat()
            message_list.append(
                {
                    'id' : msg.id,
                    'sender' : msg.sender.username,
                    'room_name' : msg.room.room_name,
                    'content' : msg.content,
                    'timestamp' : msg.timestamp.isoformat(),
                    'read' : msg.read,
                    'read_time' : read_time
                }
            )
        return message_list
        
    @database_sync_to_async
    def get_private_chat_room_object(self, user1, user2):
        member1, member2 = sorted([user1, user2], key = lambda u: u.username)
        room, created = PrivateChatRoom.objects.get_or_create(member1=member1, member2 = member2)
        return room


class GroupChatConsumer(AsyncJsonWebsocketConsumer):
    async def connect(self):
        print("GroupChatConsumer : Brower Trying to connect...........")
        self.user = self.scope['user']
        if self.user.is_anonymous :
            await self.close()
            return
        self.group_id = self.scope['url_route']['kwargs']['room_no']
        self.group_obj = await self.get_group_obj()
        if self.group_obj == None:
            await self.close()
            return
        self.is_group_member = await self.user_is_group_member()
        if not self.is_group_member:
            await self.close()
            return
        # Now all is ok we can accept the connection
        self.room_name = f'room_chat_{self.group_id}'
        await self.accept()
        await self.channel_layer.group_add(
            self.room_name,
            self.channel_name
        )
        print("GroupChatConsumer: CONNECTED ........... USER: ", self.user.username)
        previous_messages = await self.get_previous_messages()
        print(previous_messages)
        await self.send_json({
            'type' : 'previous_messages',
            'messages' : previous_messages
        })
    
    async def disconnect(self, code):
        print("GroupChatConsumer: SOCKET CONNECTION DISSCONNECTED..........USER : ", self.user.username)
        await self.channel_layer.group_discard(
            self.room_name,
            self.channel_name
        )

    async def receive_json(self, content):
        print("GroupChatConsumer: GOT MESSAGE FROM.......... USER : ", self.user.username, "content : " , content )
        type = content.get('type')
        if type == 'incoming_message':
            message = content.get('message')
            if message:
                msg_obj = await self.save_message(self.user, message)
                msg_dict = {
                    'id' : msg_obj.id,
                    'sender' : msg_obj.sender.username,
                    'content' : msg_obj.content,
                    'timestamp' : msg_obj.timestamp.isoformat(),
                    'seen_count' : msg_obj.seen_count
                }
                await self.channel_layer.group_send(
                    self.room_name,
                    {
                        'type' : 'chat_message',
                        'message' : msg_dict
                    }
                )
        elif type == 'seen_confirmation':
            seen_message_id = content.get('seen_message_id')
            print("GroupChatConsumer: RECEIVED SEEN CONFIRMAITION......... seen_msg_id" , seen_message_id)
            if seen_message_id:
                to_broadcast,dict = await self.to_broadcast_and_get_dict_to_send(seen_message_id)
                if to_broadcast:
                    await self.channel_layer.group_send(
                        self.room_name,
                        dict
                    )

    async def chat_message(self, content):
        await self.send_json(content)
    
    async def seen_count_update(self, content):
        await self.send_json(content)

    @database_sync_to_async
    def to_broadcast_and_get_dict_to_send(self, seen_message_id):
        try:
            msg_obj = GroupMessage.objects.get(id = seen_message_id)
        except:
            return False,None
        if msg_obj.group != self.group_obj or  msg_obj.sender == self.user:
            return False,None
        try:
            MessageReadTracking.objects.create(message = msg_obj, read_by_user = self.user)
        except:
            return False,None
        msg_obj.refresh_from_db()
        dict = {
            'type' : 'seen_count_update',
            'message_id' : msg_obj.id,
            'seen_count' : msg_obj.seen_count
        }
        return True, dict
    
    @database_sync_to_async
    def get_group_obj(self):
        try:
            group_obj = Group.objects.get(id = self.group_id)
        except:
            return None
        return group_obj

    @database_sync_to_async
    def save_message(self, sender, message):
        return GroupMessage.objects.create(
            sender = sender,
            content = message,
            group = self.group_obj
        )
    
    @database_sync_to_async
    def user_is_group_member(self):
        if GroupMember.objects.filter(group = self.group_obj, member = self.user).first() is None:
            return False
        return True
    
    @database_sync_to_async
    def get_previous_messages(self):
        messages = GroupMessage.objects.filter(
            group = self.group_obj
            ).order_by('timestamp')
        messages_list = []
        for msg in messages:
            messages_list.append(
                {
                    'id' : msg.id,
                    'sender' : msg.sender.username,
                    'content': msg.content,
                    'timestamp' : msg.timestamp.isoformat(),
                    'seen_count' : msg.seen_count,
                }
            )
        print(messages_list)
        return messages_list
    
    
class OnlineGroupUsersConsumer(AsyncJsonWebsocketConsumer):
    async def connect(self):
        print("OnlineGroupUsersConsumer: Browser trying to connect.................")
        self.user = self.scope['user']
        if self.user.is_anonymous :
            await self.close()
            return
        self.group_id = self.scope['url_route']['kwargs']['room_no']
        self.group_obj = await self.get_group_obj()
        if self.group_obj == None:
            await self.close()
            return
        self.is_group_member = await self.user_is_group_member()
        if not self.is_group_member:
            await self.close()
            return
        await self.accept()
        online_members = await self.get_online_members()
        await self.send_json(
            {
                'type' : 'online_members',
                'members' : online_members
            }
        )
        print("OnlineGroupUsersConsumer: CONNECTED............. USER : ",self.user.username)

    async def disconnect(self, code):
        print("OnlineGroupUsersConsumer: SOCKET CONNECTION DISSCONNECTED..........USER : ", self.user.username)

    async def receive_json(self, content):
        print("OnlineGroupUsersConsumer: Recieved online users request.................")
        type = content.get('type')
        if type == 'online_users_request':
            online_members = await self.get_online_members()
            await self.send_json(
                {
                    'type' : 'online_members',
                    'members' : online_members
                }
            )

    @database_sync_to_async
    def get_online_members(self):
        members =  self.group_obj.get_online_members()
        online_members = []
        for member in members:
            online_members.append(
                {
                    'id' : member.id,
                    'username' : member.username,
                    'name' : member.first_name + member.last_name
                }
            )
        print(online_members)
        return online_members
    
    @database_sync_to_async
    def get_group_obj(self):
        try:
            group_obj = Group.objects.get(id = self.group_id)
        except:
            return None
        return group_obj
    
    @database_sync_to_async
    def user_is_group_member(self):
        if GroupMember.objects.filter(group = self.group_obj, member = self.user).first() is None:
            return False
        return True

class UserOnlineStatusUpdateConsumer(AsyncJsonWebsocketConsumer):
    async def connect(self):
        print("UserOnlineStatusUpdateConsumer: Browser trying to connect.................")
        self.user = self.scope['user']
        if self.user.is_anonymous :
            await self.close()
            return
        await self.update_user_activity()
        await self.accept()

    async def disconnect(self, code):
        print("OnlineGroupUsersConsumer: SOCKET CONNECTION DISSCONNECTED..........USER : ", self.user.username)

    async def receive_json(self, content):
        print("Recieves online USER: ", self.user.username)
        type = content.get('type')
        if type == 'i_am_online':
            await self.update_user_activity()

    @database_sync_to_async
    def update_user_activity(self):
        self.user.useractivity.update_activity()


class AboutGroupConsumer(AsyncJsonWebsocketConsumer):
    async def connect(self):
        print("AboutGroupConsumer: Browser trying to connect.................")
        self.user = self.scope['user']
        if self.user.is_anonymous :
            await self.close()
            return
        self.group_id = self.scope['url_route']['kwargs']['group_id']
        self.group_obj = await self.get_group_obj()
        if self.group_obj == None:
            await self.close()
            return
        self.room_name = f'about_group_{self.group_id}'
        await self.accept()
        await self.channel_layer.group_add(
            self.room_name, 
            self.channel_name
        )
        print("AboutGroupConsumer: CONNECTED................. USER: ", self.user.username)

    async def disconnect(self, code):
        print("AboutGroupConsumer: DISCONNECTED................. USER: ", self.user.username)
        await self.channel_layer.group_discard(
            self.room_name,
            self.channel_name
        )

    async def receive_json(self, content):
        pass

    async def member_added(self, content):
        await self.send_json(content)

    async def member_removed(self, content):
        await self.send_json(content)

    async def admin_added(self, content):
        await self.send_json(content)
    
    async def admin_removed(self, content):
        await self.send_json(content)
    
    @database_sync_to_async
    def get_group_obj(self):
        try:
            group_obj = Group.objects.get(id = self.group_id)
        except:
            return None
        return group_obj


class AdminAccessConsumer(AsyncJsonWebsocketConsumer):
    async def connect(self):
        self.user = self.scope['user']
        self.group_id = self.scope['url_route']['kwargs']['group_id']
        self.room_name = f'about_group_{self.group_id}'
        if self.user.is_anonymous :
            await self.close()
            return
        self.group_obj = await self.get_group_obj()
        if self.group_obj == None:
            await self.close()
            return
        done = await self.is_user_is_group_member_and_admin()
        if not done:
            await self.close()
            return
        await self.channel_layer.group_add(
            self.room_name,
            self.channel_name
        )
        await self.accept()

    async def receive_json(self, data):
        if not await self.is_user_is_group_member_and_admin():
            await self.close()
            return
        type = data.get('type')
        if type == 'update_description':
            done  = await self.change_description(data['description'])
            if not done:
                return
            await self.channel_layer.group_send(
                self.room_name,
                {
                    'type': 'description_updated',
                    'description': self.group_obj.description
                }
            )
        elif type == 'add_member':
            await self.add_member_to_group(data['user_id'])
        elif type == 'remove_member':
            await self.remove_member_from_the_group(data['user_id'])
        elif type == 'add_admin':
            await self.add_admin_to_member(data['user_id'])
        elif type == 'remove_admin':
            await self.remove_admin_from_member(data['user_id'])
        elif type == 'accept_request':
            await self.accept_request_of_user(data['request_id'])
        elif type == 'reject_request':
            await self.reject_request_of_user(data['request_id'])
        elif type == 'search_user':
            done, user_list = await self.get_user_list_of_search_query(data['query'])
            if not done:
                return
            await self.channel_layer.group_send(
                self.room_name,
                {
                    'type' : 'search_results',
                    'results': user_list
                }
            )

    async def disconnect(self, code):
        await self.channel_layer.group_discard(
            self.room_name,
            self.channel_name
        )

    async def description_updated(self, content):
        await self.send_json(content)

    async def admin_removed(self, content):
        await self.send_json(content)

    async def admin_added(self, content):
        await self.send_json(content)

    async def member_added(self, content):
        await self.send_json(content)

    async def member_removed(self, content):
        await self.send_json(content)

    async def request_added(self, content):
        await self.send_json(content)

    async def request_removed(self, content):
        await self.send_json(content)

    async def search_results(self, content):
        await self.send_json(content)

    @database_sync_to_async
    def get_user_list_of_search_query(self , query):
        try:
            users = User.objects.filter(username__icontains = query).exclude(groupmember__group = self.group_obj)
            user_list = [ { 'id': user.id , 'username': user.username } for user in users ]
        except Exception as e:
            print(e)
            print("!!!!!!!!!!!!!!!!!problem in search query!!!!!!!!!!!!!!!!!!!!!")
            return False, None
        return True, user_list

    @database_sync_to_async
    def reject_request_of_user(self, request_id):
        try:
            print("INSIDE REJECT request")
            request_obj = GroupJoinRequest.objects.get(id = request_id)
            if request_obj.group != self.group_obj:
                raise Exception('Unauthorized Request to reject!!')
            request_obj.reject()
        except Exception as e:
            print(e)

    @database_sync_to_async
    def accept_request_of_user(self, request_id):
        try:
            print("INSIDE ACCEPT request")
            request_obj = GroupJoinRequest.objects.get(id = request_id)
            if request_obj.group != self.group_obj:
                raise Exception('Unauthorized Request to accept!!')
            request_obj.accept()
        except Exception as e:
            print(e)

    @database_sync_to_async
    def remove_admin_from_member(self, member_id):
        try:
            member_obj = User.objects.get(id = member_id)
            groupmember_obj = GroupMember.objects.get(group= self.group_obj, member= member_obj)
            groupmember_obj.is_admin = False
            groupmember_obj.save()
        except Exception as e:
            print(e)

    @database_sync_to_async
    def add_admin_to_member(self, member_id):
        try:
            member_obj = User.objects.get(id = member_id)
            groupmember_obj = GroupMember.objects.get(group= self.group_obj, member = member_obj)
            groupmember_obj.is_admin = True
            groupmember_obj.save()  
        except Exception as e:
            print(e)
    
    @database_sync_to_async
    def remove_member_from_the_group(self, member_id):
        try:
            member_obj = User.objects.get(id = member_id)
            groupmember_obj = GroupMember.objects.get(group = self.group_obj , member = member_obj)
            groupmember_obj.delete()
        except Exception as e:
            print(e)

    @database_sync_to_async
    def add_member_to_group(self, member_id):
        try:
            member_obj = User.objects.get(id = member_id)
            GroupMember.objects.create(group = self.group_obj , member = member_obj)
        except Exception as e:
            print(e)

    @database_sync_to_async
    def change_description(self, description):
        try: 
            group = Group.objects.get(id = self.group_id)
            group.description = description
            group.save()  # Save the updated group object
            self.group_obj = group
        except Exception as e:
            print(e)
            return False
        return True

    @database_sync_to_async
    def is_user_is_group_member_and_admin(self):
        try:
            obj  = GroupMember.objects.get(group=self.group_obj, member=self.user, is_admin = True)
        except Exception as e:
            print(e)
            return False
        return True
    
    @database_sync_to_async
    def get_group_obj(self):
        try:
            group_obj = Group.objects.get(id = self.group_id)
        except:
            return None
        return group_obj
    
    
class UserConsumer(AsyncJsonWebsocketConsumer):
    async def connect(self):
        self.user = self.scope['user']
        if self.user.is_anonymous :
            await self.close()
            return
        self.room_name = 'homepage_user'
        await self.channel_layer.group_add(
            self.room_name,
            self.channel_name
        )
        await self.accept()
    
    async def disconnect(self, code):
        await self.channel_layer.group_discard(
            self.room_name,
            self.channel_name
        )

    async def last_seen_updated(self, content):
        await self.send_json(content)
    
    async def receive_json(self, data):
        if data['type'] == 'search_users' and data['query'] != '':
            user_data = await self.get_users_based_on_search(data['query'])
        else:
            user_data = await self.get_random_users()
        await self.send_json({'users': user_data})
    
    @database_sync_to_async
    def get_users_based_on_search(self, query):
        users = User.objects.filter(username__icontains=query)[:5]
        user_data = []
        for user in users:
            if user == self.user:
                continue
            user_data.append(
                {
                    'id': user.id,
                    'username': user.username,
                    'name': user.first_name + ' ' + user.last_name,
                    'last_seen': user.useractivity.last_activity.isoformat()
                }
            )
        return user_data

    @database_sync_to_async
    def get_random_users(self):
        users = User.objects.order_by('?')[:5]
        user_data = []
        for user in users:
            if user == self.user:
                continue
            user_data.append(
                {
                    'id': user.id,
                    'username': user.username,
                    'name': user.first_name + ' ' + user.last_name,
                    'last_seen': user.useractivity.last_activity.isoformat()
                }
            )
        return user_data


class GroupConsumer(AsyncJsonWebsocketConsumer):
    async def connect(self):
        self.user = self.scope['user']
        if self.user.is_anonymous :
            await self.close()
            return
        self.room_name = f'homepage_user_{self.user.id}'
        await self.accept()
        await self.channel_layer.group_add(
            self.room_name,
            self.channel_name
        )
        await self.channel_layer.group_add(
            'homepage_group',
            self.channel_name
        )

    async def disconnect(self, code):
        await self.channel_layer.group_discard(
            self.room_name,
            self.channel_name
        )
        await self.channel_layer.group_discard(
            'homepage_group',
            self.channel_name
        )

    async def receive_json(self, data):
        if data['type'] == 'search_groups':
            query = data['query']
            if len(query) !=0 :
                group_data = await self.get_groups_based_on_search(query)
            else:
                group_data = await self.get_groups_based_on_search(query)
            await self.send_json({'groups': group_data})
        elif data['type'] == 'get_groups':
            group_data = await self.get_random_groups()
            await self.send_json({'groups': group_data})
        elif data['type'] == 'request_to_join':
            print("GOT request to join...........")
            await self.request_to_join_group(data['group_id'])
        elif data['type'] == 'cancel_request':
            await self.cancel_group_join_request(data['group_id'])
    
    async def update_status(self, content):
        await self.send_json(content)

    async def message_count_increased(self, content):
        await self.send_json(content)
    
    async def message_count_decreased(self, content):
        await self.send_json(content)
    
    async def member_count_increased(self, content):
        await self.send_json(content)

    async def member_count_decreased(self, content):
        await self.send_json(content)
    
    @database_sync_to_async
    def request_to_join_group(self,group_id):
        try:
            group_obj = Group.objects.get(id = group_id)
            GroupJoinRequest.objects.create(group = group_obj ,user = self.user)
        except Exception as e:
            print(e)

    @database_sync_to_async
    def cancel_group_join_request(self, group_id):
        try:
            obj = Group.objects.get(id = group_id)
            GroupJoinRequest.objects.filter(group = obj , user = self.user).delete()
        except Exception as e:
            print(e)

    @database_sync_to_async
    def get_groups_based_on_search(self, query):
        groups = Group.objects.filter(name__icontains=query)[:5]
        group_data = []
        for group in groups:
            if GroupMember.objects.filter(group=group , member = self.user).exists():
                status = 'member'
            elif GroupJoinRequest.objects.filter(group=group , user = self.user).exists():
                status = 'requested'
            else:
                status = 'not_member'
            group_data.append(
                {
                    'id' : group.id,
                    'name': group.name,
                    'creator': group.creator.username,
                    'members_count': GroupMember.objects.filter(group=group).count(),
                    'messages_count': GroupMessage.objects.filter(group=group).count(),
                    'status' : status
                }
            )
        return group_data
    
    @database_sync_to_async
    def get_random_groups(self):
        groups = Group.objects.order_by('?')[:5]
        group_data = []
        for group in groups:
            if GroupMember.objects.filter(group=group , member = self.user).exists():
                status = 'member'
            elif GroupJoinRequest.objects.filter(group=group , user = self.user).exists():
                status = 'requested'
            else:
                status = 'not_member'
            group_data.append(
                {
                    'id' : group.id,
                    'name': group.name,
                    'creator': group.creator.username,
                    'members_count': GroupMember.objects.filter(group=group).count(),
                    'messages_count': GroupMessage.objects.filter(group=group).count(),
                    'status' : status
                }
            )
        return group_data

class OnlineUserConsumer(AsyncJsonWebsocketConsumer):
    async def connect(self):
        self.user = self.scope['user']
        if self.user.is_anonymous :
            await self.close()
            return
        await self.channel_layer.group_add(
            'online_users',
            self.channel_name
        )
        await self.accept()
        await self.update_activity()
        self.update_task = asyncio.create_task(self.periodic_update())
        self.update_last_activity_task = asyncio.create_task(self.update_last_activity())

    async def disconnect(self, code):
        self.update_task.cancel()
        self.update_last_activity_task.cancel()
        await self.channel_layer.group_discard(
            'online_users',
            self.channel_name
        )

    @database_sync_to_async
    def update_activity(self):
        self.user.useractivity.update_activity()
        
    async def receive_json(self, data):
        print(data['type'])
        online_users = await self.get_online_users()
        print(online_users)
        await self.send_json({
            'online_users': online_users
            })
        
    async def update_last_activity(self):
        while True:
            await asyncio.sleep(last_activity_update_interval)
            await self.update_activity()
        
    async def periodic_update(self):
        while True:
            online_users = await self.get_online_users()
            await self.send_json({
                'online_users': online_users
                })
            await asyncio.sleep(online_user_send_interval) 
            

    @database_sync_to_async
    def get_online_users(self):
        members =  self.user.useractivity.get_online_users()
        online_members = []
        for member in members:
            online_members.append(
                {
                    'id' : member.id,
                    'username' : member.username,
                    'name' : member.first_name + member.last_name
                }
            )
        return online_members
    

class PrivateChatsListConsumer(AsyncJsonWebsocketConsumer):
    async def connect(self):
        self.user = self.scope['user']
        if not self.user.is_authenticated:
            await self.close()
            return
        await self.accept()
        self.room_name = f'chatslist_user_{self.user.id}'
        await self.channel_layer.group_add(
            self.room_name,
            self.channel_name
        )
        await self.channel_layer.group_add(
            'chatslist',
            self.channel_name
        )
        self.update_last_activity_task = asyncio.create_task(self.update_user_last_activity())

    async def disconnect(self, close_code):
        self.update_last_activity_task.cancel()
        await self.channel_layer.group_discard(
            self.room_name,
            self.channel_name
        )
        await self.channel_layer.group_discard(
            'chatslist',
            self.channel_name
        )

    async def receive_json(self, data):
        pass

    @database_sync_to_async
    def update_activity(self):
        self.user.useractivity.update_activity()
    
    async def update_user_last_activity(self):
        while True:
            await asyncio.sleep(last_activity_update_interval)
            await self.update_activity()

    async def last_seen_updated(self, content):
        await self.send_json(content)

    async def unread_count_incremented(self, content):
        await self.send_json(content)

    async def last_activity_updated(self, content):
        await self.send_json(content)

    async def new_chat_added(self, content):
        await self.send_json(content)