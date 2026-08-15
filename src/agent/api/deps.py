import httpx
from fastapi import Header, HTTPException

from ..core.client import OneCrawlerClient


def bearer_token(authorization: str = Header(...)) -> str:
    if not authorization.lower().startswith("bearer "):
        raise HTTPException(
            status_code=401,
            detail="Expected an 'Authorization: Bearer <token>' header with your "
            "OneCrawler access token.",
        )
    return authorization.split(" ", 1)[1]


def reraise_as_http_error(exc: Exception):
    """Surface a OneCrawler API failure as the same status code instead of a
    generic 500."""
    if isinstance(exc, httpx.HTTPStatusError):
        raise HTTPException(
            status_code=exc.response.status_code, detail=exc.response.text
        ) from exc
    raise HTTPException(status_code=502, detail=str(exc)) from exc


async def verified_user(token: str) -> dict:
    """GET /api/users/me — a real, server-verified identity check. Unlike
    decoding the JWT payload ourselves, this fails if the token is
    invalid/expired rather than trusting an unverified claim."""
    try:
        return await OneCrawlerClient(token=token).get_current_user()
    except Exception as exc:
        reraise_as_http_error(exc)
