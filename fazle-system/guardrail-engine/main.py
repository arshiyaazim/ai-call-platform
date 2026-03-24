# ============================================================
# Fazle AI Safety Guardrail Engine
# Risk scoring, policy enforcement, and approval workflows
# ============================================================
import logging
import uuid
from datetime import datetime, timezone
from typing import Optional

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("guardrail-engine")


class Settings(BaseSettings):
    database_url: str = "postgresql://postgres:postgres@postgres:5432/postgres"

    class Config:
        env_prefix = "FAZLE_"


settings = Settings()

app = FastAPI(title="Fazle AI Safety Guardrail Engine", version="1.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://iamazim.com", "https://fazle.iamazim.com"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Database ────────────────────────────────────────────────
import psycopg2
import psycopg2.extras
import psycopg2.pool

psycopg2.extras.register_uuid()
_pool = psycopg2.pool.ThreadedConnectionPool(2, 5, settings.database_url)


from contextlib import contextmanager

@contextmanager
def _get_conn():
    conn = _pool.getconn()
    try:
        yield conn
    finally:
        _pool.putconn(conn)


def ensure_guardrail_tables():
    with _get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS fazle_ai_policies (
                    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                    name VARCHAR(200) NOT NULL,
                    description TEXT DEFAULT '',
                    category VARCHAR(50) NOT NULL DEFAULT 'general',
                    severity VARCHAR(20) NOT NULL DEFAULT 'medium',
                    rule_type VARCHAR(50) NOT NULL DEFAULT 'keyword',
                    rule_config JSONB NOT NULL DEFAULT '{}',
                    enabled BOOLEAN DEFAULT true,
                    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                );
                CREATE INDEX IF NOT EXISTS idx_policies_category ON fazle_ai_policies (category);
                CREATE INDEX IF NOT EXISTS idx_policies_enabled ON fazle_ai_policies (enabled);

                CREATE TABLE IF NOT EXISTS fazle_ai_action_logs (
                    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                    action_type VARCHAR(100) NOT NULL,
                    input_text TEXT DEFAULT '',
                    risk_score FLOAT NOT NULL DEFAULT 0.0,
                    risk_level VARCHAR(20) NOT NULL DEFAULT 'low',
                    policies_triggered TEXT[] DEFAULT '{}',
                    decision VARCHAR(20) NOT NULL DEFAULT 'allowed',
                    review_status VARCHAR(20) DEFAULT 'none',
                    reviewed_by VARCHAR(100) DEFAULT '',
                    review_notes TEXT DEFAULT '',
                    metadata JSONB DEFAULT '{}',
                    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                );
                CREATE INDEX IF NOT EXISTS idx_action_logs_risk ON fazle_ai_action_logs (risk_level);
                CREATE INDEX IF NOT EXISTS idx_action_logs_decision ON fazle_ai_action_logs (decision);
                CREATE INDEX IF NOT EXISTS idx_action_logs_created ON fazle_ai_action_logs (created_at);

                -- Default policies if empty
                INSERT INTO fazle_ai_policies (name, description, category, severity, rule_type, rule_config)
                SELECT * FROM (VALUES
                    ('Block harmful content', 'Blocks requests containing harmful, violent, or hateful content', 'content_safety', 'critical', 'keyword',
                     '{"keywords": ["hack into", "attack system", "steal data", "destroy", "malware", "exploit vulnerability"]}'),
                    ('PII protection', 'Flags requests that may expose personal identifiable information', 'privacy', 'high', 'pattern',
                     '{"patterns": ["\\\\b\\\\d{3}-\\\\d{2}-\\\\d{4}\\\\b", "\\\\b\\\\d{16}\\\\b", "\\\\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\\\\.[A-Z|a-z]{2,}\\\\b"]}'),
                    ('Rate limiting', 'Limits excessive autonomous actions', 'operational', 'medium', 'rate_limit',
                     '{"max_actions_per_hour": 100, "max_actions_per_minute": 10}'),
                    ('External API guard', 'Requires approval for external API calls', 'operational', 'high', 'approval_required',
                     '{"action_types": ["external_api_call", "web_search", "file_upload"]}'),
                    ('Data deletion guard', 'Requires approval before deleting any data', 'data_safety', 'critical', 'approval_required',
                     '{"action_types": ["delete_memory", "delete_user", "delete_conversation"]}')
                ) AS v(name, description, category, severity, rule_type, rule_config)
                WHERE NOT EXISTS (SELECT 1 FROM fazle_ai_policies LIMIT 1);
            """)
        conn.commit()
    logger.info("Guardrail tables ensured (ai_policies, ai_action_logs)")


# ── Schemas ─────────────────────────────────────────────────

class PolicyCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    description: str = Field("", max_length=2000)
    category: str = Field("general", max_length=50)
    severity: str = Field("medium", pattern=r"^(low|medium|high|critical)$")
    rule_type: str = Field("keyword", max_length=50)
    rule_config: dict = Field(default_factory=dict)
    enabled: bool = True


class PolicyUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=200)
    description: Optional[str] = Field(None, max_length=2000)
    category: Optional[str] = Field(None, max_length=50)
    severity: Optional[str] = Field(None, pattern=r"^(low|medium|high|critical)$")
    rule_type: Optional[str] = Field(None, max_length=50)
    rule_config: Optional[dict] = None
    enabled: Optional[bool] = None


class RiskCheckRequest(BaseModel):
    action_type: str = Field(..., min_length=1, max_length=100)
    input_text: str = Field("", max_length=10000)
    metadata: dict = Field(default_factory=dict)


class ReviewRequest(BaseModel):
    decision: str = Field(..., pattern=r"^(approved|rejected)$")
    reviewed_by: str = Field(..., min_length=1, max_length=100)
    review_notes: str = Field("", max_length=2000)


# ── Risk Scoring Engine ────────────────────────────────────

import json
import re


def evaluate_risk(action_type: str, input_text: str, metadata: dict) -> dict:
    """Evaluate risk against all enabled policies. Returns risk assessment."""
    with _get_conn() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute("SELECT * FROM fazle_ai_policies WHERE enabled = true")
            policies = [dict(r) for r in cur.fetchall()]

    risk_score = 0.0
    triggered = []
    requires_approval = False
    severity_weights = {"low": 0.1, "medium": 0.3, "high": 0.6, "critical": 1.0}

    for policy in policies:
        config = policy["rule_config"] if isinstance(policy["rule_config"], dict) else json.loads(policy["rule_config"])
        hit = False

        if policy["rule_type"] == "keyword":
            keywords = config.get("keywords", [])
            text_lower = input_text.lower()
            hit = any(kw.lower() in text_lower for kw in keywords)

        elif policy["rule_type"] == "pattern":
            patterns = config.get("patterns", [])
            for pat in patterns:
                try:
                    if re.search(pat, input_text):
                        hit = True
                        break
                except re.error:
                    pass

        elif policy["rule_type"] == "approval_required":
            action_types = config.get("action_types", [])
            if action_type in action_types:
                hit = True
                requires_approval = True

        elif policy["rule_type"] == "rate_limit":
            # Check action count in the last hour
            max_per_hour = config.get("max_actions_per_hour", 100)
            with _get_conn() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        """SELECT COUNT(*) FROM fazle_ai_action_logs
                           WHERE action_type = %s AND created_at > NOW() - INTERVAL '1 hour'""",
                        (action_type,),
                    )
                    count = cur.fetchone()[0]
                    if count >= max_per_hour:
                        hit = True

        if hit:
            weight = severity_weights.get(policy["severity"], 0.3)
            risk_score += weight
            triggered.append(policy["name"])

    # Normalize score to 0-1 range
    risk_score = min(risk_score, 1.0)

    # Determine risk level
    if risk_score >= 0.7:
        risk_level = "critical"
    elif risk_score >= 0.4:
        risk_level = "high"
    elif risk_score >= 0.2:
        risk_level = "medium"
    else:
        risk_level = "low"

    # Determine decision
    if risk_level == "critical":
        decision = "blocked"
    elif requires_approval or risk_level == "high":
        decision = "pending_approval"
    else:
        decision = "allowed"

    return {
        "risk_score": round(risk_score, 3),
        "risk_level": risk_level,
        "policies_triggered": triggered,
        "decision": decision,
        "requires_approval": requires_approval,
    }


# ── Endpoints ───────────────────────────────────────────────

@app.on_event("startup")
def startup():
    try:
        ensure_guardrail_tables()
    except Exception as e:
        logger.error(f"Failed to ensure guardrail tables: {e}")


@app.get("/health")
async def health():
    return {"status": "healthy", "service": "guardrail-engine", "timestamp": datetime.now(timezone.utc).isoformat()}


@app.post("/guardrail/check")
async def check_risk(request: RiskCheckRequest):
    """Evaluate an action against all safety policies."""
    result = evaluate_risk(request.action_type, request.input_text, request.metadata)

    # Log the action
    with _get_conn() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                """INSERT INTO fazle_ai_action_logs
                   (action_type, input_text, risk_score, risk_level, policies_triggered, decision, metadata)
                   VALUES (%s, %s, %s, %s, %s, %s, %s)
                   RETURNING id""",
                (
                    request.action_type,
                    request.input_text[:500],  # Truncate for storage
                    result["risk_score"],
                    result["risk_level"],
                    result["policies_triggered"],
                    result["decision"],
                    json.dumps(request.metadata),
                ),
            )
            conn.commit()
            log_id = str(cur.fetchone()["id"])

    result["log_id"] = log_id
    return result


@app.get("/guardrail/policies")
async def list_policies():
    """List all safety policies."""
    with _get_conn() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute("SELECT * FROM fazle_ai_policies ORDER BY category, severity DESC, created_at")
            policies = [dict(r) for r in cur.fetchall()]
            for p in policies:
                p["id"] = str(p["id"])
                p["created_at"] = p["created_at"].isoformat()
                p["updated_at"] = p["updated_at"].isoformat()
    return {"policies": policies}


@app.post("/guardrail/policies")
async def create_policy(request: PolicyCreate):
    """Create a new safety policy."""
    with _get_conn() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                """INSERT INTO fazle_ai_policies (name, description, category, severity, rule_type, rule_config, enabled)
                   VALUES (%s, %s, %s, %s, %s, %s, %s) RETURNING *""",
                (request.name, request.description, request.category, request.severity,
                 request.rule_type, json.dumps(request.rule_config), request.enabled),
            )
            conn.commit()
            row = dict(cur.fetchone())
            row["id"] = str(row["id"])
            row["created_at"] = row["created_at"].isoformat()
            row["updated_at"] = row["updated_at"].isoformat()
    return row


@app.put("/guardrail/policies/{policy_id}")
async def update_policy(policy_id: str, request: PolicyUpdate):
    """Update a safety policy."""
    updates = request.model_dump(exclude_none=True)
    if not updates:
        raise HTTPException(status_code=400, detail="No fields to update")

    if "rule_config" in updates:
        updates["rule_config"] = json.dumps(updates["rule_config"])

    set_clause = ", ".join(f"{k} = %s" for k in updates)
    values = list(updates.values()) + [policy_id]

    with _get_conn() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                f"UPDATE fazle_ai_policies SET {set_clause}, updated_at = NOW() WHERE id = %s RETURNING *",
                values,
            )
            conn.commit()
            row = cur.fetchone()
            if not row:
                raise HTTPException(status_code=404, detail="Policy not found")
            row = dict(row)
            row["id"] = str(row["id"])
            row["created_at"] = row["created_at"].isoformat()
            row["updated_at"] = row["updated_at"].isoformat()
    return row


@app.delete("/guardrail/policies/{policy_id}")
async def delete_policy(policy_id: str):
    """Delete a safety policy."""
    with _get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM fazle_ai_policies WHERE id = %s", (policy_id,))
            conn.commit()
            if cur.rowcount == 0:
                raise HTTPException(status_code=404, detail="Policy not found")
    return {"status": "deleted"}


@app.put("/guardrail/policies/{policy_id}/toggle")
async def toggle_policy(policy_id: str):
    """Toggle a policy's enabled state."""
    with _get_conn() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                "UPDATE fazle_ai_policies SET enabled = NOT enabled, updated_at = NOW() WHERE id = %s RETURNING id, enabled",
                (policy_id,),
            )
            conn.commit()
            row = cur.fetchone()
            if not row:
                raise HTTPException(status_code=404, detail="Policy not found")
    return {"id": str(row["id"]), "enabled": row["enabled"]}


