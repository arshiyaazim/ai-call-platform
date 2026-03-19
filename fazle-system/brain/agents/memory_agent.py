# ============================================================
# Memory Agent — Retrieves and stores personal memories
# Handles semantic search, personal facts, and memory updates
# ============================================================
import logging
from typing import Optional

import httpx

from .base import BaseAgent, AgentContext, AgentResult

logger = logging.getLogger("fazle-agents.memory")

# Keywords that indicate memory operations
_MEMORY_KEYWORDS = frozenset([
    "remember", "remind me", "what did i", "what do you know",
    "do you remember", "my preference", "i prefer", "i like",
    "i don't like", "my favorite", "save this", "note that",
    "forget", "who is", "tell me about",
])


class MemoryAgent(BaseAgent):
    name = "memory"
    description = "Retrieves and stores personal memories and facts"

    def __init__(self, memory_url: str):
        self.memory_url = memory_url

    async def can_handle(self, ctx: AgentContext) -> bool:
        msg = ctx.message.lower()
        return any(kw in msg for kw in _MEMORY_KEYWORDS)

    async def execute(self, ctx: AgentContext) -> AgentResult:
        """Search memories relevant to the query and detect store intents."""
        results = {}

        # Retrieve relevant memories
        memories = await self._search_memories(
            ctx.message, user_id=ctx.user_id, limit=5,
        )
        results["memories"] = memories
        ctx.memories = memories

        # Check for personal data storage intent
        store_keywords = ["remember", "save", "note", "my preference", "i prefer", "i like"]
        msg_lower = ctx.message.lower()
        if any(kw in msg_lower for kw in store_keywords):
            results["store_intent"] = True

        # Search for personal facts
        personal_facts = await self._search_personal(ctx.message, user_id=ctx.user_id)
        if personal_facts:
            results["personal_facts"] = personal_facts
            ctx.memories.extend(personal_facts)

        return AgentResult(content=results)

    async def store_memory(
        self,
        text: str,
        memory_type: str = "personal",
        user_name: str = "Azim",
        user_id: Optional[str] = None,
        content: Optional[dict] = None,
    ) -> bool:
        """Store a new memory in the vector database."""
        body: dict = {
            "type": memory_type,
            "user": user_name,
            "text": text,
            "content": content or {"text": text},
        }
        if user_id:
            body["user_id"] = user_id

        async with httpx.AsyncClient(timeout=10.0) as client:
            try:
                resp = await client.post(f"{self.memory_url}/store", json=body)
                return resp.status_code == 200
            except Exception as e:
                logger.error(f"Memory store failed: {e}")
                return False

    async def store_personal_fact(
        self,
        category: str,
        key: str,
        value: str,
        user_id: Optional[str] = None,
    ) -> bool:
        """Store a structured personal fact (preference, contact, etc.)."""
        body = {
            "type": "personal",
            "user": "Azim",
            "text": f"{category}: {key} = {value}",
            "content": {"category": category, "key": key, "value": value},
        }
        if user_id:
            body["user_id"] = user_id

        async with httpx.AsyncClient(timeout=10.0) as client:
            try:
                resp = await client.post(f"{self.memory_url}/store", json=body)
                return resp.status_code == 200
            except Exception as e:
                logger.error(f"Personal fact store failed: {e}")
                return False

    async def _search_memories(
        self, query: str, user_id: Optional[str] = None, limit: int = 5,
    ) -> list[dict]:
        body: dict = {"query": query, "limit": limit}
        if user_id:
            body["user_id"] = user_id
        async with httpx.AsyncClient(timeout=10.0) as client:
            try:
                resp = await client.post(f"{self.memory_url}/search", json=body)
                if resp.status_code == 200:
                    return resp.json().get("results", [])
            except Exception as e:
                logger.warning(f"Memory search failed: {e}")
        return []

    async def _search_personal(
        self, query: str, user_id: Optional[str] = None,
    ) -> list[dict]:
        body: dict = {
            "query": query,
            "memory_type": "personal",
            "limit": 3,
        }
        if user_id:
            body["user_id"] = user_id
        async with httpx.AsyncClient(timeout=10.0) as client:
            try:
                resp = await client.post(f"{self.memory_url}/search", json=body)
                if resp.status_code == 200:
                    return resp.json().get("results", [])
            except Exception as e:
                logger.warning(f"Personal memory search failed: {e}")
        return []
