# ============================================================
# Fazle API Gateway — Central entry point for Fazle system
# Routes requests to Brain, Memory, Tasks, and Tools services
# ============================================================
from fastapi import FastAPI, HTTPException, Depends, Header, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from pydantic_settings import BaseSettings
from prometheus_fastapi_instrumentator import Instrumentator
import hmac
import httpx
import logging
import os
from typing import Optional
from datetime import datetime

from schemas import (
    ChatRequest, ChatResponse,
    DecisionRequest, DecisionResponse,
    MemoryStoreRequest, MemorySearchRequest,
    KnowledgeIngestRequest,
    TaskCreateRequest,
    WebSearchRequest,
    TrainRequest,
    RegisterRequest, LoginRequest,
    TokenResponse, UserResponse, UpdateUserRequest,
)
from auth import (
    hash_password, verify_password, create_access_token,
    get_current_user, require_admin, get_optional_user,
)
from database import (
    ensure_users_table, create_user, get_user_by_email,
    get_user_by_id, list_family_members, update_user, delete_user,
    count_users, save_message, get_user_conversations,
    get_conversation_messages, get_all_conversations,
)
from audit import ensure_audit_table, log_action, get_audit_logs

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("fazle-api")

# Allowed file extensions for upload
ALLOWED_EXTENSIONS = {".pdf", ".docx", ".txt", ".png", ".jpg", ".jpeg", ".gif"}


class Settings(BaseSettings):
    api_key: str = ""
    brain_url: str = "http://fazle-brain:8200"
    memory_url: str = "http://fazle-memory:8300"
    task_url: str = "http://fazle-task-engine:8400"
    tools_url: str = "http://fazle-web-intelligence:8500"
    trainer_url: str = "http://fazle-trainer:8600"
    livekit_api_key: str = ""
    livekit_api_secret: str = ""
    livekit_url: str = "wss://livekit.iamazim.com"

    class Config:
        env_prefix = "FAZLE_"


settings = Settings()

app = FastAPI(
    title="Fazle Personal AI — API Gateway",
    version="1.0.0",
    docs_url=None,
    redoc_url=None,
)

Instrumentator().instrument(app).expose(app, endpoint="/metrics")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://iamazim.com", "https://fazle.iamazim.com"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


async def verify_api_key(x_api_key: Optional[str] = Header(None)):
    if not settings.api_key or settings.api_key == "":
        raise HTTPException(status_code=500, detail="FAZLE_API_KEY not configured")
    if x_api_key != settings.api_key:
        raise HTTPException(status_code=401, detail="Invalid API key")


async def verify_auth(
    x_api_key: Optional[str] = Header(None),
    authorization: Optional[str] = Header(None),
):
    """Accept either API key (X-API-Key header) or JWT (Authorization: Bearer)."""
    # Fail fast if API key not configured
    if not settings.api_key or not settings.api_key.strip():
        raise HTTPException(
            status_code=500,
            detail="FAZLE_API_KEY not configured on server"
        )

    # Try JWT first
    if authorization and authorization.startswith("Bearer "):
        user = await get_current_user(authorization)
        return user

    # Fall back to API key (timing-safe comparison)
    if x_api_key and hmac.compare_digest(x_api_key.strip(), settings.api_key.strip()):
        return {"id": "api-key", "email": "system", "name": "API Key", "role": "admin", "relationship_to_azim": "self"}

    if x_api_key:
        raise HTTPException(status_code=401, detail="Invalid API key")

    raise HTTPException(status_code=401, detail="Authentication required")


@app.on_event("startup")
def startup():
    try:
        ensure_users_table()
        ensure_audit_table()
        logger.info("Database tables ensured on startup")
    except Exception as e:
        logger.error(f"Failed to ensure database tables: {e}")


