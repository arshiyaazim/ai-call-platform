# ============================================================
# Fazle AI Workflow Orchestration Engine
# Multi-step AI workflow creation, execution, and monitoring
# ============================================================
import logging
import uuid
import json
import threading
import time
from datetime import datetime, timezone
from typing import Optional
from contextlib import contextmanager

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings
import psycopg2
import psycopg2.extras
import psycopg2.pool
import httpx

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("workflow-engine")

psycopg2.extras.register_uuid()


class Settings(BaseSettings):
    database_url: str = "postgresql://postgres:postgres@postgres:5432/postgres"
    llm_gateway_url: str = "http://fazle-llm-gateway:8800"
    brain_url: str = "http://fazle-brain:8200"
    tool_engine_url: str = "http://fazle-tool-engine:9200"

    class Config:
        env_prefix = "WORKFLOW_"


settings = Settings()

app = FastAPI(title="Fazle AI Workflow Engine", version="1.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://iamazim.com", "https://fazle.iamazim.com"],
    allow_methods=["*"],
    allow_headers=["*"],
)

_pool = psycopg2.pool.ThreadedConnectionPool(2, 5, settings.database_url)


@contextmanager
def _get_conn():
    conn = _pool.getconn()
    try:
        yield conn
    finally:
        _pool.putconn(conn)


# ── Database Tables ─────────────────────────────────────────

