# ============================================================
# Fazle Social Engine — WhatsApp + Facebook Automation
# Microservice for social media interactions with AI persona
# ============================================================
from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings
import httpx
import logging
import uuid
from datetime import datetime, timezone
from typing import Optional
from contextlib import contextmanager

import psycopg2
import psycopg2.extras
import psycopg2.pool

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("fazle-social-engine")

psycopg2.extras.register_uuid()


class Settings(BaseSettings):
    database_url: str = "postgresql://postgres:postgres@postgres:5432/postgres"
    brain_url: str = "http://fazle-brain:8200"
    redis_url: str = "redis://redis:6379/5"
    whatsapp_api_url: str = ""
    whatsapp_api_token: str = ""
    whatsapp_phone_number_id: str = ""
    facebook_page_access_token: str = ""
    facebook_page_id: str = ""

    class Config:
        env_prefix = "SOCIAL_"


settings = Settings()

app = FastAPI(title="Fazle Social Engine", version="1.0.0", docs_url=None, redoc_url=None)

# ── Database ────────────────────────────────────────────────
_pool = None


def _get_pool():
    global _pool
    if _pool is None:
        _pool = psycopg2.pool.ThreadedConnectionPool(2, 10, settings.database_url)
    return _pool


@contextmanager
def _get_conn():
    pool = _get_pool()
    conn = pool.getconn()
    try:
        yield conn
    finally:
        pool.putconn(conn)


