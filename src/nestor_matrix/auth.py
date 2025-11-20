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
