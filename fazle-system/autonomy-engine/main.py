# ============================================================
# Fazle Autonomy Engine — Goal Decomposition & Planning
# Breaks high-level goals into actionable plans, coordinates
# multi-step autonomous execution with self-reflection
# ============================================================
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings
from prometheus_fastapi_instrumentator import Instrumentator
import httpx
import json
import logging
import uuid
import asyncio
from typing import Optional
from datetime import datetime
from enum import Enum

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("fazle-autonomy-engine")


class Settings(BaseSettings):
    brain_url: str = "http://fazle-brain:8200"
    memory_url: str = "http://fazle-memory:8300"
    tools_url: str = "http://fazle-web-intelligence:8500"
    task_url: str = "http://fazle-task-engine:8400"
    tool_engine_url: str = "http://fazle-tool-engine:9200"
    knowledge_graph_url: str = "http://fazle-knowledge-graph:9300"
    llm_gateway_url: str = "http://fazle-llm-gateway:8800"
    redis_url: str = "redis://redis:6379/6"
    max_plan_steps: int = 10
    max_retries: int = 3
    reflection_enabled: bool = True

    class Config:
        env_prefix = "AUTONOMY_"


settings = Settings()

app = FastAPI(title="Fazle Autonomy Engine", version="1.0.0")
Instrumentator().instrument(app).expose(app, endpoint="/metrics")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://fazle.iamazim.com", "https://iamazim.com"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Models ───────────────────────────────────────────────────

class PlanStatus(str, Enum):
    pending = "pending"
    planning = "planning"
    executing = "executing"
    reflecting = "reflecting"
    completed = "completed"
    failed = "failed"
    paused = "paused"


class PlanStep(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4())[:8])
    action: str
    description: str
    tool: Optional[str] = None
    depends_on: list[str] = Field(default_factory=list)
    status: str = "pending"
    result: Optional[str] = None
    error: Optional[str] = None
    started_at: Optional[str] = None
    completed_at: Optional[str] = None


