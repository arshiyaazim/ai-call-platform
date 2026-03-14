# ============================================================
# Fazle Learning Engine — Autonomous Self-Improvement System
# Analyses conversations, extracts knowledge, builds relationship
# graph, tracks user corrections, and drives nightly learning
# ============================================================
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings
from prometheus_fastapi_instrumentator import Instrumentator
import asyncpg
import httpx
import json
import logging
import uuid
import os
from typing import Optional
from datetime import datetime, timedelta

import redis

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("fazle-learning-engine")


class Settings(BaseSettings):
    database_url: str = ""
    redis_url: str = "redis://redis:6379/4"
    memory_url: str = "http://fazle-memory:8300"
    llm_gateway_url: str = "http://fazle-llm-gateway:8800"
    trainer_url: str = "http://fazle-trainer:8600"
    # Nightly learning config
    learning_hour: int = 3  # UTC hour to run nightly learning
    min_confidence: float = 0.6
    max_extractions_per_run: int = 100

    class Config:
        env_prefix = ""


settings = Settings()

DATABASE_URL = settings.database_url or os.getenv(
    "DATABASE_URL",
    "postgresql://postgres:postgres@postgres:5432/postgres",
)

_redis_client: Optional[redis.Redis] = None
_db_pool: Optional[asyncpg.Pool] = None


def _get_redis() -> redis.Redis:
    global _redis_client
    if _redis_client is None:
        _redis_client = redis.Redis.from_url(settings.redis_url, decode_responses=True)
    return _redis_client


app = FastAPI(title="Fazle Learning Engine — Self-Improvement System", version="1.0.0")

Instrumentator().instrument(app).expose(app, endpoint="/metrics")

ALLOWED_ORIGINS = os.getenv(
    "ALLOWED_ORIGINS",
    "https://fazle.iamazim.com,https://iamazim.com,http://localhost:3020",
).split(",")

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Database ────────────────────────────────────────────────

async def get_pool() -> asyncpg.Pool:
    global _db_pool
    if _db_pool is None:
        _db_pool = await asyncpg.create_pool(DATABASE_URL, min_size=2, max_size=10)
    return _db_pool


async def ensure_tables():
    """Create learning-engine tables idempotently."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS fazle_relationship_graph (
                id VARCHAR(36) PRIMARY KEY,
                person_name VARCHAR(255) NOT NULL,
                relationship VARCHAR(100) NOT NULL DEFAULT 'unknown',
                attributes JSONB DEFAULT '{}'::jsonb,
                interaction_count INT DEFAULT 0,
                last_interaction TIMESTAMPTZ,
                created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
            );
            CREATE INDEX IF NOT EXISTS idx_relationship_person
                ON fazle_relationship_graph(person_name);
        """)
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS fazle_corrections (
                id VARCHAR(36) PRIMARY KEY,
                original_response TEXT NOT NULL,
                corrected_response TEXT NOT NULL,
                user_feedback TEXT DEFAULT '',
                context JSONB DEFAULT '{}'::jsonb,
                applied BOOLEAN DEFAULT FALSE,
                created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
            );
        """)
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS fazle_learning_runs (
                id VARCHAR(36) PRIMARY KEY,
                run_type VARCHAR(50) NOT NULL,
                status VARCHAR(50) NOT NULL DEFAULT 'running',
                conversations_processed INT DEFAULT 0,
                extractions_stored INT DEFAULT 0,
                corrections_applied INT DEFAULT 0,
                relationships_updated INT DEFAULT 0,
                started_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                completed_at TIMESTAMPTZ,
                summary TEXT DEFAULT ''
            );
        """)
    logger.info("Learning engine tables verified")


@app.on_event("startup")
async def startup():
    await ensure_tables()
    logger.info("Learning engine started")


@app.on_event("shutdown")
async def shutdown():
    if _db_pool:
        await _db_pool.close()


# ── Health ──────────────────────────────────────────────────

@app.get("/health")
async def health():
    healthy = True
    checks = {}
    try:
        pool = await get_pool()
        async with pool.acquire() as conn:
            await conn.fetchval("SELECT 1")
        checks["database"] = "ok"
    except Exception:
        checks["database"] = "error"
        healthy = False
    try:
        _get_redis().ping()
        checks["redis"] = "ok"
    except Exception:
        checks["redis"] = "error"
    return {
        "status": "healthy" if healthy else "degraded",
        "service": "fazle-learning-engine",
        "checks": checks,
        "timestamp": datetime.utcnow().isoformat(),
    }


