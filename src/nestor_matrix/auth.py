"""Matrix authentication utilities."""

from urllib.parse import urlparse

import httpx


async def resolve_homeserver(domain: str) -> str:
    """Resolve homeserver URL from domain via .well-known lookup.

    Args:
        domain: Domain like "matrix.org" or "https://matrix.org"

    Returns:
        Resolved homeserver URL (e.g. "https://matrix-client.matrix.org")
    """
    scheme = "https"
    if domain.startswith(("http://", "https://")):
        parsed_url = urlparse(domain)
        scheme = parsed_url.scheme
        domain = parsed_url.netloc

    well_known_url = f"{scheme}://{domain}/.well-known/matrix/client"

    async with httpx.AsyncClient() as client:
        try:
            resp = await client.get(well_known_url, timeout=10.0)
            if resp.status_code == 200:
                data = resp.json()
                base_url = data.get("m.homeserver", {}).get("base_url")
                if base_url:
                    return base_url.rstrip("/")
        except Exception as e:
            raise ValueError(f"Well-known lookup failed for domain: '{domain}'") from e

    # Fallback to domain
    return f"{scheme}://{domain.rstrip('/')}"


async def get_access_token(
    homeserver: str,
    username: str,
    password: str,
) -> tuple[str, str]:
    """Get access token via password login.

    Args:
        homeserver: Homeserver URL (will be resolved if needed)
        username: Full user ID (@user:domain) or localpart
        password: User password

    Returns:
        Tuple of (access_token, device_id)

    Raises:
        httpx.HTTPStatusError: On login failure
    """
    homeserver = await resolve_homeserver(homeserver)

    # Normalize username to full MXID
    if not username.startswith("@"):
        domain = urlparse(homeserver).netloc
        username = f"@{username}:{domain}"

    async with httpx.AsyncClient() as client:
        resp = await client.post(
            f"{homeserver}/_matrix/client/v3/login",
            json={
                "type": "m.login.password",
                "identifier": {"type": "m.id.user", "user": username},
                "password": password,
            },
            timeout=30.0,
        )
        resp.raise_for_status()
        data = resp.json()
        print(data)
        return data["access_token"], data["device_id"]
