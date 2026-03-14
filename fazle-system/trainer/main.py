# ============================================================
# Fazle Trainer — Voice training and preference learning
# Extracts knowledge from conversations to improve Fazle
# ============================================================
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings
import httpx
import os
import json
import logging
import re
import uuid
from typing import Optional
from datetime import datetime

import redis

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("fazle-trainer")


class Settings(BaseSettings):
    openai_api_key: str = ""
    ollama_url: str = "http://ollama:11434"
    llm_provider: str = "openai"
    llm_model: str = "gpt-4o"
    ollama_model: str = "llama3.1"
    memory_url: str = "http://fazle-memory:8300"
    redis_url: str = "redis://redis:6379/2"
    llm_gateway_url: str = "http://fazle-llm-gateway:8800"
    use_llm_gateway: bool = True

    class Config:
        env_prefix = ""


settings = Settings()

_redis: Optional[redis.Redis] = None

def _get_redis() -> redis.Redis:
    global _redis
    if _redis is None:
        _redis = redis.Redis.from_url(settings.redis_url, decode_responses=True)
    return _redis


# ── PII Redaction ───────────────────────────────────────────
_PII_PATTERNS = [
    # Email addresses
    (re.compile(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'), '[EMAIL_REDACTED]'),
    # US phone numbers: (xxx) xxx-xxxx, xxx-xxx-xxxx, +1xxxxxxxxxx, etc.
    (re.compile(r'(?:\+?1[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}\b'), '[PHONE_REDACTED]'),
    # SSN: xxx-xx-xxxx
    (re.compile(r'\b\d{3}-\d{2}-\d{4}\b'), '[SSN_REDACTED]'),
    # Credit card numbers: 13-19 digit sequences with optional separators
    (re.compile(r'\b(?:\d[-.\s]?){13,19}\b'), '[CARD_REDACTED]'),
]


def redact_pii(text: str) -> str:
    """Strip or mask common PII patterns (email, phone, SSN, credit card) from text."""
    for pattern, replacement in _PII_PATTERNS:
        text = pattern.sub(replacement, text)
    return text


app = FastAPI(title="Fazle Trainer — Learning & Preference Extraction", version="1.0.0")

ALLOWED_ORIGINS = os.getenv("ALLOWED_ORIGINS", "https://fazle.iamazim.com,https://iamazim.com,http://localhost:3020").split(",")

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_methods=["*"],
    allow_headers=["*"],
)

REDIS_SESSION_PREFIX = "trainer:session:"

EXTRACTION_PROMPT = """You are an AI that extracts structured knowledge from conversations.

Given a conversation transcript, extract:
1. Personal preferences (e.g., "prefers meetings after 10 AM")
2. Contact information (e.g., "Rahim is a business partner")
3. Behavioral patterns (e.g., "usually declines cold calls")
4. Routines (e.g., "works out every morning at 7 AM")
5. Important facts (e.g., "has a meeting with investors on Friday")

Respond in JSON with:
{
  "extractions": [
    {
      "type": "preference|contact|personal|knowledge",
      "text": "human-readable description",
      "content": { "key": "value pairs of structured data" },
      "confidence": 0.0 to 1.0
    }
  ],
  "summary": "brief summary of what was learned"
}
"""


async def query_llm(messages: list[dict]) -> dict:
    """Call LLM for knowledge extraction — gateway first, direct fallback."""
    if settings.use_llm_gateway:
        try:
            async with httpx.AsyncClient(timeout=120.0) as client:
                resp = await client.post(
                    f"{settings.llm_gateway_url}/generate",
                    json={
                        "messages": messages,
                        "response_format": "json",
                        "caller": "fazle-trainer",
                        "temperature": 0.3,
                    },
                )
                resp.raise_for_status()
                return json.loads(resp.json()["content"])
        except Exception as e:
            logger.warning(f"LLM Gateway unavailable, falling back to direct: {e}")

    # Direct fallback
    if settings.llm_provider == "ollama":
        async with httpx.AsyncClient(timeout=120.0) as client:
            resp = await client.post(
                f"{settings.ollama_url}/api/chat",
                json={"model": settings.ollama_model, "messages": messages, "stream": False, "format": "json"},
            )
            resp.raise_for_status()
            return json.loads(resp.json()["message"]["content"])

    async with httpx.AsyncClient(timeout=60.0) as client:
        resp = await client.post(
            "https://api.openai.com/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {settings.openai_api_key}",
                "Content-Type": "application/json",
            },
            json={
                "model": settings.llm_model,
                "messages": messages,
                "temperature": 0.3,
                "response_format": {"type": "json_object"},
            },
        )
        resp.raise_for_status()
        return json.loads(resp.json()["choices"][0]["message"]["content"])


