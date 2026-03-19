# ============================================================
# Task Agent — Autonomous task scheduling and execution
# Creates reminders, schedules jobs, manages follow-ups
# ============================================================
import logging
from typing import Optional

import httpx

from .base import BaseAgent, AgentContext, AgentResult

logger = logging.getLogger("fazle-agents.task")

# Keywords indicating task/scheduling needs
_TASK_KEYWORDS = frozenset([
    "remind", "schedule", "set up", "create task",
    "follow up", "in 5 minutes", "in an hour", "tomorrow",
    "next week", "every day", "alert me", "notify",
    "appointment", "meeting", "call back",
])


class TaskAgent(BaseAgent):
    name = "task"
    description = "Schedules tasks, reminders, and autonomous jobs"

    def __init__(self, task_url: str):
        self.task_url = task_url

    async def can_handle(self, ctx: AgentContext) -> bool:
        msg = ctx.message.lower()
        return any(kw in msg for kw in _TASK_KEYWORDS)

    async def execute(self, ctx: AgentContext) -> AgentResult:
        """Detect task intent and create if appropriate."""
        # This agent prepares task metadata; the Brain LLM extracts specifics
        return AgentResult(
            content={"task_intent_detected": True, "message": ctx.message},
            metadata={"requires_llm_extraction": True},
        )

    async def create_task(
        self,
        title: str,
        description: str = "",
        task_type: str = "reminder",
        scheduled_at: Optional[str] = None,
        payload: Optional[dict] = None,
    ) -> dict | None:
        """Create a scheduled task via the Task Engine."""
        body = {
            "title": title,
            "description": description,
            "task_type": task_type,
            "scheduled_at": scheduled_at,
            "payload": payload or {},
        }
        async with httpx.AsyncClient(timeout=10.0) as client:
            try:
                resp = await client.post(f"{self.task_url}/tasks", json=body)
                if resp.status_code == 200:
                    return resp.json()
            except Exception as e:
                logger.error(f"Task creation failed: {e}")
        return None

    async def list_tasks(
        self, status: Optional[str] = None, task_type: Optional[str] = None,
    ) -> list[dict]:
        """List existing tasks."""
        params = {}
        if status:
            params["status"] = status
        if task_type:
            params["task_type"] = task_type
        async with httpx.AsyncClient(timeout=10.0) as client:
            try:
                resp = await client.get(f"{self.task_url}/tasks", params=params)
                if resp.status_code == 200:
                    return resp.json().get("tasks", [])
            except Exception as e:
                logger.warning(f"Task list failed: {e}")
        return []
