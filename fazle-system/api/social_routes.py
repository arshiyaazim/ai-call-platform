# ============================================================
# Fazle API — Social Engine Proxy Routes
# WhatsApp + Facebook automation via Social Engine microservice
# ============================================================
from fastapi import APIRouter, Depends, HTTPException, Query
import httpx
import logging
from typing import Optional

from auth import require_admin, get_current_user
from audit import log_action

logger = logging.getLogger("fazle-api")

router = APIRouter(prefix="/fazle/social", tags=["social"])


def _get_settings():
    from main import settings
    return settings


# ── WhatsApp ────────────────────────────────────────────────

@router.post("/whatsapp/send")
async def whatsapp_send(body: dict, user: dict = Depends(require_admin)):
    """Send a WhatsApp message."""
    settings = _get_settings()
    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            resp = await client.post(f"{settings.social_engine_url}/whatsapp/send", json=body)
            resp.raise_for_status()
            log_action(user, "whatsapp_send", target_type="social", detail=body.get("to", ""))
            return resp.json()
        except httpx.HTTPError as e:
            logger.error(f"Social engine WhatsApp send error: {e}")
            raise HTTPException(status_code=502, detail="Social engine unavailable")


@router.post("/whatsapp/schedule")
async def whatsapp_schedule(body: dict, user: dict = Depends(require_admin)):
    """Schedule a WhatsApp message."""
    settings = _get_settings()
    async with httpx.AsyncClient(timeout=15.0) as client:
        try:
            resp = await client.post(f"{settings.social_engine_url}/whatsapp/schedule", json=body)
            resp.raise_for_status()
            log_action(user, "whatsapp_schedule", target_type="social")
            return resp.json()
        except httpx.HTTPError as e:
            logger.error(f"Social engine WhatsApp schedule error: {e}")
            raise HTTPException(status_code=502, detail="Social engine unavailable")


@router.post("/whatsapp/broadcast")
async def whatsapp_broadcast(body: dict, user: dict = Depends(require_admin)):
    """Broadcast a message to multiple WhatsApp contacts."""
    settings = _get_settings()
    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            resp = await client.post(f"{settings.social_engine_url}/whatsapp/broadcast", json=body)
            resp.raise_for_status()
            log_action(user, "whatsapp_broadcast", target_type="social")
            return resp.json()
        except httpx.HTTPError as e:
            logger.error(f"Social engine WhatsApp broadcast error: {e}")
            raise HTTPException(status_code=502, detail="Social engine unavailable")


@router.get("/whatsapp/messages")
async def whatsapp_messages(limit: int = Query(50, ge=1, le=200), user: dict = Depends(require_admin)):
    """Get recent WhatsApp messages."""
    settings = _get_settings()
    async with httpx.AsyncClient(timeout=10.0) as client:
        try:
            resp = await client.get(f"{settings.social_engine_url}/whatsapp/messages", params={"limit": limit})
            resp.raise_for_status()
            return resp.json()
        except httpx.HTTPError as e:
            logger.error(f"Social engine WhatsApp messages error: {e}")
            raise HTTPException(status_code=502, detail="Social engine unavailable")


@router.get("/whatsapp/scheduled")
async def whatsapp_scheduled(user: dict = Depends(require_admin)):
    """Get scheduled WhatsApp messages."""
    settings = _get_settings()
    async with httpx.AsyncClient(timeout=10.0) as client:
        try:
            resp = await client.get(f"{settings.social_engine_url}/whatsapp/scheduled")
            resp.raise_for_status()
            return resp.json()
        except httpx.HTTPError as e:
            logger.error(f"Social engine WhatsApp scheduled error: {e}")
            raise HTTPException(status_code=502, detail="Social engine unavailable")


# ── Facebook ───────────────────────────────────────────────

@router.post("/facebook/post")
async def facebook_post(body: dict, user: dict = Depends(require_admin)):
    """Create or schedule a Facebook post."""
    settings = _get_settings()
    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            resp = await client.post(f"{settings.social_engine_url}/facebook/post", json=body)
            resp.raise_for_status()
            log_action(user, "facebook_post", target_type="social")
            return resp.json()
        except httpx.HTTPError as e:
            logger.error(f"Social engine Facebook post error: {e}")
            raise HTTPException(status_code=502, detail="Social engine unavailable")


@router.post("/facebook/comment")
async def facebook_comment(body: dict, user: dict = Depends(require_admin)):
    """Reply to a Facebook comment."""
    settings = _get_settings()
    async with httpx.AsyncClient(timeout=15.0) as client:
        try:
            resp = await client.post(f"{settings.social_engine_url}/facebook/comment", json=body)
            resp.raise_for_status()
            log_action(user, "facebook_comment", target_type="social")
            return resp.json()
        except httpx.HTTPError as e:
            logger.error(f"Social engine Facebook comment error: {e}")
            raise HTTPException(status_code=502, detail="Social engine unavailable")


