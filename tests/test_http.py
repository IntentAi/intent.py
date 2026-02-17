"""Tests for HTTP client."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from intent._route import Route
from intent.errors import Forbidden, NotFound, RateLimited, ServerError, Unauthorized
from intent.http import HTTPClient


class TestHTTPClient:
    """Test HTTPClient functionality."""

    @pytest.fixture
    def client(self) -> HTTPClient:
        """Create HTTP client instance."""
        return HTTPClient(token="test_token", base_url="https://test.api")

    @pytest.fixture
    def mock_response(self) -> MagicMock:
        """Create mock aiohttp response."""
        resp = MagicMock()
        resp.status = 200
        resp.headers = {
            "x-ratelimit-limit": "10",
            "x-ratelimit-remaining": "9",
            "x-ratelimit-reset": "1234567890",
            "x-ratelimit-bucket": "test:bucket",
        }
        resp.json = AsyncMock(return_value={"id": "123", "data": "test"})
        resp.text = AsyncMock(return_value="OK")
        resp.__aenter__ = AsyncMock(return_value=resp)
        resp.__aexit__ = AsyncMock(return_value=None)
        return resp

    async def test_session_creation(self, client: HTTPClient) -> None:
        """Test session is created lazily."""
        assert client._session is None
        session = await client._get_session()
        assert session is not None
        assert client._session is session
        await client.close()

    async def test_close_session(self, client: HTTPClient) -> None:
        """Test session cleanup."""
        await client._get_session()
        await client.close()
        assert client._session.closed

    async def test_bucket_creation(self, client: HTTPClient) -> None:
        """Test bucket is created per route."""
        route1 = Route("GET", "/servers/123")
        route2 = Route("GET", "/servers/456")

        bucket1 = client._get_bucket(route1)
        bucket2 = client._get_bucket(route2)

        assert bucket1 is not bucket2
        assert route1.bucket_key in client._buckets
        assert route2.bucket_key in client._buckets

    async def test_successful_request(
        self, client: HTTPClient, mock_response: MagicMock
    ) -> None:
        """Test successful HTTP request."""
        with patch("aiohttp.ClientSession") as mock_session_cls:
            mock_session = MagicMock()
            mock_session.request = MagicMock(return_value=mock_response)
            mock_session.close = AsyncMock()
            mock_session.close = AsyncMock()
            mock_session.closed = False
            mock_session_cls.return_value = mock_session

            result = await client.request(Route("GET", "/test"))

            assert result == {"id": "123", "data": "test"}
            mock_session.request.assert_called_once()
            call_kwargs = mock_session.request.call_args[1]
            assert "Authorization" in call_kwargs["headers"]
            assert call_kwargs["headers"]["Authorization"] == "Bearer test_token"

        await client.close()

    async def test_204_no_content(
        self, client: HTTPClient, mock_response: MagicMock
    ) -> None:
        """Test 204 response returns None."""
        mock_response.status = 204

        with patch("aiohttp.ClientSession") as mock_session_cls:
            mock_session = MagicMock()
            mock_session.request = MagicMock(return_value=mock_response)
            mock_session.close = AsyncMock()
            mock_session.closed = False
            mock_session_cls.return_value = mock_session

            result = await client.request(Route("DELETE", "/test"))
            assert result is None

        await client.close()

    async def test_401_unauthorized(
        self, client: HTTPClient, mock_response: MagicMock
    ) -> None:
        """Test 401 raises Unauthorized."""
        mock_response.status = 401
        mock_response.text = AsyncMock(return_value="Unauthorized")

        with patch("aiohttp.ClientSession") as mock_session_cls:
            mock_session = MagicMock()
            mock_session.request = MagicMock(return_value=mock_response)
            mock_session.close = AsyncMock()
            mock_session.closed = False
            mock_session_cls.return_value = mock_session

            with pytest.raises(Unauthorized):
                await client.request(Route("GET", "/test"))

        await client.close()

    async def test_403_forbidden(
        self, client: HTTPClient, mock_response: MagicMock
    ) -> None:
        """Test 403 raises Forbidden."""
        mock_response.status = 403
        mock_response.text = AsyncMock(return_value="Forbidden")

        with patch("aiohttp.ClientSession") as mock_session_cls:
            mock_session = MagicMock()
            mock_session.request = MagicMock(return_value=mock_response)
            mock_session.close = AsyncMock()
            mock_session.closed = False
            mock_session_cls.return_value = mock_session

            with pytest.raises(Forbidden):
                await client.request(Route("GET", "/test"))

        await client.close()

    async def test_404_not_found(
        self, client: HTTPClient, mock_response: MagicMock
    ) -> None:
        """Test 404 raises NotFound."""
        mock_response.status = 404
        mock_response.text = AsyncMock(return_value="Not found")

        with patch("aiohttp.ClientSession") as mock_session_cls:
            mock_session = MagicMock()
            mock_session.request = MagicMock(return_value=mock_response)
            mock_session.close = AsyncMock()
            mock_session.closed = False
            mock_session_cls.return_value = mock_session

            with pytest.raises(NotFound):
                await client.request(Route("GET", "/test"))

        await client.close()

    async def test_429_rate_limit_retry(
        self, client: HTTPClient, mock_response: MagicMock
    ) -> None:
        """Test 429 with retry_after is handled."""
        # First response is 429, second is success
        resp_429 = MagicMock()
        resp_429.status = 429
        resp_429.headers = mock_response.headers
        resp_429.json = AsyncMock(return_value={"retry_after": 0.1, "global": False})
        resp_429.__aenter__ = AsyncMock(return_value=resp_429)
        resp_429.__aexit__ = AsyncMock(return_value=None)

        with patch("aiohttp.ClientSession") as mock_session_cls:
            mock_session = MagicMock()
            mock_session.request = MagicMock(side_effect=[resp_429, mock_response])
            mock_session.close = AsyncMock()
            mock_session.closed = False
            mock_session_cls.return_value = mock_session

            with patch("asyncio.sleep") as mock_sleep:
                result = await client.request(Route("GET", "/test"))

                assert result == {"id": "123", "data": "test"}
                mock_sleep.assert_called_once_with(0.1)
                assert mock_session.request.call_count == 2

        await client.close()

    async def test_429_max_retries(
        self, client: HTTPClient, mock_response: MagicMock
    ) -> None:
        """Test 429 raises after max retries."""
        client.max_retries = 2

        resp_429 = MagicMock()
        resp_429.status = 429
        resp_429.headers = mock_response.headers
        resp_429.json = AsyncMock(return_value={"retry_after": 0.01, "global": False})
        resp_429.__aenter__ = AsyncMock(return_value=resp_429)
        resp_429.__aexit__ = AsyncMock(return_value=None)

        with patch("aiohttp.ClientSession") as mock_session_cls:
            mock_session = MagicMock()
            mock_session.request = MagicMock(return_value=resp_429)
            mock_session.close = AsyncMock()
            mock_session.closed = False
            mock_session_cls.return_value = mock_session

            with patch("asyncio.sleep"):
                with pytest.raises(RateLimited):
                    await client.request(Route("GET", "/test"))

        await client.close()

    async def test_500_server_error_retry(
        self, client: HTTPClient, mock_response: MagicMock
    ) -> None:
        """Test 500 error retries with backoff."""
        resp_500 = MagicMock()
        resp_500.status = 500
        resp_500.headers = mock_response.headers
        resp_500.text = AsyncMock(return_value="Server error")
        resp_500.__aenter__ = AsyncMock(return_value=resp_500)
        resp_500.__aexit__ = AsyncMock(return_value=None)

        with patch("aiohttp.ClientSession") as mock_session_cls:
            mock_session = MagicMock()
            mock_session.request = MagicMock(side_effect=[resp_500, mock_response])
            mock_session.close = AsyncMock()
            mock_session.closed = False
            mock_session_cls.return_value = mock_session

            with patch("asyncio.sleep") as mock_sleep:
                result = await client.request(Route("GET", "/test"))

                assert result == {"id": "123", "data": "test"}
                mock_sleep.assert_called_once()
                assert mock_session.request.call_count == 2

        await client.close()

    async def test_500_max_retries(
        self, client: HTTPClient, mock_response: MagicMock
    ) -> None:
        """Test 500 raises after max retries."""
        client.max_retries = 2

        resp_500 = MagicMock()
        resp_500.status = 503
        resp_500.headers = mock_response.headers
        resp_500.text = AsyncMock(return_value="Service unavailable")
        resp_500.__aenter__ = AsyncMock(return_value=resp_500)
        resp_500.__aexit__ = AsyncMock(return_value=None)

        with patch("aiohttp.ClientSession") as mock_session_cls:
            mock_session = MagicMock()
            mock_session.request = MagicMock(return_value=resp_500)
            mock_session.close = AsyncMock()
            mock_session.closed = False
            mock_session_cls.return_value = mock_session

            with patch("asyncio.sleep"):
                with pytest.raises(ServerError):
                    await client.request(Route("GET", "/test"))

        await client.close()

    async def test_endpoint_get_servers(self, client: HTTPClient) -> None:
        """Test get_servers endpoint."""
        with patch.object(client, "request", new_callable=AsyncMock) as mock_req:
            mock_req.return_value = [{"id": "123", "name": "Test"}]

            result = await client.get_servers()

            assert result == [{"id": "123", "name": "Test"}]
            mock_req.assert_called_once()
            route = mock_req.call_args[0][0]
            assert route.method == "GET"
            assert route.path == "/servers"

    async def test_endpoint_send_message(self, client: HTTPClient) -> None:
        """Test send_message endpoint."""
        with patch.object(client, "request", new_callable=AsyncMock) as mock_req:
            mock_req.return_value = {"id": "msg123", "content": "Hello"}

            result = await client.send_message("ch123", content="Hello")

            assert result == {"id": "msg123", "content": "Hello"}
            mock_req.assert_called_once()
            route = mock_req.call_args[0][0]
            assert route.method == "POST"
            assert route.path == "/channels/ch123/messages"
            assert mock_req.call_args[1]["json"] == {"content": "Hello"}