@app.get("/guardrail/logs")
async def list_action_logs(
    limit: int = 50,
    risk_level: Optional[str] = None,
    decision: Optional[str] = None,
):
    """List AI action logs with optional filters."""
    query = "SELECT * FROM fazle_ai_action_logs WHERE 1=1"
    params: list = []

    if risk_level:
        query += " AND risk_level = %s"
        params.append(risk_level)
    if decision:
        query += " AND decision = %s"
        params.append(decision)

    query += " ORDER BY created_at DESC LIMIT %s"
    params.append(min(limit, 500))

    with _get_conn() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(query, params)
            logs = [dict(r) for r in cur.fetchall()]
            for log in logs:
                log["id"] = str(log["id"])
                log["created_at"] = log["created_at"].isoformat()

    return {"logs": logs}


@app.post("/guardrail/logs/{log_id}/review")
async def review_action(log_id: str, request: ReviewRequest):
    """Review a pending action (approve or reject)."""
    with _get_conn() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                """UPDATE fazle_ai_action_logs
                   SET review_status = %s, decision = %s, reviewed_by = %s, review_notes = %s
                   WHERE id = %s AND decision = 'pending_approval'
                   RETURNING id, decision, review_status""",
                (request.decision, request.decision, request.reviewed_by, request.review_notes, log_id),
            )
            conn.commit()
            row = cur.fetchone()
            if not row:
                raise HTTPException(status_code=404, detail="Action log not found or already reviewed")
    return {"id": str(row["id"]), "decision": row["decision"], "review_status": row["review_status"]}