# ── Models ──────────────────────────────────────────────────

class CorrectionRequest(BaseModel):
    original_response: str
    corrected_response: str
    user_feedback: str = ""
    context: dict = Field(default_factory=dict)


class PersonRequest(BaseModel):
    person_name: str
    relationship: str = "unknown"
    attributes: dict = Field(default_factory=dict)


class LearnRequest(BaseModel):
    transcript: str
    user: str = "Azim"
    conversation_id: Optional[str] = None


# ── User Corrections ───────────────────────────────────────

@app.post("/corrections")
async def record_correction(request: CorrectionRequest):
    """Record a user correction for learning."""
    correction_id = str(uuid.uuid4())
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            """INSERT INTO fazle_corrections (id, original_response, corrected_response, user_feedback, context)
               VALUES ($1, $2, $3, $4, $5)""",
            correction_id,
            request.original_response,
            request.corrected_response,
            request.user_feedback,
            json.dumps(request.context),
        )

    # Store correction as a memory for immediate use
    async with httpx.AsyncClient(timeout=10.0) as client:
        try:
            await client.post(
                f"{settings.memory_url}/store",
                json={
                    "type": "preference",
                    "user": "Azim",
                    "content": {
                        "correction": True,
                        "original": request.original_response[:200],
                        "corrected": request.corrected_response[:200],
                        "feedback": request.user_feedback,
                    },
                    "text": f"User corrected response. Original: '{request.original_response[:100]}...' → Corrected: '{request.corrected_response[:100]}...' Feedback: {request.user_feedback}",
                },
            )
        except Exception as e:
            logger.warning(f"Failed to store correction memory: {e}")

    return {"id": correction_id, "status": "recorded"}


@app.get("/corrections")
async def list_corrections(applied: Optional[bool] = None, limit: int = 50):
    pool = await get_pool()
    async with pool.acquire() as conn:
        if applied is not None:
            rows = await conn.fetch(
                """SELECT id, original_response, corrected_response, user_feedback, applied, created_at
                   FROM fazle_corrections WHERE applied = $1 ORDER BY created_at DESC LIMIT $2""",
                applied, limit,
            )
        else:
            rows = await conn.fetch(
                """SELECT id, original_response, corrected_response, user_feedback, applied, created_at
                   FROM fazle_corrections ORDER BY created_at DESC LIMIT $1""",
                limit,
            )
    return {"corrections": [dict(r) for r in rows], "count": len(rows)}


# ── Relationship Graph ─────────────────────────────────────

@app.post("/relationships")
async def upsert_relationship(request: PersonRequest):
    """Add or update a person in the relationship graph."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        existing = await conn.fetchrow(
            "SELECT id FROM fazle_relationship_graph WHERE person_name = $1",
            request.person_name,
        )
        if existing:
            await conn.execute(
                """UPDATE fazle_relationship_graph
                   SET relationship = $1, attributes = $2, updated_at = NOW()
                   WHERE person_name = $3""",
                request.relationship,
                json.dumps(request.attributes),
                request.person_name,
            )
            return {"id": existing["id"], "status": "updated"}
        else:
            person_id = str(uuid.uuid4())
            await conn.execute(
                """INSERT INTO fazle_relationship_graph (id, person_name, relationship, attributes)
                   VALUES ($1, $2, $3, $4)""",
                person_id,
                request.person_name,
                request.relationship,
                json.dumps(request.attributes),
            )
            return {"id": person_id, "status": "created"}


@app.get("/relationships")
async def list_relationships():
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """SELECT id, person_name, relationship, attributes, interaction_count,
                      last_interaction, created_at, updated_at
               FROM fazle_relationship_graph ORDER BY interaction_count DESC""",
        )
    return {"relationships": [dict(r) for r in rows], "count": len(rows)}


@app.get("/relationships/{person_name}")
async def get_relationship(person_name: str):
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT * FROM fazle_relationship_graph WHERE person_name = $1",
            person_name,
        )
    if not row:
        raise HTTPException(status_code=404, detail="Person not found")
    return dict(row)


# ── Conversation Learning ──────────────────────────────────

LEARNING_PROMPT = """You are a knowledge extraction and relationship analysis engine.
Given a conversation transcript, extract:
1. **Knowledge facts** — preferences, routines, important dates, habits
2. **People mentioned** — names, relationships, attributes
3. **Corrections** — any cases where a previous AI response was wrong and the user corrected it
4. **Personality insights** — communication style, tone preferences, topics of interest