# ── Auth endpoints ──────────────────────────────────────────
@app.post("/auth/register", response_model=TokenResponse)
async def register(request: RegisterRequest, admin: dict = Depends(require_admin)):
    """Register a new family member. Admin only."""
    existing = get_user_by_email(request.email)
    if existing:
        raise HTTPException(status_code=409, detail="Email already registered")

    hashed = hash_password(request.password)
    user = create_user(
        email=request.email,
        hashed_password=hashed,
        name=request.name,
        relationship_to_azim=request.relationship_to_azim,
        role=request.role,
    )
    token = create_access_token({"sub": str(user["id"]), "role": user["role"], "rel": user["relationship_to_azim"]})
    log_action(admin, "register_user", target_type="user", target_id=str(user["id"]), detail=f"Registered {request.name} ({request.email}) as {request.relationship_to_azim}")
    return TokenResponse(access_token=token, user=UserResponse(**user))


@app.post("/auth/login", response_model=TokenResponse)
async def login(request: LoginRequest):
    """Log in with email and password."""
    user = get_user_by_email(request.email)
    if not user or not verify_password(request.password, user["hashed_password"]):
        raise HTTPException(status_code=401, detail="Invalid email or password")
    if not user.get("is_active", True):
        raise HTTPException(status_code=403, detail="Account is deactivated")

    token = create_access_token({"sub": str(user["id"]), "role": user["role"], "rel": user["relationship_to_azim"]})
    user_resp = {k: v for k, v in user.items() if k != "hashed_password"}
    log_action(user_resp, "login", target_type="user", target_id=str(user["id"]))
    return TokenResponse(access_token=token, user=UserResponse(**user_resp))


@app.post("/auth/setup", response_model=TokenResponse)
async def setup_admin(request: RegisterRequest):
    """Initial admin setup — only works when no users exist."""
    if count_users() > 0:
        raise HTTPException(status_code=403, detail="Setup already completed")

    hashed = hash_password(request.password)
    user = create_user(
        email=request.email,
        hashed_password=hashed,
        name=request.name,
        relationship_to_azim="self",
        role="admin",
    )
    token = create_access_token({"sub": str(user["id"]), "role": "admin", "rel": "self"})
    return TokenResponse(access_token=token, user=UserResponse(**user))


@app.get("/auth/me", response_model=UserResponse)
async def get_me(user: dict = Depends(get_current_user)):
    """Get the current authenticated user."""
    return UserResponse(**user)


@app.get("/auth/family", response_model=list[UserResponse])
async def get_family(admin: dict = Depends(require_admin)):
    """List all family members. Admin only."""
    members = list_family_members()
    return [UserResponse(**m) for m in members]


@app.put("/auth/family/{user_id}", response_model=UserResponse)
async def update_family_member(user_id: str, request: UpdateUserRequest, admin: dict = Depends(require_admin)):
    """Update a family member. Admin only."""
    updated = update_user(user_id, **request.model_dump(exclude_unset=True))
    if not updated:
        raise HTTPException(status_code=404, detail="User not found")
    log_action(admin, "update_user", target_type="user", target_id=user_id, detail=str(request.model_dump(exclude_unset=True)))
    return UserResponse(**updated)


@app.delete("/auth/family/{user_id}")
async def delete_family_member(user_id: str, admin: dict = Depends(require_admin)):
    """Delete a family member. Admin only. Cannot delete yourself."""
    if str(admin["id"]) == user_id:
        raise HTTPException(status_code=400, detail="Cannot delete your own account")
    if not delete_user(user_id):
        raise HTTPException(status_code=404, detail="User not found")
    log_action(admin, "delete_user", target_type="user", target_id=user_id)
    return {"status": "deleted"}


@app.get("/auth/setup-status")
async def setup_status():
    """Check if initial setup has been completed."""
    return {"setup_completed": count_users() > 0}