@router.post("/facebook/react")
async def facebook_react(body: dict, user: dict = Depends(require_admin)):
    """React to a Facebook post or comment."""
    settings = _get_settings()
    async with httpx.AsyncClient(timeout=10.0) as client:
        try:
            resp = await client.post(f"{settings.social_engine_url}/facebook/react", json=body)
            resp.raise_for_status()
            return resp.json()
        except httpx.HTTPError as e:
            logger.error(f"Social engine Facebook react error: {e}")
            raise HTTPException(status_code=502, detail="Social engine unavailable")


@router.get("/facebook/posts")
async def facebook_posts(limit: int = Query(50, ge=1, le=200), user: dict = Depends(require_admin)):
    """Get recent Facebook posts."""
    settings = _get_settings()
    async with httpx.AsyncClient(timeout=10.0) as client:
        try:
            resp = await client.get(f"{settings.social_engine_url}/facebook/posts", params={"limit": limit})
            resp.raise_for_status()
            return resp.json()
        except httpx.HTTPError as e:
            logger.error(f"Social engine Facebook posts error: {e}")
            raise HTTPException(status_code=502, detail="Social engine unavailable")


@router.get("/facebook/scheduled")
async def facebook_scheduled(user: dict = Depends(require_admin)):
    """Get scheduled Facebook posts."""
    settings = _get_settings()
    async with httpx.AsyncClient(timeout=10.0) as client:
        try:
            resp = await client.get(f"{settings.social_engine_url}/facebook/scheduled")
            resp.raise_for_status()
            return resp.json()
        except httpx.HTTPError as e:
            logger.error(f"Social engine Facebook scheduled error: {e}")
            raise HTTPException(status_code=502, detail="Social engine unavailable")


# ── Contacts ───────────────────────────────────────────────

@router.get("/contacts")
async def list_contacts(
    platform: Optional[str] = Query(None, pattern=r"^(whatsapp|facebook)$"),
    user: dict = Depends(require_admin),
):
    """List social contacts."""
    settings = _get_settings()
    async with httpx.AsyncClient(timeout=10.0) as client:
        try:
            params = {}
            if platform:
                params["platform"] = platform
            resp = await client.get(f"{settings.social_engine_url}/contacts", params=params)
            resp.raise_for_status()
            return resp.json()
        except httpx.HTTPError as e:
            logger.error(f"Social engine contacts error: {e}")
            raise HTTPException(status_code=502, detail="Social engine unavailable")


@router.post("/contacts")
async def add_contact(body: dict, user: dict = Depends(require_admin)):
    """Add a social contact."""
    settings = _get_settings()
    async with httpx.AsyncClient(timeout=10.0) as client:
        try:
            resp = await client.post(f"{settings.social_engine_url}/contacts", json=body)
            resp.raise_for_status()
            log_action(user, "add_contact", target_type="social")
            return resp.json()
        except httpx.HTTPError as e:
            logger.error(f"Social engine add contact error: {e}")
            raise HTTPException(status_code=502, detail="Social engine unavailable")


# ── Campaigns ──────────────────────────────────────────────

@router.get("/campaigns")
async def list_campaigns(user: dict = Depends(require_admin)):
    """List social campaigns."""
    settings = _get_settings()
    async with httpx.AsyncClient(timeout=10.0) as client:
        try:
            resp = await client.get(f"{settings.social_engine_url}/campaigns")
            resp.raise_for_status()
            return resp.json()
        except httpx.HTTPError as e:
            logger.error(f"Social engine campaigns error: {e}")
            raise HTTPException(status_code=502, detail="Social engine unavailable")


@router.post("/campaigns")
async def create_campaign(body: dict, user: dict = Depends(require_admin)):
    """Create a social campaign."""
    settings = _get_settings()
    async with httpx.AsyncClient(timeout=15.0) as client:
        try:
            resp = await client.post(f"{settings.social_engine_url}/campaigns", json=body)
            resp.raise_for_status()
            log_action(user, "create_campaign", target_type="social")
            return resp.json()
        except httpx.HTTPError as e:
            logger.error(f"Social engine create campaign error: {e}")
            raise HTTPException(status_code=502, detail="Social engine unavailable")


# ── Stats ──────────────────────────────────────────────────

@router.get("/stats")
async def social_stats(user: dict = Depends(require_admin)):
    """Get social engine stats."""
    settings = _get_settings()
    async with httpx.AsyncClient(timeout=10.0) as client:
        try:
            resp = await client.get(f"{settings.social_engine_url}/stats")
            resp.raise_for_status()
            return resp.json()
        except httpx.HTTPError as e:
            logger.error(f"Social engine stats error: {e}")
            raise HTTPException(status_code=502, detail="Social engine unavailable")