Respond in JSON:
{
  "knowledge": [
    {"type": "preference|knowledge|personal", "text": "...", "content": {...}, "confidence": 0.0-1.0}
  ],
  "people": [
    {"name": "...", "relationship": "...", "attributes": {...}}
  ],
  "corrections": [
    {"original": "...", "corrected": "...", "context": "..."}
  ],
  "personality_insights": ["..."],
  "summary": "brief summary"
}"""


@app.post("/learn")
async def learn_from_conversation(request: LearnRequest):
    """Analyze a conversation and extract knowledge, relationships, corrections."""
    if not request.transcript.strip():
        raise HTTPException(status_code=400, detail="Transcript cannot be empty")

    run_id = str(uuid.uuid4())

    # Call LLM Gateway for analysis
    messages = [
        {"role": "system", "content": LEARNING_PROMPT},
        {"role": "user", "content": f"User: {request.user}\n\nTranscript:\n{request.transcript}"},
    ]

    async with httpx.AsyncClient(timeout=60.0) as client:
        try:
            resp = await client.post(
                f"{settings.llm_gateway_url}/generate",
                json={
                    "messages": messages,
                    "response_format": "json",
                    "caller": "learning-engine",
                    "temperature": 0.3,
                    "cache": False,
                },
            )
            resp.raise_for_status()
            result = json.loads(resp.json()["content"])
        except Exception as e:
            logger.error(f"LLM analysis failed: {e}")
            raise HTTPException(status_code=502, detail="LLM analysis unavailable")

    pool = await get_pool()
    stored_count = 0
    relationships_updated = 0
    corrections_count = 0

    # Store knowledge extractions
    for item in result.get("knowledge", []):
        if item.get("confidence", 0) < settings.min_confidence:
            continue
        async with httpx.AsyncClient(timeout=10.0) as client:
            try:
                await client.post(
                    f"{settings.memory_url}/store",
                    json={
                        "type": item.get("type", "knowledge"),
                        "user": request.user,
                        "content": item.get("content", {}),
                        "text": item.get("text", ""),
                    },
                )
                stored_count += 1
            except Exception as e:
                logger.warning(f"Failed to store knowledge: {e}")

    # Update relationship graph
    for person in result.get("people", []):
        name = person.get("name", "").strip()
        if not name:
            continue
        async with pool.acquire() as conn:
            existing = await conn.fetchrow(
                "SELECT id, attributes FROM fazle_relationship_graph WHERE person_name = $1",
                name,
            )
            if existing:
                # Merge attributes
                old_attrs = json.loads(existing["attributes"]) if isinstance(existing["attributes"], str) else (existing["attributes"] or {})
                new_attrs = {**old_attrs, **person.get("attributes", {})}
                await conn.execute(
                    """UPDATE fazle_relationship_graph
                       SET relationship = COALESCE(NULLIF($1, 'unknown'), relationship),
                           attributes = $2,
                           interaction_count = interaction_count + 1,
                           last_interaction = NOW(),
                           updated_at = NOW()
                       WHERE id = $3""",
                    person.get("relationship", "unknown"),
                    json.dumps(new_attrs),
                    existing["id"],
                )
            else:
                await conn.execute(
                    """INSERT INTO fazle_relationship_graph (id, person_name, relationship, attributes, interaction_count, last_interaction)
                       VALUES ($1, $2, $3, $4, 1, NOW())""",
                    str(uuid.uuid4()),
                    name,
                    person.get("relationship", "unknown"),
                    json.dumps(person.get("attributes", {})),
                )
            relationships_updated += 1

    # Record corrections
    for correction in result.get("corrections", []):
        correction_id = str(uuid.uuid4())
        async with pool.acquire() as conn:
            await conn.execute(
                """INSERT INTO fazle_corrections (id, original_response, corrected_response, user_feedback, context)
                   VALUES ($1, $2, $3, $4, $5)""",
                correction_id,
                correction.get("original", ""),
                correction.get("corrected", ""),
                correction.get("context", ""),
                json.dumps({"source": "auto_extracted", "conversation_id": request.conversation_id}),
            )
            corrections_count += 1

    # Store personality insights as memories
    for insight in result.get("personality_insights", []):
        if insight:
            async with httpx.AsyncClient(timeout=10.0) as client:
                try:
                    await client.post(
                        f"{settings.memory_url}/store",
                        json={
                            "type": "personal",
                            "user": request.user,
                            "content": {"insight": insight, "source": "auto_learning"},
                            "text": f"Personality insight: {insight}",
                        },
                    )
                except Exception:
                    pass

    # Log the learning run
    async with pool.acquire() as conn:
        await conn.execute(
            """INSERT INTO fazle_learning_runs (id, run_type, status, conversations_processed, extractions_stored, corrections_applied, relationships_updated, completed_at, summary)
               VALUES ($1, 'conversation', 'completed', 1, $2, $3, $4, NOW(), $5)""",
            run_id, stored_count, corrections_count, relationships_updated,
            result.get("summary", ""),
        )

    return {
        "run_id": run_id,
        "summary": result.get("summary", ""),
        "extractions_stored": stored_count,
        "corrections_recorded": corrections_count,
        "relationships_updated": relationships_updated,
    }


# ── Nightly Learning Run ───────────────────────────────────

@app.post("/nightly-learn")
async def nightly_learning_run():
    """Process unanalyzed conversations from the past 24 hours.
    Intended to be called by the task engine on a schedule."""
    run_id = str(uuid.uuid4())
    pool = await get_pool()

    # Log the run start
    async with pool.acquire() as conn:
        await conn.execute(
            """INSERT INTO fazle_learning_runs (id, run_type, status)
               VALUES ($1, 'nightly', 'running')""",
            run_id,
        )

    conversations_processed = 0
    total_extractions = 0
    total_corrections = 0
    total_relationships = 0

    try:
        # Get recent conversations from memory service
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.post(
                f"{settings.memory_url}/search",
                json={
                    "query": "conversation from today",
                    "memory_type": "conversation",
                    "limit": settings.max_extractions_per_run,
                },
            )
            if resp.status_code != 200:
                logger.warning("Failed to fetch recent conversations")
                conversations = []
            else:
                conversations = resp.json().get("results", [])

        # Batch conversations for analysis
        batch_size = 5
        for i in range(0, len(conversations), batch_size):
            batch = conversations[i:i + batch_size]
            transcript = "\n---\n".join(
                c.get("text", str(c.get("content", ""))) for c in batch
            )
            if not transcript.strip():
                continue

            messages = [
                {"role": "system", "content": LEARNING_PROMPT},
                {"role": "user", "content": f"User: Azim\n\nTranscript:\n{transcript}"},
            ]

            async with httpx.AsyncClient(timeout=60.0) as client:
                try:
                    resp = await client.post(
                        f"{settings.llm_gateway_url}/generate",
                        json={
                            "messages": messages,
                            "response_format": "json",
                            "caller": "learning-engine-nightly",
                            "temperature": 0.2,
                            "cache": False,
                        },
                    )
                    resp.raise_for_status()
                    result = json.loads(resp.json()["content"])
                except Exception as e:
                    logger.warning(f"Nightly batch analysis failed: {e}")
                    continue

            conversations_processed += len(batch)

            # Store knowledge
            for item in result.get("knowledge", []):
                if item.get("confidence", 0) < settings.min_confidence:
                    continue
                async with httpx.AsyncClient(timeout=10.0) as client:
                    try:
                        await client.post(
                            f"{settings.memory_url}/store",
                            json={
                                "type": item.get("type", "knowledge"),
                                "user": "Azim",
                                "content": item.get("content", {}),
                                "text": item.get("text", ""),
                            },
                        )
                        total_extractions += 1
                    except Exception:
                        pass

            # Update relationships
            for person in result.get("people", []):
                name = person.get("name", "").strip()
                if not name:
                    continue
                async with pool.acquire() as conn:
                    existing = await conn.fetchrow(
                        "SELECT id, attributes FROM fazle_relationship_graph WHERE person_name = $1",
                        name,
                    )
                    if existing:
                        old_attrs = json.loads(existing["attributes"]) if isinstance(existing["attributes"], str) else (existing["attributes"] or {})
                        new_attrs = {**old_attrs, **person.get("attributes", {})}
                        await conn.execute(
                            """UPDATE fazle_relationship_graph
                               SET relationship = COALESCE(NULLIF($1, 'unknown'), relationship),
                                   attributes = $2,
                                   interaction_count = interaction_count + 1,
                                   last_interaction = NOW(),
                                   updated_at = NOW()
                               WHERE id = $3""",
                            person.get("relationship", "unknown"),
                            json.dumps(new_attrs),
                            existing["id"],
                        )
                    else:
                        await conn.execute(
                            """INSERT INTO fazle_relationship_graph (id, person_name, relationship, attributes, interaction_count, last_interaction)
                               VALUES ($1, $2, $3, $4, 1, NOW())""",
                            str(uuid.uuid4()),
                            name,
                            person.get("relationship", "unknown"),
                            json.dumps(person.get("attributes", {})),
                        )
                    total_relationships += 1

            # Record corrections
            for correction in result.get("corrections", []):
                correction_id = str(uuid.uuid4())
                async with pool.acquire() as conn:
                    await conn.execute(
                        """INSERT INTO fazle_corrections (id, original_response, corrected_response, user_feedback, context)
                           VALUES ($1, $2, $3, $4, $5)""",
                        correction_id,
                        correction.get("original", ""),
                        correction.get("corrected", ""),
                        correction.get("context", ""),
                        json.dumps({"source": "nightly_analysis"}),
                    )
                    total_corrections += 1

        # Apply unapplied corrections as learning
        async with pool.acquire() as conn:
            unapplied = await conn.fetch(
                "SELECT id, original_response, corrected_response, user_feedback FROM fazle_corrections WHERE applied = FALSE LIMIT 20"
            )
            for row in unapplied:
                # Store each correction as a preference memory
                async with httpx.AsyncClient(timeout=10.0) as client:
                    try:
                        await client.post(
                            f"{settings.memory_url}/store",
                            json={
                                "type": "preference",
                                "user": "Azim",
                                "content": {
                                    "correction": True,
                                    "original": row["original_response"][:200],
                                    "corrected": row["corrected_response"][:200],
                                },
                                "text": f"Correction learned: instead of '{row['original_response'][:80]}' respond with '{row['corrected_response'][:80]}'",
                            },
                        )
                    except Exception:
                        pass
                await conn.execute(
                    "UPDATE fazle_corrections SET applied = TRUE WHERE id = $1",
                    row["id"],
                )

        status = "completed"
        summary = f"Processed {conversations_processed} conversations. Stored {total_extractions} facts, {total_corrections} corrections, {total_relationships} relationships."

    except Exception as e:
        logger.error(f"Nightly learning failed: {e}")
        status = "failed"
        summary = str(e)

    # Update the run record
    async with pool.acquire() as conn:
        await conn.execute(
            """UPDATE fazle_learning_runs
               SET status = $1, conversations_processed = $2, extractions_stored = $3,
                   corrections_applied = $4, relationships_updated = $5, completed_at = NOW(), summary = $6
               WHERE id = $7""",
            status, conversations_processed, total_extractions,
            total_corrections, total_relationships, summary, run_id,
        )

    return {
        "run_id": run_id,
        "status": status,
        "conversations_processed": conversations_processed,
        "extractions_stored": total_extractions,
        "corrections_applied": total_corrections,
        "relationships_updated": total_relationships,
        "summary": summary,
    }


# ── Learning Runs History ──────────────────────────────────

@app.get("/runs")
async def list_runs(limit: int = 20):
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """SELECT id, run_type, status, conversations_processed, extractions_stored,
                      corrections_applied, relationships_updated, started_at, completed_at, summary
               FROM fazle_learning_runs ORDER BY started_at DESC LIMIT $1""",
            limit,
        )
    return {"runs": [dict(r) for r in rows], "count": len(rows)}


# ── Stats ───────────────────────────────────────────────────

@app.get("/stats")
async def learning_stats():
    """Return aggregate learning statistics."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        total_runs = await conn.fetchval("SELECT COUNT(*) FROM fazle_learning_runs")
        total_corrections = await conn.fetchval("SELECT COUNT(*) FROM fazle_corrections")
        applied_corrections = await conn.fetchval("SELECT COUNT(*) FROM fazle_corrections WHERE applied = TRUE")
        total_people = await conn.fetchval("SELECT COUNT(*) FROM fazle_relationship_graph")
        last_run = await conn.fetchrow(
            "SELECT started_at, status, summary FROM fazle_learning_runs ORDER BY started_at DESC LIMIT 1"
        )

    return {
        "total_learning_runs": total_runs,
        "total_corrections": total_corrections,
        "applied_corrections": applied_corrections,
        "people_in_graph": total_people,
        "last_run": dict(last_run) if last_run else None,
    }
