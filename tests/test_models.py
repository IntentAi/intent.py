"""Tests for data models."""

from intent.enums import ChannelType
from intent.http import HTTPClient
from intent.models import Channel, Message, Server, User
from intent.state import ConnectionState


class TestModels:
    """Test Intent data models."""

    def test_user_creation(self) -> None:
        """Test User model creation."""
        http = HTTPClient(token="test")
        state = ConnectionState(http)

        data = {
            "id": "123456",
            "username": "alice",
            "display_name": "Alice",
            "avatar_url": "https://example.com/avatar.png",
            "created_at": "2024-01-01T00:00:00Z",
        }

        user = User(data=data, state=state)

        assert user.id == "123456"
        assert user.username == "alice"
        assert user.display_name == "Alice"
        assert user.avatar_url == "https://example.com/avatar.png"
        assert user.created_at == "2024-01-01T00:00:00Z"
        assert str(user) == "Alice"
        assert "alice" in repr(user)

    def test_user_equality(self) -> None:
        """Test User equality and hashing."""
        http = HTTPClient(token="test")
        state = ConnectionState(http)

        data1 = {
            "id": "123",
            "username": "alice",
            "display_name": "Alice",
            "avatar_url": None,
            "created_at": "2024-01-01T00:00:00Z",
        }
        data2 = {
            "id": "123",
            "username": "alice2",
            "display_name": "Alice 2",
            "avatar_url": None,
            "created_at": "2024-01-01T00:00:00Z",
        }
        data3 = {
            "id": "456",
            "username": "bob",
            "display_name": "Bob",
            "avatar_url": None,
            "created_at": "2024-01-01T00:00:00Z",
        }

        user1 = User(data=data1, state=state)
        user2 = User(data=data2, state=state)
        user3 = User(data=data3, state=state)

        # Same ID = equal
        assert user1 == user2
        assert hash(user1) == hash(user2)

        # Different ID = not equal
        assert user1 != user3
        assert hash(user1) != hash(user3)

        # Can be used in sets
        user_set = {user1, user2, user3}
        assert len(user_set) == 2

    def test_server_creation(self) -> None:
        """Test Server model creation."""
        http = HTTPClient(token="test")
        state = ConnectionState(http)

        data = {
            "id": "789",
            "name": "Test Server",
            "owner_id": "123",
            "icon_url": "https://example.com/icon.png",
            "description": "A test server",
            "member_count": 42,
            "created_at": "2024-01-01T00:00:00Z",
        }

        server = Server(data=data, state=state)

        assert server.id == "789"
        assert server.name == "Test Server"
        assert server.owner_id == "123"
        assert server.icon_url == "https://example.com/icon.png"
        assert server.description == "A test server"
        assert server.member_count == 42
        assert str(server) == "Test Server"
        assert "789" in repr(server)

    def test_channel_creation(self) -> None:
        """Test Channel model creation."""
        http = HTTPClient(token="test")
        state = ConnectionState(http)

        data = {
            "id": "111",
            "server_id": "789",
            "name": "general",
            "type": 0,
            "topic": "General chat",
            "position": 0,
            "parent_id": "222",
            "created_at": "2024-01-01T00:00:00Z",
        }

        channel = Channel(data=data, state=state)

        assert channel.id == "111"
        assert channel.server_id == "789"
        assert channel.name == "general"
        assert channel.type == ChannelType.TEXT
        assert channel.topic == "General chat"
        assert channel.position == 0
        assert channel.parent_id == "222"
        assert str(channel) == "general"
        assert "TEXT" in repr(channel)

    def test_channel_types(self) -> None:
        """Test Channel type enum."""
        http = HTTPClient(token="test")
        state = ConnectionState(http)

        text_data = {
            "id": "1",
            "server_id": "789",
            "name": "text",
            "type": 0,
            "topic": None,
            "position": 0,
            "parent_id": None,
            "created_at": "2024-01-01T00:00:00Z",
        }
        voice_data = {
            "id": "2",
            "server_id": "789",
            "name": "voice",
            "type": 1,
            "topic": None,
            "position": 1,
            "parent_id": None,
            "created_at": "2024-01-01T00:00:00Z",
        }
        category_data = {
            "id": "3",
            "server_id": "789",
            "name": "category",
            "type": 2,
            "topic": None,
            "position": 2,
            "parent_id": None,
            "created_at": "2024-01-01T00:00:00Z",
        }

        text_ch = Channel(data=text_data, state=state)
        voice_ch = Channel(data=voice_data, state=state)
        category_ch = Channel(data=category_data, state=state)

        assert text_ch.type == ChannelType.TEXT
        assert voice_ch.type == ChannelType.VOICE
        assert category_ch.type == ChannelType.CATEGORY

    def test_message_creation(self) -> None:
        """Test Message model creation."""
        http = HTTPClient(token="test")
        state = ConnectionState(http)

        data = {
            "id": "999",
            "channel_id": "111",
            "author": {
                "id": "123",
                "username": "alice",
                "display_name": "Alice",
                "avatar_url": None,
                "created_at": "2024-01-01T00:00:00Z",
            },
            "content": "Hello world!",
            "created_at": "2024-01-01T12:00:00Z",
            "edited_at": None,
            "webhook_id": None,
        }

        message = Message(data=data, state=state)

        assert message.id == "999"
        assert message.channel_id == "111"
        assert message.author.id == "123"
        assert message.author.username == "alice"
        assert message.content == "Hello world!"
        assert message.created_at == "2024-01-01T12:00:00Z"
        assert message.edited_at is None
        assert message.webhook_id is None
        assert str(message) == "Hello world!"
        assert "999" in repr(message)

    def test_message_webhook(self) -> None:
        """Test Message webhook detection."""
        http = HTTPClient(token="test")
        state = ConnectionState(http)

        normal_data = {
            "id": "1",
            "channel_id": "111",
            "author": {
                "id": "123",
                "username": "alice",
                "display_name": "Alice",
                "avatar_url": None,
                "created_at": "2024-01-01T00:00:00Z",
            },
            "content": "Normal message",
            "created_at": "2024-01-01T12:00:00Z",
            "edited_at": None,
            "webhook_id": None,
        }

        webhook_data = {
            "id": "2",
            "channel_id": "111",
            "author": {
                "id": "456",
                "username": "webhook",
                "display_name": "Webhook",
                "avatar_url": None,
                "created_at": "2024-01-01T00:00:00Z",
            },
            "content": "Webhook message",
            "created_at": "2024-01-01T12:00:00Z",
            "edited_at": None,
            "webhook_id": "webhook_123",
        }

        normal_msg = Message(data=normal_data, state=state)
        webhook_msg = Message(data=webhook_data, state=state)

        assert not normal_msg.is_webhook
        assert webhook_msg.is_webhook
