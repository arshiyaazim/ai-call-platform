# ============================================================
# Fazle Memory — Long-term memory with vector search (Qdrant)
# Stores: preferences, contacts, knowledge, conversations,
#         images, and documents with embedded images
# ============================================================
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings
from prometheus_fastapi_instrumentator import Instrumentator
import httpx
import logging
import uuid
import hashlib
from typing import Optional
import os
from datetime import datetime
from minio import Minio
from urllib.parse import urlparse

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("fazle-memory")


class Settings(BaseSettings):
    vector_db_url: str = "http://qdrant:6333"
    openai_api_key: str = ""
    embedding_model: str = "text-embedding-3-small"
    embedding_dim: int = 1536
    collection_name: str = "fazle_memories"

    # Multimodal collection (text-embedding-3-large for vision captions)
    multimodal_collection: str = "fazle_memories_multimodal"
    multimodal_embedding_dim: int = 3072
    multimodal_embedding_model: str = "text-embedding-3-large"

    # MinIO S3 storage for presigned URLs
    minio_endpoint: str = "minio:9000"
    minio_access_key: str = ""
    minio_secret_key: str = ""
    minio_bucket: str = "fazle-multimodal"
    minio_secure: bool = False
    minio_presign_expiry: int = 3600  # 1 hour

    class Config:
        env_prefix = ""


settings = Settings()

app = FastAPI(title="Fazle Memory — Vector Memory System", version="1.0.0")

Instrumentator().instrument(app).expose(app, endpoint="/metrics")

ALLOWED_ORIGINS = os.getenv("ALLOWED_ORIGINS", "https://fazle.iamazim.com,https://iamazim.com,http://localhost:3020").split(",")

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_methods=["*"],
    allow_headers=["*"],
)

MEMORY_TYPES = {"preference", "contact", "knowledge", "personal", "conversation", "image", "document_with_images"}

# Initialize MinIO client
def _get_minio_client() -> Minio | None:
    if not settings.minio_access_key or not settings.minio_secret_key:
        logger.warning("MinIO credentials not configured — presigned URLs disabled")
        return None
    return Minio(
        settings.minio_endpoint,
        access_key=settings.minio_access_key,
        secret_key=settings.minio_secret_key,
        secure=settings.minio_secure,
    )

_minio_client: Minio | None = None

def get_minio() -> Minio | None:
    global _minio_client
    if _minio_client is None:
        _minio_client = _get_minio_client()
    return _minio_client


async def ensure_collection():
    """Create Qdrant collections if they don't exist."""
    collections = [
        (settings.collection_name, settings.embedding_dim),
        (settings.multimodal_collection, settings.multimodal_embedding_dim),
    ]
    async with httpx.AsyncClient(timeout=10.0) as client:
        for coll_name, dim in collections:
            try:
                resp = await client.get(f"{settings.vector_db_url}/collections/{coll_name}")
                if resp.status_code == 200:
                    continue
            except Exception:
                pass

            try:
                await client.put(
                    f"{settings.vector_db_url}/collections/{coll_name}",
                    json={
                        "vectors": {"size": dim, "distance": "Cosine"},
                    },
                )
                logger.info(f"Created collection: {coll_name} (dim={dim})")
            except Exception as e:
                logger.error(f"Failed to create collection {coll_name}: {e}")

        # Create payload indexes on multimodal collection for efficient filtering
        for field_name, field_type in [("type", "keyword"), ("uploaded_by", "keyword")]:
            try:
                await client.put(
                    f"{settings.vector_db_url}/collections/{settings.multimodal_collection}/index",
                    json={"field_name": field_name, "field_schema": field_type},
                )
            except Exception:
                pass  # Index may already exist


async def get_embedding(text: str) -> list[float]:
    """Get embedding vector from OpenAI (text-embedding-3-small, 1536-dim)."""
    async with httpx.AsyncClient(timeout=15.0) as client:
        resp = await client.post(
            "https://api.openai.com/v1/embeddings",
            headers={
                "Authorization": f"Bearer {settings.openai_api_key}",
                "Content-Type": "application/json",
            },
            json={"model": settings.embedding_model, "input": text},
        )
        resp.raise_for_status()
        data = resp.json()
        return data["data"][0]["embedding"]