# ── Voice (LiveKit token) ──────────────────────────────────
@app.post("/fazle/voice/token")
async def voice_token(auth_user: dict = Depends(verify_auth)):
    """Generate a LiveKit access token for authenticated users."""
    if not settings.livekit_api_key or not settings.livekit_api_secret:
        raise HTTPException(status_code=503, detail="Voice service not configured")

    from livekit.api import AccessToken, VideoGrants

    user_id = str(auth_user.get("id", "anonymous"))
    user_name = auth_user.get("name", "User")
    relationship = auth_user.get("relationship_to_azim", "self")

    # Each user gets their own private room for voice chat with Azim
    room_name = f"fazle-voice-{user_id}"

    token = AccessToken(settings.livekit_api_key, settings.livekit_api_secret)
    token.with_identity(user_id)
    token.with_name(user_name)
    token.with_metadata(relationship)
    token.with_grants(VideoGrants(
        room_join=True,
        room=room_name,
        can_publish=True,
        can_subscribe=True,
    ))

    return {
        "token": token.to_jwt(),
        "url": settings.livekit_url,
        "room": room_name,
    }


# ── Health ──────────────────────────────────────────────────
@app.get("/health")
async def health():
    return {"status": "healthy", "service": "fazle-api", "timestamp": datetime.utcnow().isoformat()}


# ── Decision endpoint (Dograh integration) ──────────────────
@app.post("/fazle/decision", response_model=DecisionResponse, dependencies=[Depends(verify_auth)])
async def make_decision(request: DecisionRequest):
    """Dograh calls this endpoint to get AI decisions for voice interactions."""
    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            resp = await client.post(
                f"{settings.brain_url}/decide",
                json=request.model_dump(),
            )
            resp.raise_for_status()
            return DecisionResponse(**resp.json())
        except httpx.HTTPError as e:
            logger.error(f"Brain service error: {e}")
            raise HTTPException(status_code=502, detail="Brain service unavailable")


# ── Chat endpoint ───────────────────────────────────────────
@app.post("/fazle/chat", response_model=ChatResponse)
async def chat(
    request: ChatRequest,
    auth_user: dict = Depends(verify_auth),
):
    """Text chat with Fazle. Injects authenticated user context for persona engine."""
    body = request.model_dump()
    # Inject user context from JWT for persona-aware responses
    if isinstance(auth_user, dict) and auth_user.get("id") != "api-key":
        body["user_id"] = str(auth_user["id"])
        body["user_name"] = auth_user.get("name", "Azim")
        body["relationship"] = auth_user.get("relationship_to_azim", "self")
        body["user"] = auth_user.get("name", "Azim")
    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            resp = await client.post(
                f"{settings.brain_url}/chat",
                json=body,
            )
            resp.raise_for_status()
            data = resp.json()

            # Persist chat history to DB
            user_id = str(auth_user["id"]) if isinstance(auth_user, dict) and auth_user.get("id") != "api-key" else None
            conv_id = data.get("conversation_id", "")
            if user_id and conv_id:
                try:
                    save_message(user_id, conv_id, "user", request.message, title=request.message[:200])
                    save_message(user_id, conv_id, "assistant", data.get("reply", ""))
                except Exception as e:
                    logger.warning(f"Chat history save failed: {e}")

            return ChatResponse(**data)
        except httpx.HTTPError as e:
            logger.error(f"Brain service error: {e}")
            raise HTTPException(status_code=502, detail="Brain service unavailable")


# ── Chat history ────────────────────────────────────────────
@app.get("/fazle/conversations")
async def list_conversations(auth_user: dict = Depends(verify_auth)):
    """List conversations for the current user (admin sees all)."""
    if auth_user.get("role") == "admin":
        return {"conversations": get_all_conversations()}
    return {"conversations": get_user_conversations(str(auth_user["id"]))}


@app.get("/fazle/conversations/{conversation_id}")
async def get_conversation(conversation_id: str, auth_user: dict = Depends(verify_auth)):
    """Get messages for a specific conversation."""
    user_id = None if auth_user.get("role") == "admin" else str(auth_user["id"])
    messages = get_conversation_messages(conversation_id, user_id=user_id)
    if not messages and user_id:
        raise HTTPException(status_code=404, detail="Conversation not found")
    return {"messages": messages}