def ensure_tables():
    with _get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS fazle_social_contacts (
                    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                    name VARCHAR(200) NOT NULL,
                    platform VARCHAR(20) NOT NULL,
                    identifier VARCHAR(200) NOT NULL,
                    metadata JSONB DEFAULT '{}',
                    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                );
                CREATE INDEX IF NOT EXISTS idx_social_contacts_platform
                    ON fazle_social_contacts (platform);
                CREATE INDEX IF NOT EXISTS idx_social_contacts_identifier
                    ON fazle_social_contacts (identifier);

                CREATE TABLE IF NOT EXISTS fazle_social_messages (
                    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                    platform VARCHAR(20) NOT NULL,
                    direction VARCHAR(10) NOT NULL,
                    contact_id UUID REFERENCES fazle_social_contacts(id) ON DELETE SET NULL,
                    contact_identifier VARCHAR(200),
                    content TEXT NOT NULL,
                    metadata JSONB DEFAULT '{}',
                    status VARCHAR(20) DEFAULT 'sent',
                    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                );
                CREATE INDEX IF NOT EXISTS idx_social_messages_platform
                    ON fazle_social_messages (platform);
                CREATE INDEX IF NOT EXISTS idx_social_messages_created
                    ON fazle_social_messages (created_at DESC);

                CREATE TABLE IF NOT EXISTS fazle_social_scheduled (
                    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                    platform VARCHAR(20) NOT NULL,
                    action_type VARCHAR(50) NOT NULL,
                    payload JSONB NOT NULL DEFAULT '{}',
                    scheduled_at TIMESTAMPTZ NOT NULL,
                    status VARCHAR(20) DEFAULT 'pending',
                    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                );
                CREATE INDEX IF NOT EXISTS idx_social_scheduled_status
                    ON fazle_social_scheduled (status, scheduled_at);

                CREATE TABLE IF NOT EXISTS fazle_social_campaigns (
                    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                    name VARCHAR(200) NOT NULL,
                    platform VARCHAR(20) NOT NULL,
                    campaign_type VARCHAR(50) NOT NULL,
                    config JSONB NOT NULL DEFAULT '{}',
                    status VARCHAR(20) DEFAULT 'draft',
                    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                );

                CREATE TABLE IF NOT EXISTS fazle_social_posts (
                    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                    platform VARCHAR(20) NOT NULL DEFAULT 'facebook',
                    post_id VARCHAR(200),
                    content TEXT NOT NULL,
                    image_url TEXT,
                    status VARCHAR(20) DEFAULT 'published',
                    metadata JSONB DEFAULT '{}',
                    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                );
                CREATE INDEX IF NOT EXISTS idx_social_posts_platform
                    ON fazle_social_posts (platform, created_at DESC);
            """)
        conn.commit()
    logger.info("Social engine tables ensured")


@app.on_event("startup")
def startup():
    try:
        ensure_tables()
    except Exception as e:
        logger.error(f"Database init failed: {e}")


@app.get("/health")
async def health():
    return {"status": "healthy", "service": "fazle-social-engine", "timestamp": datetime.utcnow().isoformat()}


# ── Brain integration ──────────────────────────────────────
async def generate_ai_reply(message: str, context: str = "") -> str:
    """Use Fazle Brain to generate a persona-aware response."""
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(
                f"{settings.brain_url}/chat",
                json={
                    "message": message,
                    "user": "Social Bot",
                    "conversation_id": f"social-{uuid.uuid4().hex[:8]}",
                    "context": context,
                },
            )
            if resp.status_code == 200:
                return resp.json().get("reply", "")
    except Exception as e:
        logger.error(f"Brain AI reply failed: {e}")
    return ""


# ── WhatsApp endpoints ─────────────────────────────────────

@app.post("/whatsapp/send")
async def whatsapp_send(body: dict):
    """Send a WhatsApp message. If auto_reply=true, generate AI reply first."""
    to = body.get("to", "")
    message = body.get("message", "")
    auto_reply = body.get("auto_reply", False)

    if not to or not message:
        raise HTTPException(status_code=400, detail="'to' and 'message' are required")

    # If auto_reply, use Brain to generate response
    if auto_reply:
        ai_reply = await generate_ai_reply(message)
        if ai_reply:
            message = ai_reply

    # Store message in DB
    with _get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """INSERT INTO fazle_social_messages (platform, direction, contact_identifier, content, metadata, status)
                   VALUES ('whatsapp', 'outgoing', %s, %s, %s, 'queued')""",
                (to, message, psycopg2.extras.Json(body.get("metadata", {}))),
            )
        conn.commit()

    # Send via WhatsApp Business API if configured
    sent = False
    if settings.whatsapp_api_url and settings.whatsapp_api_token:
        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                resp = await client.post(
                    f"{settings.whatsapp_api_url}/{settings.whatsapp_phone_number_id}/messages",
                    headers={"Authorization": f"Bearer {settings.whatsapp_api_token}"},
                    json={
                        "messaging_product": "whatsapp",
                        "to": to,
                        "type": "text",
                        "text": {"body": message},
                    },
                )
                sent = resp.status_code == 200
        except Exception as e:
            logger.error(f"WhatsApp API send failed: {e}")

    return {"status": "sent" if sent else "queued", "to": to, "message": message}


@app.post("/whatsapp/schedule")
async def whatsapp_schedule(body: dict):
    """Schedule a WhatsApp message for later."""
    scheduled_at = body.get("scheduled_at")
    if not scheduled_at:
        raise HTTPException(status_code=400, detail="'scheduled_at' is required")

    with _get_conn() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                """INSERT INTO fazle_social_scheduled
                   (platform, action_type, payload, scheduled_at)
                   VALUES ('whatsapp', 'send', %s, %s)
                   RETURNING id, scheduled_at, status""",
                (psycopg2.extras.Json(body), scheduled_at),
            )
            conn.commit()
            row = dict(cur.fetchone())
            row["id"] = str(row["id"])

    return {"status": "scheduled", **row}


@app.post("/whatsapp/broadcast")
async def whatsapp_broadcast(body: dict):
    """Broadcast a message to multiple contacts."""
    contacts = body.get("contacts", [])
    message = body.get("message", "")

    if not contacts or not message:
        raise HTTPException(status_code=400, detail="'contacts' and 'message' are required")

    # Store as campaign
    with _get_conn() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                """INSERT INTO fazle_social_campaigns
                   (name, platform, campaign_type, config, status)
                   VALUES (%s, 'whatsapp', 'broadcast', %s, 'running')
                   RETURNING id""",
                (body.get("name", f"Broadcast {datetime.utcnow().strftime('%Y-%m-%d')}"),
                 psycopg2.extras.Json({"contacts": contacts, "message": message})),
            )
            conn.commit()
            campaign_id = str(cur.fetchone()["id"])

    return {"status": "broadcast_queued", "campaign_id": campaign_id, "contact_count": len(contacts)}


@app.get("/whatsapp/messages")
async def whatsapp_messages(limit: int = 50):
    with _get_conn() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                """SELECT id, direction, contact_identifier, content, status, created_at
                   FROM fazle_social_messages
                   WHERE platform = 'whatsapp'
                   ORDER BY created_at DESC LIMIT %s""",
                (limit,),
            )
            messages = [dict(r) for r in cur.fetchall()]
            for m in messages:
                m["id"] = str(m["id"])
    return {"messages": messages}


@app.get("/whatsapp/scheduled")
async def whatsapp_scheduled():
    with _get_conn() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                """SELECT id, action_type, payload, scheduled_at, status, created_at
                   FROM fazle_social_scheduled
                   WHERE platform = 'whatsapp' AND status = 'pending'
                   ORDER BY scheduled_at""",
            )
            scheduled = [dict(r) for r in cur.fetchall()]
            for s in scheduled:
                s["id"] = str(s["id"])
    return {"scheduled": scheduled}


# ── Facebook endpoints ─────────────────────────────────────

@app.post("/facebook/post")
async def facebook_post(body: dict):
    """Create or schedule a Facebook post. If ai_generate=true, use Brain."""
    content = body.get("content", "")
    ai_generate = body.get("ai_generate", False)
    schedule_at = body.get("schedule_at")

    if ai_generate:
        prompt = body.get("prompt", "Create an engaging social media post")
        content = await generate_ai_reply(prompt, context="Facebook post generation")
        if not content:
            content = body.get("content", "")

    if not content:
        raise HTTPException(status_code=400, detail="Content is required")

    if schedule_at:
        # Schedule the post
        with _get_conn() as conn:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute(
                    """INSERT INTO fazle_social_scheduled
                       (platform, action_type, payload, scheduled_at)
                       VALUES ('facebook', 'post', %s, %s)
                       RETURNING id, scheduled_at, status""",
                    (psycopg2.extras.Json({"content": content, "image_url": body.get("image_url")}), schedule_at),
                )
                conn.commit()
                row = dict(cur.fetchone())
                row["id"] = str(row["id"])
        return {"status": "scheduled", **row}

    # Post immediately via Graph API if configured
    post_id = None
    if settings.facebook_page_access_token and settings.facebook_page_id:
        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                payload = {"message": content, "access_token": settings.facebook_page_access_token}
                if body.get("image_url"):
                    payload["url"] = body["image_url"]
                    endpoint = f"https://graph.facebook.com/v19.0/{settings.facebook_page_id}/photos"
                else:
                    endpoint = f"https://graph.facebook.com/v19.0/{settings.facebook_page_id}/feed"
                resp = await client.post(endpoint, data=payload)
                if resp.status_code == 200:
                    post_id = resp.json().get("id")
        except Exception as e:
            logger.error(f"Facebook API post failed: {e}")

    # Store in DB
    with _get_conn() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                """INSERT INTO fazle_social_posts (platform, post_id, content, image_url, status)
                   VALUES ('facebook', %s, %s, %s, %s)
                   RETURNING id""",
                (post_id, content, body.get("image_url"), "published" if post_id else "draft"),
            )
            conn.commit()
            db_id = str(cur.fetchone()["id"])

    return {"status": "published" if post_id else "draft", "id": db_id, "post_id": post_id, "content": content}


@app.post("/facebook/comment")
async def facebook_comment(body: dict):
    """Reply to a Facebook comment. If auto_reply=true, use Brain."""
    post_id = body.get("post_id", "")
    comment_id = body.get("comment_id", "")
    message = body.get("message", "")
    auto_reply = body.get("auto_reply", False)

    if not (post_id or comment_id):
        raise HTTPException(status_code=400, detail="'post_id' or 'comment_id' required")

    if auto_reply and body.get("original_comment"):
        message = await generate_ai_reply(
            body["original_comment"],
            context="Facebook comment reply. Be brief, friendly, and engaging."
        )

    if not message:
        raise HTTPException(status_code=400, detail="Message is required")

    sent = False
    target = comment_id or post_id
    if settings.facebook_page_access_token:
        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                resp = await client.post(
                    f"https://graph.facebook.com/v19.0/{target}/comments",
                    data={"message": message, "access_token": settings.facebook_page_access_token},
                )
                sent = resp.status_code == 200
        except Exception as e:
            logger.error(f"Facebook comment API failed: {e}")

    return {"status": "sent" if sent else "queued", "target": target, "message": message}


@app.post("/facebook/react")
async def facebook_react(body: dict):
    """React to a Facebook post or comment."""
    target_id = body.get("target_id", "")
    reaction_type = body.get("reaction_type", "LIKE")

    if not target_id:
        raise HTTPException(status_code=400, detail="'target_id' is required")

    valid_reactions = {"LIKE", "LOVE", "HAHA", "WOW", "SAD", "ANGRY"}
    if reaction_type.upper() not in valid_reactions:
        raise HTTPException(status_code=400, detail=f"Invalid reaction. Must be one of: {', '.join(valid_reactions)}")

    sent = False
    if settings.facebook_page_access_token:
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.post(
                    f"https://graph.facebook.com/v19.0/{target_id}/reactions",
                    data={"type": reaction_type.upper(), "access_token": settings.facebook_page_access_token},
                )
                sent = resp.status_code == 200
        except Exception as e:
            logger.error(f"Facebook react API failed: {e}")

    return {"status": "sent" if sent else "queued", "target_id": target_id, "reaction": reaction_type}


@app.get("/facebook/posts")
async def facebook_posts(limit: int = 50):
    with _get_conn() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                """SELECT id, post_id, content, image_url, status, created_at
                   FROM fazle_social_posts
                   WHERE platform = 'facebook'
                   ORDER BY created_at DESC LIMIT %s""",
                (limit,),
            )
            posts = [dict(r) for r in cur.fetchall()]
            for p in posts:
                p["id"] = str(p["id"])
    return {"posts": posts}


@app.get("/facebook/scheduled")
async def facebook_scheduled():
    with _get_conn() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                """SELECT id, action_type, payload, scheduled_at, status, created_at
                   FROM fazle_social_scheduled
                   WHERE platform = 'facebook' AND status = 'pending'
                   ORDER BY scheduled_at""",
            )
            scheduled = [dict(r) for r in cur.fetchall()]
            for s in scheduled:
                s["id"] = str(s["id"])
    return {"scheduled": scheduled}


# ── Contacts ───────────────────────────────────────────────

@app.get("/contacts")
async def list_contacts(platform: Optional[str] = None):
    with _get_conn() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            if platform:
                cur.execute(
                    "SELECT * FROM fazle_social_contacts WHERE platform = %s ORDER BY name",
                    (platform,),
                )
            else:
                cur.execute("SELECT * FROM fazle_social_contacts ORDER BY name")
            contacts = [dict(r) for r in cur.fetchall()]
            for c in contacts:
                c["id"] = str(c["id"])
    return {"contacts": contacts}


@app.post("/contacts")
async def add_contact(body: dict):
    name = body.get("name", "")
    platform = body.get("platform", "")
    identifier = body.get("identifier", "")

    if not name or not platform or not identifier:
        raise HTTPException(status_code=400, detail="'name', 'platform', 'identifier' are required")

    if platform not in ("whatsapp", "facebook"):
        raise HTTPException(status_code=400, detail="Platform must be 'whatsapp' or 'facebook'")

    with _get_conn() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                """INSERT INTO fazle_social_contacts (name, platform, identifier, metadata)
                   VALUES (%s, %s, %s, %s)
                   RETURNING id, name, platform, identifier""",
                (name, platform, identifier, psycopg2.extras.Json(body.get("metadata", {}))),
            )
            conn.commit()
            contact = dict(cur.fetchone())
            contact["id"] = str(contact["id"])

    return {"status": "created", "contact": contact}


# ── Campaigns ──────────────────────────────────────────────

@app.get("/campaigns")
async def list_campaigns():
    with _get_conn() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                "SELECT * FROM fazle_social_campaigns ORDER BY created_at DESC"
            )
            campaigns = [dict(r) for r in cur.fetchall()]
            for c in campaigns:
                c["id"] = str(c["id"])
    return {"campaigns": campaigns}


@app.post("/campaigns")
async def create_campaign(body: dict):
    name = body.get("name", "")
    platform = body.get("platform", "")
    campaign_type = body.get("campaign_type", "broadcast")

    if not name or not platform:
        raise HTTPException(status_code=400, detail="'name' and 'platform' are required")

    with _get_conn() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                """INSERT INTO fazle_social_campaigns (name, platform, campaign_type, config)
                   VALUES (%s, %s, %s, %s)
                   RETURNING id, name, platform, campaign_type, status""",
                (name, platform, campaign_type, psycopg2.extras.Json(body.get("config", {}))),
            )
            conn.commit()
            campaign = dict(cur.fetchone())
            campaign["id"] = str(campaign["id"])

    return {"status": "created", "campaign": campaign}


# ── Stats ──────────────────────────────────────────────────

@app.get("/stats")
async def social_stats():
    with _get_conn() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute("SELECT COUNT(*) as total FROM fazle_social_contacts")
            total_contacts = cur.fetchone()["total"]

            cur.execute("SELECT COUNT(*) as total FROM fazle_social_messages WHERE platform = 'whatsapp'")
            whatsapp_messages = cur.fetchone()["total"]

            cur.execute("SELECT COUNT(*) as total FROM fazle_social_posts WHERE platform = 'facebook'")
            facebook_posts = cur.fetchone()["total"]

            cur.execute("SELECT COUNT(*) as total FROM fazle_social_scheduled WHERE status = 'pending'")
            pending_scheduled = cur.fetchone()["total"]

            cur.execute("SELECT COUNT(*) as total FROM fazle_social_campaigns WHERE status = 'running'")
            active_campaigns = cur.fetchone()["total"]

    return {
        "total_contacts": total_contacts,
        "whatsapp_messages": whatsapp_messages,
        "facebook_posts": facebook_posts,
        "pending_scheduled": pending_scheduled,
        "active_campaigns": active_campaigns,
    }