async def get_multimodal_embedding(text: str) -> list[float]:
    """Get embedding vector from OpenAI (text-embedding-3-large, 3072-dim)."""
    async with httpx.AsyncClient(timeout=15.0) as client:
        resp = await client.post(
            "https://api.openai.com/v1/embeddings",
            headers={
                "Authorization": f"Bearer {settings.openai_api_key}",
                "Content-Type": "application/json",
            },
            json={"model": settings.multimodal_embedding_model, "input": text},
        )
        resp.raise_for_status()
        data = resp.json()
        return data["data"][0]["embedding"]


def generate_presigned_url(object_name: str) -> str | None:
    """Generate a presigned URL for an object in MinIO."""
    client = get_minio()
    if not client:
        return None
    try:
        from datetime import timedelta
        url = client.presigned_get_object(
            settings.minio_bucket,
            object_name,
            expires=timedelta(seconds=settings.minio_presign_expiry),
        )
        return url
    except Exception as e:
        logger.warning(f"Failed to generate presigned URL for {object_name}: {e}")
        return None


@app.on_event("startup")
async def startup():
    await ensure_collection()


# ── Health ──────────────────────────────────────────────────
@app.get("/health")
async def health():
    return {"status": "healthy", "service": "fazle-memory", "timestamp": datetime.utcnow().isoformat()}


# ── Store memory ────────────────────────────────────────────
class StoreRequest(BaseModel):
    type: str = Field(..., description="Memory type")
    user: str = "Azim"
    content: dict = Field(default_factory=dict)
    text: str = ""
    user_id: Optional[str] = Field(None, description="Owner user ID for privacy isolation")


@app.post("/store")
async def store_memory(request: StoreRequest):
    """Store a memory with vector embedding."""
    if request.type not in MEMORY_TYPES:
        raise HTTPException(status_code=400, detail=f"Invalid memory type. Must be one of: {MEMORY_TYPES}")

    text_to_embed = request.text or str(request.content)
    if not text_to_embed.strip():
        raise HTTPException(status_code=400, detail="No text content to store")

    try:
        embedding = await get_embedding(text_to_embed)
    except Exception as e:
        logger.error(f"Embedding failed: {e}")
        raise HTTPException(status_code=502, detail="Embedding service unavailable")

    # Generate deterministic ID from content for deduplication
    content_hash = hashlib.sha256(text_to_embed.encode()).hexdigest()[:16]
    point_id = str(uuid.uuid5(uuid.NAMESPACE_DNS, content_hash))

    payload = {
        "type": request.type,
        "user": request.user,
        "content": request.content,
        "text": text_to_embed,
        "created_at": datetime.utcnow().isoformat(),
    }
    if request.user_id:
        payload["user_id"] = request.user_id

    async with httpx.AsyncClient(timeout=10.0) as client:
        try:
            resp = await client.put(
                f"{settings.vector_db_url}/collections/{settings.collection_name}/points",
                json={
                    "points": [
                        {
                            "id": point_id,
                            "vector": embedding,
                            "payload": payload,
                        }
                    ]
                },
            )
            resp.raise_for_status()
        except Exception as e:
            logger.error(f"Qdrant store failed: {e}")
            raise HTTPException(status_code=502, detail="Vector database unavailable")

    return {"status": "stored", "id": point_id, "type": request.type}


# ── Search memories ─────────────────────────────────────────
class SearchRequest(BaseModel):
    query: str
    memory_type: Optional[str] = None
    limit: int = 5
    user_id: Optional[str] = Field(None, description="Filter memories by owner user ID")


@app.post("/search")
async def search_memories(request: SearchRequest):
    """Semantic search across memories."""
    try:
        embedding = await get_embedding(request.query)
    except Exception as e:
        logger.error(f"Embedding failed: {e}")
        raise HTTPException(status_code=502, detail="Embedding service unavailable")

    search_body: dict = {
        "vector": embedding,
        "limit": request.limit,
        "with_payload": True,
    }

    # Build filter conditions
    filter_conditions = []
    if request.memory_type and request.memory_type in MEMORY_TYPES:
        filter_conditions.append({"key": "type", "match": {"value": request.memory_type}})
    if request.user_id:
        filter_conditions.append({"key": "user_id", "match": {"value": request.user_id}})
    if filter_conditions:
        search_body["filter"] = {"must": filter_conditions}

    async with httpx.AsyncClient(timeout=10.0) as client:
        try:
            resp = await client.post(
                f"{settings.vector_db_url}/collections/{settings.collection_name}/points/search",
                json=search_body,
            )
            resp.raise_for_status()
            data = resp.json()
        except Exception as e:
            logger.error(f"Qdrant search failed: {e}")
            raise HTTPException(status_code=502, detail="Vector database unavailable")

    results = []
    for hit in data.get("result", []):
        payload = hit.get("payload", {})
        results.append({
            "id": hit.get("id"),
            "score": hit.get("score", 0),
            "type": payload.get("type"),
            "user": payload.get("user"),
            "content": payload.get("content"),
            "text": payload.get("text"),
            "created_at": payload.get("created_at"),
        })

    return {"results": results, "count": len(results)}


