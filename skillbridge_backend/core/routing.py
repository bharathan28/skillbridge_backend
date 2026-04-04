from django.urls import re_path
from . import consumers

websocket_urlpatterns = [
    # Chat WebSocket: ws://host/ws/chat/user_1_2/
    re_path(r"^ws/chat/(?P<room_name>[^/]+)/$", consumers.ChatConsumer.as_asgi()),
    # Video signaling: ws://host/ws/video/channel_name/
    re_path(r"^ws/video/(?P<channel_name>[^/]+)/$", consumers.VideoSignalingConsumer.as_asgi()),
]
