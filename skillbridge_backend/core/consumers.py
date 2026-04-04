"""
WebSocket Consumer — Real-time chat via Django Channels.
Frontend connects to: ws://localhost:8000/ws/chat/<room_name>/
room_name is typically "user_{min_id}_{max_id}" to ensure both
users join the same room regardless of who initiates.
"""
import json
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from django.contrib.auth import get_user_model

User = get_user_model()


class ChatConsumer(AsyncWebsocketConsumer):
    """Handles WebSocket connections for real-time chat."""

    async def connect(self):
        self.room_name = self.scope["url_route"]["kwargs"]["room_name"]
        self.room_group_name = f"chat_{self.room_name}"

        # Join room group
        await self.channel_layer.group_add(
            self.room_group_name,
            self.channel_name
        )
        await self.accept()
        await self.send(text_data=json.dumps({
            "type": "system",
            "message": f"Connected to room: {self.room_name}"
        }))

    async def disconnect(self, close_code):
        # Leave room group
        await self.channel_layer.group_discard(
            self.room_group_name,
            self.channel_name
        )

    async def receive(self, text_data):
        """Handle incoming WebSocket message from client."""
        try:
            data = json.loads(text_data)
        except json.JSONDecodeError:
            await self.send(text_data=json.dumps({"type": "error", "message": "Invalid JSON"}))
            return

        msg_type = data.get("type", "message")

        if msg_type == "message":
            sender_id = data.get("sender_id")
            receiver_id = data.get("receiver_id")
            content = data.get("content", "").strip()

            if not content or not sender_id or not receiver_id:
                return

            # Save to database
            saved_msg = await self.save_message(sender_id, receiver_id, content)

            # Broadcast to room group
            await self.channel_layer.group_send(
                self.room_group_name,
                {
                    "type": "chat_message",
                    "message_id": saved_msg["id"],
                    "sender_id": saved_msg["sender_id"],
                    "sender_name": saved_msg["sender_name"],
                    "content": saved_msg["content"],
                    "timestamp": saved_msg["timestamp"],
                }
            )

        elif msg_type == "typing":
            # Broadcast typing indicator
            await self.channel_layer.group_send(
                self.room_group_name,
                {
                    "type": "typing_indicator",
                    "user_id": data.get("user_id"),
                    "is_typing": data.get("is_typing", False),
                }
            )

        elif msg_type == "read":
            # Mark messages as read
            await self.mark_messages_read(data.get("reader_id"), data.get("sender_id"))

    async def chat_message(self, event):
        """Send message to WebSocket client."""
        await self.send(text_data=json.dumps({
            "type": "message",
            "message_id": event["message_id"],
            "sender_id": event["sender_id"],
            "sender_name": event["sender_name"],
            "content": event["content"],
            "timestamp": event["timestamp"],
        }))

    async def typing_indicator(self, event):
        """Send typing indicator to WebSocket client."""
        await self.send(text_data=json.dumps({
            "type": "typing",
            "user_id": event["user_id"],
            "is_typing": event["is_typing"],
        }))

    @database_sync_to_async
    def save_message(self, sender_id, receiver_id, content):
        from .models import Message
        try:
            sender = User.objects.get(id=sender_id)
            receiver = User.objects.get(id=receiver_id)
            msg = Message.objects.create(
                sender=sender,
                receiver=receiver,
                content=content
            )
            return {
                "id": msg.id,
                "sender_id": sender.id,
                "sender_name": sender.full_name,
                "content": msg.content,
                "timestamp": msg.timestamp.isoformat(),
            }
        except User.DoesNotExist:
            return {"id": None, "sender_id": sender_id, "sender_name": "Unknown",
                    "content": content, "timestamp": ""}

    @database_sync_to_async
    def mark_messages_read(self, reader_id, sender_id):
        from .models import Message
        try:
            reader = User.objects.get(id=reader_id)
            sender = User.objects.get(id=sender_id)
            Message.objects.filter(receiver=reader, sender=sender, is_read=False).update(is_read=True)
        except User.DoesNotExist:
            pass


class VideoSignalingConsumer(AsyncWebsocketConsumer):
    """
    WebSocket Consumer for Agora video call signaling.
    Handles: call_offer, call_accept, call_reject, call_end events.
    Frontend: ws://localhost:8000/ws/video/<channel_name>/
    """

    async def connect(self):
        self.channel_name_param = self.scope["url_route"]["kwargs"]["channel_name"]
        self.room_group_name = f"video_{self.channel_name_param}"

        await self.channel_layer.group_add(self.room_group_name, self.channel_name)
        await self.accept()

    async def disconnect(self, close_code):
        await self.channel_layer.group_discard(self.room_group_name, self.channel_name)

    async def receive(self, text_data):
        try:
            data = json.loads(text_data)
        except json.JSONDecodeError:
            return

        signal_type = data.get("type")

        # Broadcast signaling events to all peers in the channel
        if signal_type in ["call_offer", "call_accept", "call_reject", "call_end", "ice_candidate"]:
            await self.channel_layer.group_send(
                self.room_group_name,
                {
                    "type": "video_signal",
                    "signal_type": signal_type,
                    "from_user": data.get("from_user"),
                    "to_user": data.get("to_user"),
                    "data": data.get("data"),
                }
            )

    async def video_signal(self, event):
        await self.send(text_data=json.dumps({
            "type": event["signal_type"],
            "from_user": event["from_user"],
            "to_user": event["to_user"],
            "data": event["data"],
        }))
