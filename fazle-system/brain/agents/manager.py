# ============================================================
# Agent Manager — Orchestrates multi-agent reasoning pipeline
# Routes queries to appropriate agents, merges results,
# and feeds enriched context to the LLM for final response
# ============================================================
import asyncio
import logging
from enum import Enum

from .base import AgentContext
from .conversation import ConversationAgent
from .memory_agent import MemoryAgent
from .research import ResearchAgent
from .task_agent import TaskAgent
from .tool_agent import ToolAgent

logger = logging.getLogger("fazle-agents.manager")


class QueryRoute(str, Enum):
    FAST_VOICE = "fast_voice"       # Ultra-low latency, direct Ollama
    CONVERSATION = "conversation"    # Normal conversation with memory
    FULL_PIPELINE = "full_pipeline"  # Memory + tools + research + LLM


# Keywords for query routing
_SIMPLE_PATTERNS = frozenset([
    "hi", "hello", "hey", "thanks", "thank you", "bye", "goodbye",
    "good morning", "good night", "how are you", "what's up",
    "yes", "no", "ok", "okay", "sure", "yeah", "nah",
])

_COMPLEX_KEYWORDS = frozenset([
    "remember", "schedule", "remind", "search", "find", "look up",
    "what did i", "what do you know", "tell me about", "who is",
    "create", "set up", "configure", "send email", "check calendar",
    "run code", "execute", "latest news", "weather", "price",
    "research", "how to", "explain", "summarize",
])


class AgentManager:
    """Orchestrates the multi-agent system for Fazle AI."""

    def __init__(
        self,
        ollama_url: str,
        voice_fast_model: str,
        llm_gateway_url: str,
        memory_url: str,
        tools_url: str,
        task_url: str,
    ):
        self.conversation_agent = ConversationAgent(
            ollama_url=ollama_url,
            voice_fast_model=voice_fast_model,
            llm_gateway_url=llm_gateway_url,
        )
        self.memory_agent = MemoryAgent(memory_url=memory_url)
        self.research_agent = ResearchAgent(tools_url=tools_url)
        self.task_agent = TaskAgent(task_url=task_url)
        self.tool_agent = ToolAgent(tools_url=tools_url)

        self._agents = [
            self.memory_agent,
            self.research_agent,
            self.task_agent,
            self.tool_agent,
            self.conversation_agent,  # Always last (fallback)
        ]

    @property
    def agents(self):
        return self._agents

    def route_query(self, message: str, source: str = "text") -> QueryRoute:
        """Classify query into a routing path.

        Returns:
            FAST_VOICE: For simple greetings/acknowledgments via voice
            CONVERSATION: For conversational queries that need memory
            FULL_PIPELINE: For queries requiring tools, search, or tasks
        """
        msg_lower = message.lower().strip()

        # Ultra-fast: simple greetings and short phrases via voice
        if source == "voice":
            words = msg_lower.split()
            if len(words) <= 3 and any(p in msg_lower for p in _SIMPLE_PATTERNS):
                return QueryRoute.FAST_VOICE

        # Full pipeline: complex queries needing tools/search/memory
        if any(kw in msg_lower for kw in _COMPLEX_KEYWORDS):
            return QueryRoute.FULL_PIPELINE

        # Default: normal conversation with basic memory
        return QueryRoute.CONVERSATION

    async def process(self, ctx: AgentContext, route: QueryRoute | None = None) -> dict:
        """Process a query through the appropriate agent pipeline.

        Returns dict with:
            - reply: str
            - agents_used: list[str]
            - memories: list
            - route: str
        """
        if route is None:
            route = self.route_query(ctx.message, ctx.metadata.get("source", "text"))

        agents_used = []

        if route == QueryRoute.FAST_VOICE:
            # Ultra-fast: direct conversation, skip everything
            result = await self.conversation_agent.execute(ctx)
            return {
                "reply": result.content,
                "agents_used": ["conversation"],
                "memories": [],
                "route": route.value,
            }

        if route == QueryRoute.CONVERSATION:
            # Conversation with memory: parallel memory search + response
            await self.memory_agent.execute(ctx)
            agents_used.append("memory")
            # ctx.memories is now populated by memory_agent
            return {
                "reply": None,  # Caller uses LLM with enriched context
                "agents_used": agents_used,
                "memories": ctx.memories,
                "route": route.value,
            }

        # FULL_PIPELINE: run relevant agents in parallel
        tasks = []
        agent_names = []

        for agent in self._agents:
            if agent.name == "conversation":
                continue  # Conversation handled separately at the end
            can = await agent.can_handle(ctx)
            if can:
                tasks.append(agent.execute(ctx))
                agent_names.append(agent.name)

        if tasks:
            results = await asyncio.gather(*tasks, return_exceptions=True)
            for name, result in zip(agent_names, results):
                if isinstance(result, Exception):
                    logger.error(f"Agent {name} failed: {result}")
                else:
                    agents_used.append(name)

        return {
            "reply": None,  # Caller uses LLM with enriched context
            "agents_used": agents_used,
            "memories": ctx.memories,
            "search_results": ctx.search_results,
            "tool_results": ctx.tool_results,
            "task_results": ctx.task_results,
            "route": route.value,
        }

    async def stream_fast(self, ctx: AgentContext):
        """Stream a fast voice response directly."""
        async for chunk in self.conversation_agent.stream(ctx):
            yield chunk