# ── Knowledge ingestion ─────────────────────────────────────
class IngestRequest(BaseModel):
    text: str
    source: str = "manual"
    title: str = ""


@app.post("/ingest")
async def ingest_knowledge(request: IngestRequest):
    """Ingest a document into the knowledge base. Splits into chunks."""
    if not request.text.strip():
        raise HTTPException(status_code=400, detail="No text to ingest")

    # Split text into chunks of ~500 chars with overlap
    chunks = _chunk_text(request.text, chunk_size=500, overlap=50)
    stored = 0

    for i, chunk in enumerate(chunks):
        try:
            embedding = await get_embedding(chunk)
        except Exception as e:
            logger.warning(f"Embedding failed for chunk {i}: {e}")
            continue

        point_id = str(uuid.uuid4())
        payload = {
            "type": "knowledge",
            "user": "system",
            "content": {"source": request.source, "title": request.title, "chunk_index": i},
            "text": chunk,
            "created_at": datetime.utcnow().isoformat(),
        }

        async with httpx.AsyncClient(timeout=10.0) as client:
            try:
                await client.put(
                    f"{settings.vector_db_url}/collections/{settings.collection_name}/points",
                    json={"points": [{"id": point_id, "vector": embedding, "payload": payload}]},
                )
                stored += 1
            except Exception as e:
                logger.warning(f"Failed to store chunk {i}: {e}")

    return {"status": "ingested", "chunks_stored": stored, "total_chunks": len(chunks)}


# ── List memories by type ───────────────────────────────────
@app.get("/memories")
async def list_memories(memory_type: Optional[str] = None, limit: int = 20, offset: int = 0):
    """List stored memories, optionally filtered by type."""
    scroll_body: dict = {
        "limit": limit,
        "offset": offset,
        "with_payload": True,
    }

    if memory_type and memory_type in MEMORY_TYPES:
        scroll_body["filter"] = {
            "must": [{"key": "type", "match": {"value": memory_type}}]
        }

    async with httpx.AsyncClient(timeout=10.0) as client:
        try:
            resp = await client.post(
                f"{settings.vector_db_url}/collections/{settings.collection_name}/points/scroll",
                json=scroll_body,
            )
            resp.raise_for_status()
            data = resp.json()
        except Exception as e:
            logger.error(f"Qdrant scroll failed: {e}")
            raise HTTPException(status_code=502, detail="Vector database unavailable")

    points = data.get("result", {}).get("points", [])
    return {
        "memories": [
            {
                "id": p.get("id"),
                "type": p.get("payload", {}).get("type"),
                "text": p.get("payload", {}).get("text"),
                "content": p.get("payload", {}).get("content"),
                "created_at": p.get("payload", {}).get("created_at"),
            }
            for p in points
        ],
        "count": len(points),
    }


# ── Delete memory ───────────────────────────────────────────
@app.delete("/memories/{memory_id}")
async def delete_memory(memory_id: str):
    """Delete a specific memory by ID."""
    async with httpx.AsyncClient(timeout=10.0) as client:
        try:
            resp = await client.post(
                f"{settings.vector_db_url}/collections/{settings.collection_name}/points/delete",
                json={"points": [memory_id]},
            )
            resp.raise_for_status()
        except Exception as e:
            logger.error(f"Qdrant delete failed: {e}")
            raise HTTPException(status_code=502, detail="Vector database unavailable")
    return {"status": "deleted", "id": memory_id}