# ── Memory proxy ────────────────────────────────────────────
@app.post("/fazle/memory")
async def store_memory(request: MemoryStoreRequest, auth_user: dict = Depends(verify_auth)):
    body = request.model_dump()
    if isinstance(auth_user, dict) and auth_user.get("id") != "api-key":
        body["user_id"] = str(auth_user["id"])
    async with httpx.AsyncClient(timeout=15.0) as client:
        try:
            resp = await client.post(
                f"{settings.memory_url}/store",
                json=body,
            )
            resp.raise_for_status()
            return resp.json()
        except httpx.HTTPError as e:
            logger.error(f"Memory service error: {e}")
            raise HTTPException(status_code=502, detail="Memory service unavailable")


@app.post("/fazle/memory/search")
async def search_memory(request: MemorySearchRequest, auth_user: dict = Depends(verify_auth)):
    body = request.model_dump()
    # Non-admin users can only see their own memories
    if isinstance(auth_user, dict) and auth_user.get("id") != "api-key" and auth_user.get("role") != "admin":
        body["user_id"] = str(auth_user["id"])
    async with httpx.AsyncClient(timeout=15.0) as client:
        try:
            resp = await client.post(
                f"{settings.memory_url}/search",
                json=body,
            )
            resp.raise_for_status()
            return resp.json()
        except httpx.HTTPError as e:
            logger.error(f"Memory service error: {e}")
            raise HTTPException(status_code=502, detail="Memory service unavailable")


@app.delete("/fazle/memory/{memory_id}")
async def delete_memory(memory_id: str, auth_user: dict = Depends(verify_auth)):
    async with httpx.AsyncClient(timeout=15.0) as client:
        try:
            resp = await client.delete(
                f"{settings.memory_url}/memories/{memory_id}",
            )
            resp.raise_for_status()
            return resp.json()
        except httpx.HTTPError as e:
            logger.error(f"Memory service error: {e}")
            raise HTTPException(status_code=502, detail="Memory service unavailable")


# ── Knowledge ingestion proxy ───────────────────────────────
@app.post("/fazle/knowledge/ingest", dependencies=[Depends(verify_auth)])
async def ingest_knowledge(request: KnowledgeIngestRequest):
    async with httpx.AsyncClient(timeout=60.0) as client:
        try:
            resp = await client.post(
                f"{settings.memory_url}/ingest",
                json=request.model_dump(),
            )
            resp.raise_for_status()
            return resp.json()
        except httpx.HTTPError as e:
            logger.error(f"Memory service error: {e}")
            raise HTTPException(status_code=502, detail="Memory service unavailable")


# ── File upload ─────────────────────────────────────────────
@app.post("/fazle/files/upload")
async def upload_file(
    file: UploadFile = File(...),
    auth_user: dict = Depends(verify_auth),
):
    """Upload a file (PDF, DOCX, TXT, images) for RAG ingestion."""
    ext = os.path.splitext(file.filename or "")[1].lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"File type not allowed. Supported: {', '.join(sorted(ALLOWED_EXTENSIONS))}",
        )

    # Size guard (20MB)
    contents = await file.read()
    if len(contents) > 20 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="File too large (max 20MB)")

    user_id = str(auth_user["id"]) if isinstance(auth_user, dict) and auth_user.get("id") != "api-key" else None

    # Extract text based on file type
    text_content = ""
    if ext == ".txt":
        text_content = contents.decode("utf-8", errors="replace")
    elif ext == ".pdf":
        try:
            import io
            import PyPDF2
            reader = PyPDF2.PdfReader(io.BytesIO(contents))
            text_content = "\n".join(page.extract_text() or "" for page in reader.pages)
        except Exception as e:
            logger.warning(f"PDF extraction failed: {e}")
            text_content = f"[PDF file: {file.filename} - text extraction failed]"
    elif ext == ".docx":
        try:
            import io
            import docx
            doc = docx.Document(io.BytesIO(contents))
            text_content = "\n".join(p.text for p in doc.paragraphs)
        except Exception as e:
            logger.warning(f"DOCX extraction failed: {e}")
            text_content = f"[DOCX file: {file.filename} - text extraction failed]"
    else:
        # Image files — store metadata
        text_content = f"[Uploaded image: {file.filename}]"

    # Ingest extracted text into memory/knowledge
    if text_content.strip():
        async with httpx.AsyncClient(timeout=60.0) as client:
            try:
                body = {
                    "text": text_content[:50000],
                    "source": f"upload:{file.filename}",
                    "title": file.filename,
                }
                if user_id:
                    body["user_id"] = user_id
                await client.post(
                    f"{settings.memory_url}/ingest",
                    json=body,
                )
            except Exception as e:
                logger.warning(f"Knowledge ingest after upload failed: {e}")

    return {
        "status": "uploaded",
        "filename": file.filename,
        "size": len(contents),
        "type": ext,
        "text_extracted": bool(text_content.strip()),
    }


