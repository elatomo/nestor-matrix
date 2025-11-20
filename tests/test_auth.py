import httpx
import pytest
from httpx import Response

from nestor_matrix.auth import resolve_homeserver


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

        assert expected_url == await resolve_homeserver(domain)

    @pytest.mark.asyncio
    async def test_well_known_404_fallback(self, respx_mock):
        """Falls back to original domain when well-known returns 404."""
        domain = "example.com"
        well_known_url = f"https://{domain}/.well-known/matrix/client"

        respx_mock.get(well_known_url).mock(return_value=Response(404))

        assert f"https://{domain}" == await resolve_homeserver(domain)

    @pytest.mark.asyncio
    async def test_invalid_json_raises_error(self, respx_mock):
        """Raises ValueError on invalid JSON from well-known."""
        domain = "invalidjson.org"
        well_known_url = f"https://{domain}/.well-known/matrix/client"

        respx_mock.get(well_known_url).mock(
            return_value=Response(200, json="Non json response")
        )

        with pytest.raises(ValueError, match="Well-known lookup failed"):
            await resolve_homeserver(domain)

    @pytest.mark.asyncio
    async def test_respects_http_schema_in_domain(self, respx_mock):
        """Respects http schema in the original domain."""
        domain = "http://example.com"
        well_known_url = "http://example.com/.well-known/matrix/client"

        respx_mock.get(well_known_url).mock(return_value=Response(404))

        assert domain == await resolve_homeserver(domain)

    @pytest.mark.asyncio
    async def test_http_error_raises_error(self, respx_mock):
        """Raises ValueError on HTTP errors when resolving homeserver."""
        domain = "raises.org"
        well_known_url = f"https://{domain}/.well-known/matrix/client"

        respx_mock.get(well_known_url).mock(side_effect=httpx.ConnectError)

        with pytest.raises(ValueError, match="Well-known lookup failed"):
            await resolve_homeserver(domain)