# ── Store multimodal memory ─────────────────────────────────
class StoreMultimodalRequest(BaseModel):
    type: str = Field(..., description="Memory type (image / document_with_images)")
    user: str = "Azim"
    caption: str = Field(..., description="GPT-4o generated caption / description")
    object_key: str = Field(..., description="MinIO object key for the original file")
    thumbnail_key: str = Field("", description="MinIO object key for the thumbnail")
    original_filename: str = ""
    content: dict = Field(default_factory=dict)
    user_id: Optional[str] = None
    uploaded_by: Optional[str] = None


@app.post("/store-multimodal")
async def store_multimodal_memory(request: StoreMultimodalRequest):
    """Store a multimodal memory with text-embedding-3-large vector."""
    if request.type not in {"image", "document_with_images"}:
        raise HTTPException(status_code=400, detail="Type must be 'image' or 'document_with_images'")

    if not request.caption.strip():
        raise HTTPException(status_code=400, detail="Caption is required for multimodal storage")

    try:
        embedding = await get_multimodal_embedding(request.caption)
    except Exception as e:
        logger.error(f"Multimodal embedding failed: {e}")
        raise HTTPException(status_code=502, detail="Embedding service unavailable")

    content_hash = hashlib.sha256(
        f"{request.object_key}:{request.caption[:200]}".encode()
    ).hexdigest()[:16]
    point_id = str(uuid.uuid5(uuid.NAMESPACE_DNS, content_hash))

    payload = {
        "type": request.type,
        "user": request.user,
        "caption": request.caption,
        "text": request.caption,
        "object_key": request.object_key,
        "thumbnail_key": request.thumbnail_key,
        "original_filename": request.original_filename,
        "content": request.content,
        "created_at": datetime.utcnow().isoformat(),
    }
    if request.user_id:
        payload["user_id"] = request.user_id
    if request.uploaded_by:
        payload["uploaded_by"] = request.uploaded_by

    async with httpx.AsyncClient(timeout=10.0) as client:
        try:
            resp = await client.put(
                f"{settings.vector_db_url}/collections/{settings.multimodal_collection}/points",
                json={
                    "points": [
                        {
                            "id": point_id,
                            "vector": embedding,
                            "payload": payload,
                        }
                    ]
                },
            )
            resp.raise_for_status()
        except Exception as e:
            logger.error(f"Qdrant multimodal store failed: {e}")
            raise HTTPException(status_code=502, detail="Vector database unavailable")

    return {"status": "stored", "id": point_id, "type": request.type, "collection": settings.multimodal_collection}


# ── Search multimodal memories ──────────────────────────────
class SearchMultimodalRequest(BaseModel):
    query: str
    limit: int = 5
    user_id: Optional[str] = None
    memory_type: Optional[str] = None


@app.post("/search-multimodal")
async def search_multimodal_memories(request: SearchMultimodalRequest):
    """Semantic search across multimodal memories (images, documents with images)."""
    try:
        embedding = await get_multimodal_embedding(request.query)
    except Exception as e:
        logger.error(f"Multimodal embedding failed: {e}")
        raise HTTPException(status_code=502, detail="Embedding service unavailable")

    search_body: dict = {
        "vector": embedding,
        "limit": request.limit,
        "with_payload": True,
    }

    filter_conditions = []
    if request.memory_type and request.memory_type in {"image", "document_with_images"}:
        filter_conditions.append({"key": "type", "match": {"value": request.memory_type}})
    if request.user_id:
        filter_conditions.append({"key": "user_id", "match": {"value": request.user_id}})
    if filter_conditions:
        search_body["filter"] = {"must": filter_conditions}

    async with httpx.AsyncClient(timeout=10.0) as client:
        try:
            resp = await client.post(
                f"{settings.vector_db_url}/collections/{settings.multimodal_collection}/points/search",
                json=search_body,
            )
            resp.raise_for_status()
            data = resp.json()
        except Exception as e:
            logger.error(f"Qdrant multimodal search failed: {e}")
            raise HTTPException(status_code=502, detail="Vector database unavailable")

    results = []
    for hit in data.get("result", []):
        p = hit.get("payload", {})
        # Generate presigned URLs for the images
        image_url = generate_presigned_url(p.get("object_key", "")) if p.get("object_key") else None
        thumbnail_url = generate_presigned_url(p.get("thumbnail_key", "")) if p.get("thumbnail_key") else None
        results.append({
            "id": hit.get("id"),
            "score": hit.get("score", 0),
            "type": p.get("type"),
            "user": p.get("user"),
            "caption": p.get("caption", ""),
            "text": p.get("text", p.get("caption", "")),
            "object_key": p.get("object_key", ""),
            "thumbnail_key": p.get("thumbnail_key", ""),
            "original_filename": p.get("original_filename", ""),
            "image_url": image_url,
            "thumbnail_url": thumbnail_url,
            "content": p.get("content", {}),
            "created_at": p.get("created_at"),
        })

    return {"results": results, "count": len(results)}