class AutonomyPlan(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    goal: str
    context: Optional[str] = None
    steps: list[PlanStep] = Field(default_factory=list)
    status: PlanStatus = PlanStatus.pending
    reflection: Optional[str] = None
    created_at: str = Field(default_factory=lambda: datetime.utcnow().isoformat())
    updated_at: Optional[str] = None
    completed_at: Optional[str] = None
    retry_count: int = 0
    user_id: Optional[str] = None


class PlanRequest(BaseModel):
    goal: str
    context: Optional[str] = None
    max_steps: Optional[int] = None
    auto_execute: bool = False
    user_id: Optional[str] = None


class ExecuteRequest(BaseModel):
    plan_id: str
    step_ids: Optional[list[str]] = None


class PlanResponse(BaseModel):
    plan: AutonomyPlan
    message: str


# ── In-memory plan store ─────────────────────────────────────
_plans: dict[str, AutonomyPlan] = {}


# ── LLM helper ──────────────────────────────────────────────

async def query_llm(prompt: str, system: str = "") -> str:
    """Route LLM queries through the gateway."""
    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            resp = await client.post(
                f"{settings.llm_gateway_url}/llm/generate",
                json={
                    "prompt": prompt,
                    "system_prompt": system or "You are Fazle's autonomy planning engine. Decompose goals into concrete actionable steps.",
                    "temperature": 0.3,
                    "max_tokens": 2000,
                },
            )
            resp.raise_for_status()
            data = resp.json()
            return data.get("response", data.get("text", ""))
        except Exception as e:
            logger.error(f"LLM query failed: {e}")
            raise HTTPException(status_code=502, detail="LLM gateway unreachable")


async def retrieve_context(goal: str) -> str:
    """Pull relevant memories for planning context."""
    async with httpx.AsyncClient(timeout=10.0) as client:
        try:
            resp = await client.post(
                f"{settings.memory_url}/search",
                json={"query": goal, "top_k": 5},
            )
            if resp.status_code == 200:
                results = resp.json()
                if isinstance(results, list):
                    return "\n".join(r.get("content", "") for r in results[:5])
                return str(results)
        except Exception:
            logger.warning("Memory retrieval failed, proceeding without context")
    return ""


# ── Plan Generation ─────────────────────────────────────────

async def generate_plan(goal: str, context: Optional[str] = None, max_steps: int = 10) -> list[PlanStep]:
    """Use LLM to decompose a goal into executable steps."""
    memory_context = await retrieve_context(goal)

    prompt = f"""Decompose the following goal into concrete, executable steps.

Goal: {goal}

{"Additional context: " + context if context else ""}
{"Relevant memories: " + memory_context if memory_context else ""}

Return a JSON array of steps. Each step must have:
- "action": short action name (e.g., "web_search", "analyze", "store_memory", "notify", "code_execute", "summarize")
- "description": what this step does
- "tool": which tool to use (one of: web_search, memory_store, memory_search, code_sandbox, http_request, summarize, notify, none)
- "depends_on": array of step indices (0-based) this step depends on

Maximum {max_steps} steps. Return ONLY valid JSON array, no markdown."""

    raw = await query_llm(prompt)

    # Parse JSON from response
    try:
        # Try to extract JSON array from response
        raw = raw.strip()
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
        steps_data = json.loads(raw)
    except json.JSONDecodeError:
        # Fallback: single-step plan
        logger.warning("Failed to parse plan from LLM, using single-step fallback")
        steps_data = [{"action": "execute", "description": goal, "tool": "none", "depends_on": []}]

    steps = []
    for i, s in enumerate(steps_data[:max_steps]):
        step = PlanStep(
            action=s.get("action", f"step_{i}"),
            description=s.get("description", ""),
            tool=s.get("tool"),
            depends_on=[steps[d].id for d in s.get("depends_on", []) if d < len(steps)],
        )
        steps.append(step)

    return steps


# ── Step Execution ───────────────────────────────────────────

async def execute_step(plan: AutonomyPlan, step: PlanStep) -> str:
    """Execute a single plan step using the appropriate tool."""
    step.status = "executing"
    step.started_at = datetime.utcnow().isoformat()

    try:
        result = ""
        async with httpx.AsyncClient(timeout=30.0) as client:
            if step.tool == "web_search":
                resp = await client.post(
                    f"{settings.tools_url}/search",
                    json={"query": step.description, "max_results": 5},
                )
                result = resp.text if resp.status_code == 200 else f"Search failed: {resp.status_code}"

            elif step.tool == "memory_store":
                resp = await client.post(
                    f"{settings.memory_url}/store",
                    json={"content": step.description, "type": "autonomy_result"},
                )
                result = "Stored in memory" if resp.status_code == 200 else f"Store failed: {resp.status_code}"

            elif step.tool == "memory_search":
                resp = await client.post(
                    f"{settings.memory_url}/search",
                    json={"query": step.description, "top_k": 5},
                )
                result = resp.text if resp.status_code == 200 else f"Search failed: {resp.status_code}"

            elif step.tool == "summarize":
                # Gather previous step results for summarization
                prev_results = "\n".join(
                    f"Step '{s.action}': {s.result}"
                    for s in plan.steps if s.result and s.id != step.id
                )
                result = await query_llm(
                    f"Summarize these results:\n{prev_results}\n\nFor goal: {plan.goal}",
                    system="Provide a concise summary.",
                )

            elif step.tool in ("code_sandbox", "http_request"):
                # Route to tool execution engine
                resp = await client.post(
                    f"{settings.tool_engine_url}/tools/execute",
                    json={"tool_name": step.tool, "parameters": {"description": step.description}},
                )
                result = resp.text if resp.status_code == 200 else f"Tool exec failed: {resp.status_code}"

            else:
                # Generic: ask LLM to perform the step
                result = await query_llm(
                    f"Perform this step: {step.description}\nContext: {plan.goal}",
                )

        step.status = "completed"
        step.result = result[:2000]  # Truncate large results
        step.completed_at = datetime.utcnow().isoformat()
        return result

    except Exception as e:
        step.status = "failed"
        step.error = str(e)[:500]
        step.completed_at = datetime.utcnow().isoformat()
        raise


# ── Reflection ───────────────────────────────────────────────

async def reflect_on_plan(plan: AutonomyPlan) -> str:
    """Self-reflect on plan execution results."""
    results_summary = "\n".join(
        f"Step '{s.action}' ({s.status}): {s.result or s.error or 'no output'}"
        for s in plan.steps
    )

    prompt = f"""Reflect on this autonomous plan execution:

Goal: {plan.goal}
Steps and Results:
{results_summary}

Evaluate:
1. Was the goal achieved?
2. What worked well?
3. What could be improved?
4. Any follow-up actions needed?

Be concise."""

    return await query_llm(prompt, system="You are Fazle's reflection engine. Evaluate plan execution honestly.")


# ── Plan Execution Orchestrator ──────────────────────────────

async def execute_plan(plan_id: str, step_ids: Optional[list[str]] = None):
    """Execute a plan (all steps or specific ones)."""
    plan = _plans.get(plan_id)
    if not plan:
        raise HTTPException(status_code=404, detail="Plan not found")

    plan.status = PlanStatus.executing
    plan.updated_at = datetime.utcnow().isoformat()

    steps_to_run = plan.steps
    if step_ids:
        steps_to_run = [s for s in plan.steps if s.id in step_ids]

    # Execute steps respecting dependencies
    completed_ids = {s.id for s in plan.steps if s.status == "completed"}

    for step in steps_to_run:
        if step.status == "completed":
            continue

        # Wait for dependencies
        for dep_id in step.depends_on:
            if dep_id not in completed_ids:
                dep_step = next((s for s in plan.steps if s.id == dep_id), None)
                if dep_step and dep_step.status == "failed":
                    step.status = "skipped"
                    step.error = f"Dependency {dep_id} failed"
                    continue

        try:
            await execute_step(plan, step)
            completed_ids.add(step.id)
        except Exception as e:
            logger.error(f"Step {step.id} failed: {e}")
            if plan.retry_count < settings.max_retries:
                plan.retry_count += 1
                step.status = "pending"  # Allow retry
            else:
                step.status = "failed"

    # Reflection
    if settings.reflection_enabled:
        plan.status = PlanStatus.reflecting
        try:
            plan.reflection = await reflect_on_plan(plan)
        except Exception as e:
            logger.error(f"Reflection failed: {e}")

    # Update final status
    failed_steps = [s for s in plan.steps if s.status == "failed"]
    if failed_steps:
        plan.status = PlanStatus.failed if len(failed_steps) == len(plan.steps) else PlanStatus.completed
    else:
        plan.status = PlanStatus.completed

    plan.completed_at = datetime.utcnow().isoformat()
    plan.updated_at = datetime.utcnow().isoformat()


# ── Endpoints ────────────────────────────────────────────────

@app.get("/health")
async def health():
    return {"status": "healthy", "service": "autonomy-engine", "plans_count": len(_plans)}


@app.post("/autonomy/plan", response_model=PlanResponse)
async def create_plan(req: PlanRequest):
    """Generate an autonomous execution plan from a goal."""
    max_steps = min(req.max_steps or settings.max_plan_steps, settings.max_plan_steps)

    plan = AutonomyPlan(
        goal=req.goal,
        context=req.context,
        status=PlanStatus.planning,
        user_id=req.user_id,
    )
    _plans[plan.id] = plan

    try:
        plan.steps = await generate_plan(req.goal, req.context, max_steps)
        plan.status = PlanStatus.pending
        plan.updated_at = datetime.utcnow().isoformat()
    except Exception as e:
        plan.status = PlanStatus.failed
        plan.updated_at = datetime.utcnow().isoformat()
        raise HTTPException(status_code=500, detail=f"Plan generation failed: {e}")

    # Auto-execute if requested
    if req.auto_execute:
        asyncio.create_task(execute_plan(plan.id))
        return PlanResponse(plan=plan, message="Plan generated and execution started")

    return PlanResponse(plan=plan, message=f"Plan generated with {len(plan.steps)} steps")


@app.post("/autonomy/execute", response_model=PlanResponse)
async def trigger_execution(req: ExecuteRequest):
    """Execute a previously generated plan."""
    if req.plan_id not in _plans:
        raise HTTPException(status_code=404, detail="Plan not found")

    asyncio.create_task(execute_plan(req.plan_id, req.step_ids))
    plan = _plans[req.plan_id]
    return PlanResponse(plan=plan, message="Execution started")


@app.get("/autonomy/plan/{plan_id}", response_model=PlanResponse)
async def get_plan(plan_id: str):
    """Get plan status and details."""
    plan = _plans.get(plan_id)
    if not plan:
        raise HTTPException(status_code=404, detail="Plan not found")
    return PlanResponse(plan=plan, message=f"Plan status: {plan.status}")


@app.get("/autonomy/plans")
async def list_plans(limit: int = 20, status: Optional[str] = None):
    """List all plans, optionally filtered by status."""
    plans = list(_plans.values())
    if status:
        plans = [p for p in plans if p.status == status]
    plans.sort(key=lambda p: p.created_at, reverse=True)
    return {"plans": plans[:limit], "total": len(plans)}


@app.delete("/autonomy/plan/{plan_id}")
async def delete_plan(plan_id: str):
    """Delete a plan."""
    if plan_id not in _plans:
        raise HTTPException(status_code=404, detail="Plan not found")
    del _plans[plan_id]
    return {"message": "Plan deleted"}


@app.post("/autonomy/plan/{plan_id}/pause")
async def pause_plan(plan_id: str):
    """Pause an executing plan."""
    plan = _plans.get(plan_id)
    if not plan:
        raise HTTPException(status_code=404, detail="Plan not found")
    plan.status = PlanStatus.paused
    plan.updated_at = datetime.utcnow().isoformat()
    return {"message": "Plan paused", "plan_id": plan_id}
