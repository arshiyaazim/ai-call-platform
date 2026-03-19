# ============================================================
# Conversation Agent — Handles direct voice/text conversation
# Uses fast or full LLM pipeline based on query complexity
# ============================================================
import json
import logging
from typing import AsyncIterator

import httpx

from .base import BaseAgent, AgentContext, AgentResult

logger = logging.getLogger("fazle-agents.conversation")


class ConversationAgent(BaseAgent):
    name = "conversation"
    description = "Handles direct conversational responses via LLM"

    def __init__(self, ollama_url: str, voice_fast_model: str, llm_gateway_url: str):
        self.ollama_url = ollama_url
        self.voice_fast_model = voice_fast_model
        self.llm_gateway_url = llm_gateway_url
        self._client: httpx.AsyncClient | None = None

    def _get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                base_url=self.ollama_url,
                timeout=httpx.Timeout(connect=5.0, read=30.0, write=5.0, pool=5.0),
            )
        return self._client

    async def can_handle(self, ctx: AgentContext) -> bool:
        return True  # Conversation agent is the default fallback

    async def execute(self, ctx: AgentContext) -> AgentResult:
        """Generate a conversational response (non-streaming)."""
        messages = self._build_messages(ctx)
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                resp = await client.post(
                    f"{self.ollama_url}/api/chat",
                    json={
                        "model": self.voice_fast_model,
                        "messages": messages,
                        "stream": False,
                    },
                )
                resp.raise_for_status()
                data = resp.json()
                content = data.get("message", {}).get("content", "")
                return AgentResult(content=content)
        except Exception as e:
            logger.error(f"Conversation agent failed: {e}")
            return AgentResult(
                content="I'm having trouble right now. Give me a moment.",
                error=str(e),
            )

    async def stream(self, ctx: AgentContext) -> AsyncIterator[str]:
        """Stream conversational response tokens."""
        messages = self._build_messages(ctx)
        try:
            client = self._get_client()
            async with client.stream(
                "POST",
                "/api/generate",
                json={
                    "model": self.voice_fast_model,
                    "prompt": ctx.message,
                    "system": self._build_system_prompt(ctx),
                    "stream": True,
                    "options": {"num_ctx": 512, "num_predict": 40},
                },
            ) as resp:
                resp.raise_for_status()
                async for line in resp.aiter_lines():
                    if line.strip():
                        data = json.loads(line)
                        chunk = data.get("response", "")
                        if chunk:
                            yield chunk
                        if data.get("done", False):
                            break
        except Exception as e:
            logger.error(f"Conversation stream failed: {e}")
            yield "Sorry, I'm having trouble right now."

    def _build_system_prompt(self, ctx: AgentContext) -> str:
        memory_context = ""
        if ctx.memories:
            memory_lines = [f"- {m.get('text', '')}" for m in ctx.memories[:3]]
            memory_context = "\n\nRelevant memories:\n" + "\n".join(memory_lines)

        return (
            f"You are Azim's personal AI assistant speaking to {ctx.user_name}. "
            "Respond naturally in 1-3 sentences. Be concise, warm, and direct. "
            f"Plain text only.{memory_context}"
        )

    def _build_messages(self, ctx: AgentContext) -> list[dict]:
        return [
            {"role": "system", "content": self._build_system_prompt(ctx)},
            {"role": "user", "content": ctx.message},
        ]