# ── Task proxy ──────────────────────────────────────────────
@app.post("/fazle/tasks", dependencies=[Depends(verify_auth)])
async def create_task(request: TaskCreateRequest):
    async with httpx.AsyncClient(timeout=15.0) as client:
        try:
            resp = await client.post(
                f"{settings.task_url}/tasks",
                json=request.model_dump(),
            )
            resp.raise_for_status()
            return resp.json()
        except httpx.HTTPError as e:
            logger.error(f"Task service error: {e}")
            raise HTTPException(status_code=502, detail="Task service unavailable")


@app.get("/fazle/tasks", dependencies=[Depends(verify_auth)])
async def list_tasks():
    async with httpx.AsyncClient(timeout=15.0) as client:
        try:
            resp = await client.get(f"{settings.task_url}/tasks")
            resp.raise_for_status()
            return resp.json()
        except httpx.HTTPError as e:
            logger.error(f"Task service error: {e}")
            raise HTTPException(status_code=502, detail="Task service unavailable")


# ── Web intelligence proxy ──────────────────────────────────
@app.post("/fazle/web/search", dependencies=[Depends(verify_auth)])
async def web_search(request: WebSearchRequest):
    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            resp = await client.post(
                f"{settings.tools_url}/search",
                json=request.model_dump(),
            )
            resp.raise_for_status()
            return resp.json()
        except httpx.HTTPError as e:
            logger.error(f"Web intelligence error: {e}")
            raise HTTPException(status_code=502, detail="Web intelligence service unavailable")


# ── Training proxy ──────────────────────────────────────────
@app.post("/fazle/train", dependencies=[Depends(verify_auth)])
async def train(request: TrainRequest):
    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            resp = await client.post(
                f"{settings.trainer_url}/train",
                json=request.model_dump(),
            )
            resp.raise_for_status()
            return resp.json()
        except httpx.HTTPError as e:
            logger.error(f"Trainer service error: {e}")
            raise HTTPException(status_code=502, detail="Trainer service unavailable")


# ── Service status ──────────────────────────────────────────
@app.get("/fazle/status", dependencies=[Depends(verify_auth)])
async def system_status():
    services = {
        "brain": settings.brain_url,
        "memory": settings.memory_url,
        "tasks": settings.task_url,
        "tools": settings.tools_url,
        "trainer": settings.trainer_url,
    }
    results = {}
    async with httpx.AsyncClient(timeout=5.0) as client:
        for name, url in services.items():
            try:
                resp = await client.get(f"{url}/health")
                results[name] = "healthy" if resp.status_code == 200 else "unhealthy"
            except Exception:
                results[name] = "unreachable"
    return {"services": results, "timestamp": datetime.utcnow().isoformat()}


# ── Audit log (admin only) ─────────────────────────────────
@app.get("/fazle/audit")
async def view_audit_log(
    limit: int = 100,
    action: Optional[str] = None,
    admin: dict = Depends(require_admin),
):
    """View audit trail. Admin only."""
    logs = get_audit_logs(limit=min(limit, 500), action_filter=action)
    return {"logs": logs}
