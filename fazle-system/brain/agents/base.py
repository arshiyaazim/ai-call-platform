# ============================================================
# Base Agent — Abstract interface for all Fazle agents
# ============================================================
from dataclasses import dataclass, field
from typing import Any, Optional
import logging

logger = logging.getLogger("fazle-agents")


@dataclass
class AgentContext:
    """Shared context passed between agents during a request."""
    message: str
    user_name: str = "Azim"
    user_id: Optional[str] = None
    relationship: str = "self"
    conversation_id: Optional[str] = None
    memories: list[dict] = field(default_factory=list)
    tool_results: list[dict] = field(default_factory=list)
    search_results: list[dict] = field(default_factory=list)
    task_results: list[dict] = field(default_factory=list)
    metadata: dict = field(default_factory=dict)


@dataclass
class AgentResult:
    """Result returned by an agent."""
    content: Any = None
    should_continue: bool = True
    error: Optional[str] = None
    metadata: dict = field(default_factory=dict)


class BaseAgent:
    """Abstract base class for all agents."""

    name: str = "base"
    description: str = "Base agent"

    async def execute(self, ctx: AgentContext) -> AgentResult:
        """Execute the agent's task. Override in subclasses."""
        raise NotImplementedError

    async def can_handle(self, ctx: AgentContext) -> bool:
        """Check if this agent should handle the given context."""
        return False