# ── Unified search (text + multimodal) ──────────────────────
@app.post("/search-all")
async def search_all_memories(request: SearchRequest):
    """Search across both text and multimodal collections, merging results by score."""
    # Search text collection
    text_results = []
    try:
        text_embedding = await get_embedding(request.query)
        text_search_body: dict = {
            "vector": text_embedding,
            "limit": request.limit,
            "with_payload": True,
        }
        text_filters = []
        if request.memory_type and request.memory_type in MEMORY_TYPES:
            text_filters.append({"key": "type", "match": {"value": request.memory_type}})
        if request.user_id:
            text_filters.append({"key": "user_id", "match": {"value": request.user_id}})
        if text_filters:
            text_search_body["filter"] = {"must": text_filters}

        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(
                f"{settings.vector_db_url}/collections/{settings.collection_name}/points/search",
                json=text_search_body,
            )
            resp.raise_for_status()
            for hit in resp.json().get("result", []):
                p = hit.get("payload", {})
                text_results.append({
                    "id": hit.get("id"), "score": hit.get("score", 0),
                    "type": p.get("type"), "user": p.get("user"),
                    "text": p.get("text"), "content": p.get("content"),
                    "created_at": p.get("created_at"), "collection": "text",
                })
    except Exception as e:
        logger.warning(f"Text search failed: {e}")

    # Search multimodal collection
    mm_results = []
    try:
        mm_embedding = await get_multimodal_embedding(request.query)
        mm_search_body: dict = {
            "vector": mm_embedding,
            "limit": request.limit,
            "with_payload": True,
        }
        mm_filters = []
        if request.user_id:
            mm_filters.append({"key": "user_id", "match": {"value": request.user_id}})
        if mm_filters:
            mm_search_body["filter"] = {"must": mm_filters}

        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(
                f"{settings.vector_db_url}/collections/{settings.multimodal_collection}/points/search",
                json=mm_search_body,
            )
            resp.raise_for_status()
            for hit in resp.json().get("result", []):
                p = hit.get("payload", {})
                image_url = generate_presigned_url(p.get("object_key", "")) if p.get("object_key") else None
                thumbnail_url = generate_presigned_url(p.get("thumbnail_key", "")) if p.get("thumbnail_key") else None
                mm_results.append({
                    "id": hit.get("id"), "score": hit.get("score", 0),
                    "type": p.get("type"), "user": p.get("user"),
                    "text": p.get("caption", p.get("text", "")),
                    "caption": p.get("caption", ""),
                    "object_key": p.get("object_key", ""),
                    "image_url": image_url, "thumbnail_url": thumbnail_url,
                    "original_filename": p.get("original_filename", ""),
                    "content": p.get("content", {}),
                    "created_at": p.get("created_at"), "collection": "multimodal",
                })
    except Exception as e:
        logger.warning(f"Multimodal search failed: {e}")

    # Merge and sort by score
    combined = text_results + mm_results
    combined.sort(key=lambda x: x.get("score", 0), reverse=True)
    return {"results": combined[:request.limit], "count": len(combined[:request.limit])}


def _chunk_text(text: str, chunk_size: int = 500, overlap: int = 50) -> list[str]:
    """Split text into overlapping chunks."""
    if len(text) <= chunk_size:
        return [text]

    chunks = []
    start = 0
    while start < len(text):
        end = start + chunk_size
        chunk = text[start:end]
        if chunk.strip():
            chunks.append(chunk.strip())
        start = end - overlap
    return chunks


# ── Personal Facts — Structured user data ───────────────────
PERSONAL_CATEGORIES = {
    "preference", "contact", "project", "schedule",
    "relationship", "health", "financial", "habit",
}


class PersonalFactRequest(BaseModel):
    category: str = Field(..., description="Fact category (preference, contact, project, etc.)")
    key: str = Field(..., description="Fact key (e.g., 'favorite_color')")
    value: str = Field(..., description="Fact value (e.g., 'blue')")
    user_id: Optional[str] = None


