# ============================================================
# Tool Agent — Plugin-based tool execution framework
# Discovers, validates, and executes structured tools
# ============================================================
import logging
from typing import Optional

import httpx

from .base import BaseAgent, AgentContext, AgentResult

logger = logging.getLogger("fazle-agents.tool")

# Keywords indicating tool usage
_TOOL_KEYWORDS = frozenset([
    "send email", "check calendar", "open file", "run code",
    "execute", "calculate", "convert", "translate",
    "create file", "list files", "send message",
])


class ToolAgent(BaseAgent):
    name = "tool"
    description = "Executes plugin-based tools (email, calendar, code, filesystem)"

    def __init__(self, tools_url: str):
        self.tools_url = tools_url
        self._tool_registry: dict[str, dict] | None = None

    async def can_handle(self, ctx: AgentContext) -> bool:
        msg = ctx.message.lower()
        return any(kw in msg for kw in _TOOL_KEYWORDS)

    async def execute(self, ctx: AgentContext) -> AgentResult:
        """Discover available tools and indicate tool execution intent."""
        tools = await self.list_tools()
        return AgentResult(
            content={
                "available_tools": [t["name"] for t in tools],
                "tool_intent_detected": True,
            },
            metadata={"requires_llm_routing": True},
        )

    async def list_tools(self) -> list[dict]:
        """Get list of available tools from the plugin registry."""
        if self._tool_registry is not None:
            return list(self._tool_registry.values())

        async with httpx.AsyncClient(timeout=10.0) as client:
            try:
                resp = await client.get(f"{self.tools_url}/plugins")
                if resp.status_code == 200:
                    tools = resp.json().get("tools", [])
                    self._tool_registry = {t["name"]: t for t in tools}
                    return tools
            except Exception as e:
                logger.warning(f"Tool registry fetch failed: {e}")
        return []

    async def execute_tool(
        self,
        tool_name: str,
        params: dict,
        user_id: Optional[str] = None,
    ) -> dict:
        """Execute a specific tool by name with given parameters."""
        body = {"tool": tool_name, "params": params}
        if user_id:
            body["user_id"] = user_id

        async with httpx.AsyncClient(timeout=30.0) as client:
            try:
                resp = await client.post(
                    f"{self.tools_url}/plugins/execute",
                    json=body,
                )
                if resp.status_code == 200:
                    return resp.json()
                return {"error": f"Tool execution returned {resp.status_code}"}
            except Exception as e:
                logger.error(f"Tool execution failed: {e}")
                return {"error": str(e)}
