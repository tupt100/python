from channels.generic.websocket import AsyncJsonWebsocketConsumer

from .models import Notification


class NotificationConsumer(AsyncJsonWebsocketConsumer):
    # Create on group
    user_group = 'user_channel'
    organisation_group = 'organisation_channel'
    global_group = 'global'

    async def connect(self):
        user = self.scope.get("user")
        await self.accept()
        print('WS: connect', user)
        # await self.channel_layer.group_add("notification", self.channel_name)
        await self.channel_layer.group_add('user_channel_{}'.format(user.id),
                                           self.channel_name)
        # await self.channel_layer.group_add(self.global_group,
        # self.channel_name)
        print("Added {} channel for notification".format({self.channel_name}))

    async def disconnect(self, close_code):
        user = self.scope.get("user")
        print('WS: disconnect', user)
        # await self.channel_layer.group_discard("notification",
        # self.channel_name)
        await self.channel_layer.group_discard(
            'user_channel_{}'.format(user.id), self.channel_name)
        # await self.channel_layer.group_discard(self.global_group,
        # self.channel_name)
        print("Removed {} channel to notification".format({self.channel_name}))

    async def user_notification(self, event):
        # await self.send_json(event)
        print("Got message")
        print(event, self.channel_name)
        user = self.scope.get("user")
        # Count Unread Notification on behalf of user
        unread = Notification.objects.filter(user=user, status=1).count()
        # Send a message down to the client
        await self.send_json(
            {
                "msg_type": "Notification",
                "username": event["username"],
                "message": event["message"],
                "unread_count": unread,
            },
        )