@app.post("/personal/store")
async def store_personal_fact(request: PersonalFactRequest):
    """Store a structured personal fact about the user."""
    if request.category not in PERSONAL_CATEGORIES:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid category. Must be one of: {PERSONAL_CATEGORIES}",
        )

    text = f"Personal {request.category}: {request.key} is {request.value}"
    try:
        embedding = await get_embedding(text)
    except Exception as e:
        logger.error(f"Embedding failed for personal fact: {e}")
        raise HTTPException(status_code=502, detail="Embedding service unavailable")

    content_hash = hashlib.sha256(
        f"personal:{request.category}:{request.key}".encode()
    ).hexdigest()[:16]
    point_id = str(uuid.uuid5(uuid.NAMESPACE_DNS, content_hash))

    payload = {
        "type": "personal",
        "user": "Azim",
        "category": request.category,
        "key": request.key,
        "value": request.value,
        "text": text,
        "content": {
            "category": request.category,
            "key": request.key,
            "value": request.value,
        },
        "created_at": datetime.utcnow().isoformat(),
    }
    if request.user_id:
        payload["user_id"] = request.user_id

    async with httpx.AsyncClient(timeout=10.0) as client:
        try:
            resp = await client.put(
                f"{settings.vector_db_url}/collections/{settings.collection_name}/points",
                json={"points": [{"id": point_id, "vector": embedding, "payload": payload}]},
            )
            resp.raise_for_status()
        except Exception as e:
            logger.error(f"Personal fact store failed: {e}")
            raise HTTPException(status_code=502, detail="Vector database unavailable")

    return {"status": "stored", "id": point_id, "category": request.category, "key": request.key}


class PersonalSearchRequest(BaseModel):
    query: str = ""
    category: Optional[str] = None
    user_id: Optional[str] = None
    limit: int = 10


@app.post("/personal/search")
async def search_personal_facts(request: PersonalSearchRequest):
    """Search personal facts by semantic query and/or category."""
    if not request.query.strip() and not request.category:
        raise HTTPException(status_code=400, detail="Provide a query or category")

    search_text = request.query or f"personal {request.category}"
    try:
        embedding = await get_embedding(search_text)
    except Exception as e:
        logger.error(f"Embedding failed: {e}")
        raise HTTPException(status_code=502, detail="Embedding service unavailable")

    filter_conditions = [{"key": "type", "match": {"value": "personal"}}]
    if request.category and request.category in PERSONAL_CATEGORIES:
        filter_conditions.append({"key": "category", "match": {"value": request.category}})
    if request.user_id:
        filter_conditions.append({"key": "user_id", "match": {"value": request.user_id}})

    search_body = {
        "vector": embedding,
        "limit": request.limit,
        "with_payload": True,
        "filter": {"must": filter_conditions},
    }

    async with httpx.AsyncClient(timeout=10.0) as client:
        try:
            resp = await client.post(
                f"{settings.vector_db_url}/collections/{settings.collection_name}/points/search",
                json=search_body,
            )
            resp.raise_for_status()
            data = resp.json()
        except Exception as e:
            logger.error(f"Personal fact search failed: {e}")
            raise HTTPException(status_code=502, detail="Vector database unavailable")

    results = []
    for hit in data.get("result", []):
        p = hit.get("payload", {})
        results.append({
            "id": hit.get("id"),
            "score": hit.get("score", 0),
            "category": p.get("category", ""),
            "key": p.get("key", ""),
            "value": p.get("value", ""),
            "text": p.get("text", ""),
            "created_at": p.get("created_at"),
        })

    return {"results": results, "count": len(results)}


# ── Metrics ─────────────────────────────────────────────────
@app.get("/metrics/collections")
async def collection_metrics():
    """Report collection sizes for monitoring."""
    metrics = {}
    for coll in [settings.collection_name, settings.multimodal_collection]:
        async with httpx.AsyncClient(timeout=5.0) as client:
            try:
                resp = await client.get(f"{settings.vector_db_url}/collections/{coll}")
                if resp.status_code == 200:
                    info = resp.json().get("result", {})
                    metrics[coll] = {
                        "points_count": info.get("points_count", 0),
                        "vectors_count": info.get("vectors_count", 0),
                    }
            except Exception:
                metrics[coll] = {"error": "unavailable"}
    return metrics