def ensure_tables():
    with _get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS fazle_ai_workflows (
                    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                    name VARCHAR(255) NOT NULL,
                    description TEXT DEFAULT '',
                    steps JSONB NOT NULL DEFAULT '[]',
                    status VARCHAR(30) NOT NULL DEFAULT 'draft',
                    trigger_type VARCHAR(30) DEFAULT 'manual',
                    current_step INT DEFAULT 0,
                    result JSONB DEFAULT '{}',
                    error TEXT DEFAULT '',
                    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                    started_at TIMESTAMPTZ,
                    completed_at TIMESTAMPTZ
                );
                CREATE INDEX IF NOT EXISTS idx_workflows_status ON fazle_ai_workflows (status);
                CREATE INDEX IF NOT EXISTS idx_workflows_created ON fazle_ai_workflows (created_at);

                CREATE TABLE IF NOT EXISTS fazle_ai_workflow_logs (
                    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                    workflow_id UUID NOT NULL REFERENCES fazle_ai_workflows(id) ON DELETE CASCADE,
                    step_index INT NOT NULL DEFAULT 0,
                    level VARCHAR(20) NOT NULL DEFAULT 'info',
                    message TEXT NOT NULL,
                    data JSONB DEFAULT '{}',
                    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                );
                CREATE INDEX IF NOT EXISTS idx_wf_logs_workflow ON fazle_ai_workflow_logs (workflow_id);
            """)
        conn.commit()
    logger.info("Workflow tables ensured")


# ── Schemas ─────────────────────────────────────────────────

class WorkflowStep(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    type: str = Field("llm_call", pattern=r"^(llm_call|tool_call|condition|delay|webhook)$")
    config: dict = Field(default_factory=dict)


class WorkflowCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    description: str = Field("", max_length=2000)
    steps: list[WorkflowStep] = Field(..., min_length=1, max_length=50)
    trigger_type: str = Field("manual", pattern=r"^(manual|schedule|event)$")


# ── Workflow Execution ──────────────────────────────────────

_running_workflows: dict[str, bool] = {}


def _add_log(conn, workflow_id: uuid.UUID, step_index: int, level: str, message: str, data: dict | None = None):
    with conn.cursor() as cur:
        cur.execute(
            """INSERT INTO fazle_ai_workflow_logs (workflow_id, step_index, level, message, data)
               VALUES (%s, %s, %s, %s, %s)""",
            (workflow_id, step_index, level, message, json.dumps(data or {})),
        )
    conn.commit()


def _execute_step(step: dict, step_index: int, context: dict) -> dict:
    """Execute a single workflow step and return the result."""
    step_type = step.get("type", "llm_call")
    config = step.get("config", {})

    if step_type == "llm_call":
        prompt = config.get("prompt", "")
        # Substitute context variables
        for key, val in context.items():
            prompt = prompt.replace(f"{{{{{key}}}}}", str(val))
        try:
            resp = httpx.post(
                f"{settings.llm_gateway_url}/v1/chat/completions",
                json={"model": config.get("model", "default"), "messages": [{"role": "user", "content": prompt}]},
                timeout=120.0,
            )
            resp.raise_for_status()
            data = resp.json()
            return {"output": data.get("choices", [{}])[0].get("message", {}).get("content", ""), "status": "completed"}
        except Exception as e:
            return {"output": "", "status": "error", "error": str(e)}

    elif step_type == "tool_call":
        tool_name = config.get("tool", "")
        tool_input = config.get("input", {})
        for key, val in context.items():
            if isinstance(tool_input, dict):
                tool_input = {k: str(v).replace(f"{{{{{key}}}}}", str(val)) for k, v in tool_input.items()}
        try:
            resp = httpx.post(
                f"{settings.tool_engine_url}/tools/{tool_name}/execute",
                json={"input": tool_input},
                timeout=120.0,
            )
            resp.raise_for_status()
            return {"output": resp.json(), "status": "completed"}
        except Exception as e:
            return {"output": None, "status": "error", "error": str(e)}

    elif step_type == "condition":
        expr = config.get("expression", "true")
        # Simple truthiness check on context
        check_key = config.get("check_key", "")
        check_val = context.get(check_key, "")
        passed = bool(check_val) if expr == "truthy" else str(check_val) == str(config.get("expected", ""))
        return {"output": passed, "status": "completed", "condition_passed": passed}

    elif step_type == "delay":
        seconds = min(config.get("seconds", 5), 300)
        time.sleep(seconds)
        return {"output": f"Waited {seconds}s", "status": "completed"}

    elif step_type == "webhook":
        url = config.get("url", "")
        method = config.get("method", "POST").upper()
        if not url:
            return {"output": None, "status": "error", "error": "No webhook URL provided"}
        try:
            resp = httpx.request(method, url, json=context, timeout=30.0)
            return {"output": resp.text[:2000], "status": "completed", "status_code": resp.status_code}
        except Exception as e:
            return {"output": None, "status": "error", "error": str(e)}

    return {"output": None, "status": "error", "error": f"Unknown step type: {step_type}"}


def _run_workflow(workflow_id: uuid.UUID):
    """Background thread that executes a workflow step-by-step."""
    wf_key = str(workflow_id)
    _running_workflows[wf_key] = True
    context: dict = {}

    try:
        with _get_conn() as conn:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute("SELECT * FROM fazle_ai_workflows WHERE id = %s", (workflow_id,))
                wf = cur.fetchone()
            if not wf:
                return

            steps = wf["steps"] if isinstance(wf["steps"], list) else json.loads(wf["steps"])
            _add_log(conn, workflow_id, 0, "info", f"Workflow '{wf['name']}' started with {len(steps)} steps")

        for idx, step in enumerate(steps):
            if not _running_workflows.get(wf_key, False):
                # Stopped externally
                with _get_conn() as conn:
                    with conn.cursor() as cur:
                        cur.execute("UPDATE fazle_ai_workflows SET status = 'stopped', current_step = %s WHERE id = %s", (idx, workflow_id))
                    conn.commit()
                    _add_log(conn, workflow_id, idx, "warn", "Workflow stopped by user")
                return

            with _get_conn() as conn:
                with conn.cursor() as cur:
                    cur.execute("UPDATE fazle_ai_workflows SET current_step = %s, status = 'running' WHERE id = %s", (idx, workflow_id))
                conn.commit()
                _add_log(conn, workflow_id, idx, "info", f"Executing step {idx}: {step.get('name', 'unnamed')}")

            result = _execute_step(step, idx, context)

            with _get_conn() as conn:
                if result.get("status") == "error":
                    _add_log(conn, workflow_id, idx, "error", f"Step failed: {result.get('error', 'unknown')}")
                    with conn.cursor() as cur:
                        cur.execute(
                            "UPDATE fazle_ai_workflows SET status = 'failed', error = %s, current_step = %s, result = %s WHERE id = %s",
                            (result.get("error", ""), idx, json.dumps(context), workflow_id),
                        )
                    conn.commit()
                    return
                else:
                    context[f"step_{idx}_output"] = result.get("output", "")
                    context[step.get("name", f"step_{idx}")] = result.get("output", "")
                    _add_log(conn, workflow_id, idx, "info", f"Step {idx} completed successfully")

        # All steps done
        with _get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "UPDATE fazle_ai_workflows SET status = 'completed', result = %s, completed_at = NOW() WHERE id = %s",
                    (json.dumps(context), workflow_id),
                )
            conn.commit()
            _add_log(conn, workflow_id, len(steps), "info", "Workflow completed successfully")

    except Exception as e:
        logger.exception("Workflow execution error")
        try:
            with _get_conn() as conn:
                with conn.cursor() as cur:
                    cur.execute("UPDATE fazle_ai_workflows SET status = 'failed', error = %s WHERE id = %s", (str(e), workflow_id))
                conn.commit()
                _add_log(conn, workflow_id, 0, "error", f"Workflow crashed: {e}")
        except Exception:
            pass
    finally:
        _running_workflows.pop(wf_key, None)


# ── Routes ──────────────────────────────────────────────────

@app.on_event("startup")
async def startup():
    ensure_tables()


@app.get("/health")
async def health():
    return {"status": "ok", "service": "workflow-engine", "version": "1.0.0"}


@app.post("/workflows/create")
async def create_workflow(req: WorkflowCreate):
    steps_json = [s.model_dump() for s in req.steps]
    with _get_conn() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                """INSERT INTO fazle_ai_workflows (name, description, steps, trigger_type)
                   VALUES (%s, %s, %s, %s) RETURNING *""",
                (req.name, req.description, json.dumps(steps_json), req.trigger_type),
            )
            row = dict(cur.fetchone())
        conn.commit()
    return _serialize_workflow(row)


@app.get("/workflows")
async def list_workflows(status: str | None = None, limit: int = 50):
    limit = min(limit, 200)
    with _get_conn() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            if status:
                cur.execute(
                    "SELECT * FROM fazle_ai_workflows WHERE status = %s ORDER BY created_at DESC LIMIT %s",
                    (status, limit),
                )
            else:
                cur.execute("SELECT * FROM fazle_ai_workflows ORDER BY created_at DESC LIMIT %s", (limit,))
            rows = [dict(r) for r in cur.fetchall()]
    return {"workflows": [_serialize_workflow(r) for r in rows]}


@app.get("/workflows/{workflow_id}")
async def get_workflow(workflow_id: uuid.UUID):
    with _get_conn() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute("SELECT * FROM fazle_ai_workflows WHERE id = %s", (workflow_id,))
            row = cur.fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Workflow not found")
    return _serialize_workflow(dict(row))


@app.post("/workflows/{workflow_id}/start")
async def start_workflow(workflow_id: uuid.UUID):
    with _get_conn() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute("SELECT * FROM fazle_ai_workflows WHERE id = %s", (workflow_id,))
            row = cur.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Workflow not found")
        if row["status"] == "running":
            raise HTTPException(status_code=409, detail="Workflow already running")

        with conn.cursor() as cur:
            cur.execute(
                "UPDATE fazle_ai_workflows SET status = 'running', started_at = NOW(), error = '' WHERE id = %s",
                (workflow_id,),
            )
        conn.commit()

    thread = threading.Thread(target=_run_workflow, args=(workflow_id,), daemon=True)
    thread.start()
    return {"status": "started", "workflow_id": str(workflow_id)}


@app.post("/workflows/{workflow_id}/stop")
async def stop_workflow(workflow_id: uuid.UUID):
    wf_key = str(workflow_id)
    if wf_key in _running_workflows:
        _running_workflows[wf_key] = False
        return {"status": "stop_requested", "workflow_id": wf_key}
    with _get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE fazle_ai_workflows SET status = 'stopped' WHERE id = %s AND status = 'running'",
                (workflow_id,),
            )
        conn.commit()
    return {"status": "stopped", "workflow_id": wf_key}


@app.get("/workflows/{workflow_id}/logs")
async def workflow_logs(workflow_id: uuid.UUID, limit: int = 100):
    limit = min(limit, 500)
    with _get_conn() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                """SELECT * FROM fazle_ai_workflow_logs
                   WHERE workflow_id = %s ORDER BY created_at ASC LIMIT %s""",
                (workflow_id, limit),
            )
            rows = [dict(r) for r in cur.fetchall()]
    return {"logs": [_serialize_log(r) for r in rows]}


@app.delete("/workflows/{workflow_id}")
async def delete_workflow(workflow_id: uuid.UUID):
    wf_key = str(workflow_id)
    if wf_key in _running_workflows:
        raise HTTPException(status_code=409, detail="Cannot delete a running workflow")
    with _get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM fazle_ai_workflows WHERE id = %s", (workflow_id,))
            deleted = cur.rowcount
        conn.commit()
    if not deleted:
        raise HTTPException(status_code=404, detail="Workflow not found")
    return {"deleted": True}


# ── Helpers ─────────────────────────────────────────────────

def _serialize_workflow(row: dict) -> dict:
    return {
        "id": str(row["id"]),
        "name": row["name"],
        "description": row.get("description", ""),
        "steps": row["steps"] if isinstance(row["steps"], list) else json.loads(row["steps"]),
        "status": row["status"],
        "trigger_type": row.get("trigger_type", "manual"),
        "current_step": row.get("current_step", 0),
        "result": row.get("result", {}),
        "error": row.get("error", ""),
        "created_at": row["created_at"].isoformat() if row.get("created_at") else None,
        "started_at": row["started_at"].isoformat() if row.get("started_at") else None,
        "completed_at": row["completed_at"].isoformat() if row.get("completed_at") else None,
    }


def _serialize_log(row: dict) -> dict:
    return {
        "id": str(row["id"]),
        "workflow_id": str(row["workflow_id"]),
        "step_index": row["step_index"],
        "level": row["level"],
        "message": row["message"],
        "data": row.get("data", {}),
        "created_at": row["created_at"].isoformat() if row.get("created_at") else None,
    }
