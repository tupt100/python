from channels.routing import ProtocolTypeRouter, URLRouter
from channels.security.websocket import AllowedHostsOriginValidator
from django.urls import path
from notifications.socket_notification import NotificationConsumer

# application = ProtocolTypeRouter({
#     "websocket": URLRouter([
#         path("notifications/", NotificationConsumer),
#     ])
# })

from notifications.token_auth import TokenAuthMiddlewareStack

application = ProtocolTypeRouter({
    "websocket": AllowedHostsOriginValidator(TokenAuthMiddlewareStack(
        URLRouter([
            path("notifications/", NotificationConsumer.as_asgi()),
        ]),
    ), ),
})
