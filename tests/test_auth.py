import json
from unittest.mock import patch

import httpx
import pytest
from httpx import Response

from nestor_matrix import auth


class TestResolveHomeserver:
    @pytest.mark.asyncio
    async def test_valid_well_known(self, respx_mock):
        """Returns base_url from well-known JSON when available."""
        domain = "matrix.org"
        well_known_url = f"https://{domain}/.well-known/matrix/client"
        expected_url = "https://matrix-client.matrix.org"

        respx_mock.get(well_known_url).mock(
            return_value=Response(
                200, json={"m.homeserver": {"base_url": expected_url}}
            )
        )

        assert expected_url == await auth.resolve_homeserver(domain)

    @pytest.mark.asyncio
    async def test_well_known_404_fallback(self, respx_mock):
        """Falls back to original domain when well-known returns 404."""
        domain = "example.com"
        well_known_url = f"https://{domain}/.well-known/matrix/client"

        respx_mock.get(well_known_url).mock(return_value=Response(404))

        assert f"https://{domain}" == await auth.resolve_homeserver(domain)

    @pytest.mark.asyncio
    async def test_invalid_json_raises_error(self, respx_mock):
        """Raises ValueError on invalid JSON from well-known."""
        domain = "invalidjson.org"
        well_known_url = f"https://{domain}/.well-known/matrix/client"

        respx_mock.get(well_known_url).mock(
            return_value=Response(200, json="Non json response")
        )

        with pytest.raises(ValueError, match="Well-known lookup failed"):
            await auth.resolve_homeserver(domain)

    @pytest.mark.asyncio
    async def test_respects_http_schema_in_domain(self, respx_mock):
        """Respects http schema in the original domain."""
        domain = "http://example.com"
        well_known_url = "http://example.com/.well-known/matrix/client"

        respx_mock.get(well_known_url).mock(return_value=Response(404))

        assert domain == await auth.resolve_homeserver(domain)

    @pytest.mark.asyncio
    async def test_http_error_raises_error(self, respx_mock):
        """Raises ValueError on HTTP errors when resolving homeserver."""
        domain = "raises.org"
        well_known_url = f"https://{domain}/.well-known/matrix/client"

        respx_mock.get(well_known_url).mock(side_effect=httpx.ConnectError)

        with pytest.raises(ValueError, match="Well-known lookup failed"):
            await auth.resolve_homeserver(domain)


@pytest.fixture
def resolved_homeserver():
    """Mock resolved homeserver."""
    with patch("nestor_matrix.auth.resolve_homeserver") as resolve_homeserver:
        homeserver = "https://matrix.example.com"
        resolve_homeserver.return_value = homeserver
        yield homeserver


class TestGetAccessToken:
    @pytest.mark.asyncio
    async def test_successful_login_with_full_mxid(
        self, respx_mock, resolved_homeserver
    ):
        """Returns access token and device ID on successful login."""
        homeserver = "matrix.example.com"
        username = "@user:example.com"
        password = "secret123"
        expected_token = "syt_dGVzdA_AbCdEfGhIjKlMnOpQrS_123456"
        expected_device = "ABCDEFGHIJ"

        respx_mock.post(f"{resolved_homeserver}/_matrix/client/v3/login").mock(
            return_value=Response(
                200,
                json={
                    "user_id": username,
                    "access_token": expected_token,
                    "device_id": expected_device,
                    "home_server": "example.com",
                },
            )
        )

        token, device_id = await auth.get_access_token(homeserver, username, password)

        assert token == expected_token
        assert device_id == expected_device

    @pytest.mark.asyncio
    async def test_login_with_localpart_username(self, respx_mock, resolved_homeserver):
        """Converts localpart to full MXID using homeserver domain."""
        homeserver = "matrix.example.com"
        username = "alice"  # No @ prefix
        password = "secret123"
        expected_mxid = "@alice:matrix.example.com"

        respx_mock.post(f"{resolved_homeserver}/_matrix/client/v3/login").mock(
            return_value=Response(
                200,
                json={
                    "user_id": expected_mxid,
                    "access_token": "token",
                    "device_id": "DEVICE",
                },
            )
        )

        await auth.get_access_token(homeserver, username, password)

        # Verify the request used the full MXID
        request = respx_mock.calls.last.request
        body = json.loads(request.content)
        assert body["identifier"]["user"] == "@alice:matrix.example.com"

    @pytest.mark.asyncio
    async def test_resolves_homeserver_before_login(
        self, respx_mock, resolved_homeserver
    ):
        """Resolves homeserver via well-known before attempting login."""
        homeserver = "example.com"
        username = "@user:example.com"
        password = "secret"

        respx_mock.post(f"{resolved_homeserver}/_matrix/client/v3/login").mock(
            return_value=Response(
                200,
                json={
                    "user_id": username,
                    "access_token": "token",
                    "device_id": "DEVICE",
                },
            )
        )

        await auth.get_access_token(homeserver, username, password)
        # The domain and the resolved homeserver used in the request are
        # different (this implicitly means that we resolved the homeserver)
        assert homeserver != resolved_homeserver

    @pytest.mark.asyncio
    async def test_login_failure_raises_http_error(
        self, respx_mock, resolved_homeserver
    ):
        """Raises HTTPStatusError on failed login (403 Forbidden)."""
        homeserver = "matrix.example.com"
        username = "@user:example.com"
        password = "wrongpassword"

        respx_mock.post(f"{resolved_homeserver}/_matrix/client/v3/login").mock(
            return_value=Response(
                403,
                json={
                    "errcode": "M_FORBIDDEN",
                    "error": "Invalid username or password",
                },
            )
        )

        with pytest.raises(httpx.HTTPStatusError) as exc_info:
            await auth.get_access_token(homeserver, username, password)

        assert exc_info.value.response.status_code == 403

    @pytest.mark.asyncio
    async def test_sends_correct_login_payload(self, respx_mock, resolved_homeserver):
        """Sends properly formatted login request payload."""
        homeserver = "matrix.example.com"
        username = "@bob:example.com"
        password = "mypassword"

        respx_mock.post(f"{resolved_homeserver}/_matrix/client/v3/login").mock(
            return_value=Response(
                200,
                json={
                    "user_id": username,
                    "access_token": "token",
                    "device_id": "DEVICE",
                },
            )
        )

        await auth.get_access_token(homeserver, username, password)

        request = respx_mock.calls.last.request
        body = json.loads(request.content)

        # Verify request contains correct fields
        assert body == {
            "type": "m.login.password",
            "identifier": {"type": "m.id.user", "user": "@bob:example.com"},
            "password": "mypassword",
        }

    @pytest.mark.asyncio
    async def test_network_error_propagates(self, respx_mock, resolved_homeserver):
        """Network errors during login propagate to caller."""
        homeserver = "matrix.example.com"
        username = "@user:example.com"
        password = "secret"

        respx_mock.post(f"{resolved_homeserver}/_matrix/client/v3/login").mock(
            side_effect=httpx.ConnectError("Connection failed")
        )

        with pytest.raises(httpx.ConnectError):
            await auth.get_access_token(homeserver, username, password)
