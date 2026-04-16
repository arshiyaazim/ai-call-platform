# ============================================================
# Fazle API — WBOM Proxy Routes (authenticated)
# All WBOM requests flow through here for admin-only access
# ============================================================
from fastapi import APIRouter, Depends, Request, Response
import httpx
import logging

from auth import require_admin

logger = logging.getLogger("fazle-api")

router = APIRouter(prefix="/fazle/wbom", tags=["wbom"])


def _get_wbom_url() -> str:
    from main import settings
    return settings.wbom_url


@router.api_route("/{path:path}", methods=["GET", "POST", "PUT", "DELETE", "PATCH"])
async def wbom_proxy(path: str, request: Request, _user: dict = Depends(require_admin)):
    """Authenticated catch-all proxy to the WBOM microservice."""
    wbom_url = _get_wbom_url()
    target = f"{wbom_url}/api/wbom/{path}"
    if request.url.query:
        target += f"?{request.url.query}"

    body = await request.body()
    headers = {
        "content-type": request.headers.get("content-type", "application/json"),
        "accept": request.headers.get("accept", "application/json"),
    }

    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            resp = await client.request(
                method=request.method,
                url=target,
                content=body if body else None,
                headers=headers,
            )
            return Response(
                content=resp.content,
                status_code=resp.status_code,
                media_type=resp.headers.get("content-type", "application/json"),
            )
        except httpx.HTTPError as e:
            logger.error(f"WBOM proxy error [{request.method} /{path}]: {e}")
            return Response(
                content=b'{"status":"fallback","detail":"WBOM service unavailable"}',
                status_code=502,
                media_type="application/json",
            )