@app.get("/guardrail/stats")
async def guardrail_stats():
    """Get guardrail statistics."""
    with _get_conn() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute("SELECT COUNT(*) AS total FROM fazle_ai_policies WHERE enabled = true")
            active_policies = cur.fetchone()["total"]

            cur.execute("SELECT COUNT(*) AS total FROM fazle_ai_action_logs")
            total_checks = cur.fetchone()["total"]

            cur.execute("SELECT COUNT(*) AS total FROM fazle_ai_action_logs WHERE decision = 'blocked'")
            blocked = cur.fetchone()["total"]

            cur.execute("SELECT COUNT(*) AS total FROM fazle_ai_action_logs WHERE decision = 'pending_approval'")
            pending = cur.fetchone()["total"]

            cur.execute("""
                SELECT risk_level, COUNT(*) AS count
                FROM fazle_ai_action_logs
                GROUP BY risk_level
            """)
            risk_dist = {r["risk_level"]: r["count"] for r in cur.fetchall()}

            cur.execute("""
                SELECT COUNT(*) AS total FROM fazle_ai_action_logs
                WHERE created_at > NOW() - INTERVAL '24 hours'
            """)
            last_24h = cur.fetchone()["total"]

    return {
        "active_policies": active_policies,
        "total_checks": total_checks,
        "blocked_actions": blocked,
        "pending_approvals": pending,
        "checks_last_24h": last_24h,
        "risk_distribution": risk_dist,
    }