# ── Health ──────────────────────────────────────────────────
@app.get("/health")
async def health():
    return {"status": "healthy", "service": "fazle-trainer", "timestamp": datetime.utcnow().isoformat()}


# ── Train from transcript ──────────────────────────────────
class TrainRequest(BaseModel):
    transcript: str
    user: str = "Azim"
    session_type: str = "conversation"  # conversation, teaching, correction


@app.post("/train")
async def train(request: TrainRequest):
    """Extract knowledge from a conversation transcript and store in memory."""
    if not request.transcript.strip():
        raise HTTPException(status_code=400, detail="Transcript cannot be empty")

    session_id = str(uuid.uuid4())

    messages = [
        {"role": "system", "content": EXTRACTION_PROMPT},
        {
            "role": "user",
            "content": (
                f"Session type: {request.session_type}\n"
                f"User: {request.user}\n\n"
                f"Transcript:\n{request.transcript}"
            ),
        },
    ]

    try:
        result = await query_llm(messages)
    except Exception as e:
        logger.error(f"LLM extraction failed: {e}")
        raise HTTPException(status_code=502, detail="LLM service unavailable")

    extractions = result.get("extractions", [])
    summary = result.get("summary", "")
    stored_count = 0

    # Store extracted knowledge in memory
    async with httpx.AsyncClient(timeout=15.0) as client:
        for extraction in extractions:
            if extraction.get("confidence", 0) < 0.5:
                continue
            # Redact PII before storing
            extraction_text = redact_pii(extraction.get("text", ""))
            extraction_content = {
                k: redact_pii(v) if isinstance(v, str) else v
                for k, v in extraction.get("content", {}).items()
            }
            try:
                await client.post(
                    f"{settings.memory_url}/store",
                    json={
                        "type": extraction.get("type", "personal"),
                        "user": request.user,
                        "content": extraction_content,
                        "text": extraction_text,
                    },
                )
                stored_count += 1
            except Exception as e:
                logger.warning(f"Failed to store extraction: {e}")

    session = {
        "id": session_id,
        "user": request.user,
        "session_type": request.session_type,
        "extractions": extractions,
        "summary": summary,
        "stored_count": stored_count,
        "created_at": datetime.utcnow().isoformat(),
    }
    _get_redis().set(f"{REDIS_SESSION_PREFIX}{session_id}", json.dumps(session), ex=86400 * 30)

    return session


# ── List training sessions ─────────────────────────────────
@app.get("/sessions")
async def list_sessions(limit: int = 20):
    """List recent training sessions."""
    r = _get_redis()
    keys = r.keys(f"{REDIS_SESSION_PREFIX}*")
    sessions = []
    for key in keys:
        raw = r.get(key)
        if raw:
            sessions.append(json.loads(raw))
    sessions.sort(key=lambda s: s["created_at"], reverse=True)
    return {"sessions": sessions[:limit], "count": len(sessions)}


# ── Get training session ───────────────────────────────────
@app.get("/sessions/{session_id}")
async def get_session(session_id: str):
    raw = _get_redis().get(f"{REDIS_SESSION_PREFIX}{session_id}")
    if not raw:
        raise HTTPException(status_code=404, detail="Session not found")
    return json.loads(raw)


# ── Teach directly ─────────────────────────────────────────
class TeachRequest(BaseModel):
    fact: str
    memory_type: str = "preference"
    user: str = "Azim"


@app.post("/teach")
async def teach(request: TeachRequest):
    """Directly teach Fazle a fact or preference."""
    if not request.fact.strip():
        raise HTTPException(status_code=400, detail="Fact cannot be empty")

    async with httpx.AsyncClient(timeout=10.0) as client:
        try:
            resp = await client.post(
                f"{settings.memory_url}/store",
                json={
                    "type": request.memory_type,
                    "user": request.user,
                    "content": {"fact": request.fact, "source": "direct_teaching"},
                    "text": request.fact,
                },
            )
            resp.raise_for_status()
            return {"status": "learned", "fact": request.fact, "type": request.memory_type}
        except Exception as e:
            logger.error(f"Failed to store teaching: {e}")
            raise HTTPException(status_code=502, detail="Memory service unavailable")
