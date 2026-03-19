# ============================================================
# Fazle Self-Learning Engine — Pattern & Improvement Analysis
# Analyzes conversation patterns, detects recurring themes,
# optimizes agent routing, and generates improvement insights
# ============================================================
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings
from prometheus_fastapi_instrumentator import Instrumentator
import httpx
import json
import logging
import uuid
from typing import Optional, Any
from datetime import datetime
from enum import Enum
from collections import defaultdict

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("fazle-self-learning")


class Settings(BaseSettings):
    memory_url: str = "http://fazle-memory:8300"
    brain_url: str = "http://fazle-brain:8200"
    llm_gateway_url: str = "http://fazle-llm-gateway:8800"
    learning_engine_url: str = "http://fazle-learning-engine:8900"
    knowledge_graph_url: str = "http://fazle-knowledge-graph:9300"
    redis_url: str = "redis://redis:6379/10"
    analysis_batch_size: int = 20
    min_pattern_occurrences: int = 3

    class Config:
        env_prefix = "SELF_LEARNING_"


settings = Settings()

app = FastAPI(title="Fazle Self-Learning Engine", version="1.0.0")
Instrumentator().instrument(app).expose(app, endpoint="/metrics")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://fazle.iamazim.com", "https://iamazim.com"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Models ───────────────────────────────────────────────────

class InsightType(str, Enum):
    pattern = "pattern"
    preference = "preference"
    improvement = "improvement"
    routing_optimization = "routing_optimization"
    knowledge_gap = "knowledge_gap"
    behavioral = "behavioral"


class LearningInsight(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    insight_type: InsightType
    title: str
    description: str
    confidence: float = 0.5
    evidence_count: int = 1
    action_suggested: Optional[str] = None
    applied: bool = False
    created_at: str = Field(default_factory=lambda: datetime.utcnow().isoformat())
    updated_at: Optional[str] = None


class AnalyzeRequest(BaseModel):
    conversations: Optional[list[dict]] = None
    text: Optional[str] = None
    focus_area: Optional[str] = None


class ImproveRequest(BaseModel):
    insight_id: Optional[str] = None
    area: Optional[str] = None  # "routing", "persona", "knowledge", "tools"
    auto_apply: bool = False


class RoutingMetric(BaseModel):
    agent_name: str
    total_queries: int = 0
    successful: int = 0
    avg_latency_ms: float = 0
    user_satisfaction: float = 0


class LearningStats(BaseModel):
    total_insights: int = 0
    applied_insights: int = 0
    patterns_detected: int = 0
    routing_optimizations: int = 0
    analysis_runs: int = 0
    last_analysis: Optional[str] = None


# ── In-memory stores ────────────────────────────────────────

_insights: dict[str, LearningInsight] = {}
_routing_metrics: dict[str, RoutingMetric] = {}
_analysis_count: int = 0
_last_analysis: Optional[str] = None
_conversation_patterns: defaultdict = defaultdict(int)


# ── Analysis Logic ──────────────────────────────────────────

async def analyze_conversations(conversations: list[dict] = None, text: str = None, focus: str = None) -> list[LearningInsight]:
    """Analyze conversation data using LLM to extract patterns and insights."""
    global _analysis_count, _last_analysis

    # Gather context
    context = ""
    if text:
        context = text[:5000]
    elif conversations:
        context = json.dumps(conversations[:20], default=str)[:5000]
    else:
        # Fetch recent from memory
        async with httpx.AsyncClient(timeout=15.0) as client:
            try:
                resp = await client.post(
                    f"{settings.memory_url}/search",
                    json={"query": "recent conversation interaction", "top_k": settings.analysis_batch_size},
                )
                if resp.status_code == 200:
                    context = resp.text[:5000]
            except Exception:
                pass

    if not context:
        return []

    focus_instruction = f"\nFocus specifically on: {focus}" if focus else ""

    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.post(
            f"{settings.llm_gateway_url}/llm/generate",
            json={
                "prompt": f"""Analyze these conversation data and extract learning insights.
{focus_instruction}

Data:
{context}

Return a JSON array of insights. Each insight must have:
- "type": one of "pattern", "preference", "improvement", "routing_optimization", "knowledge_gap", "behavioral"
- "title": short insight title
- "description": detailed description
- "confidence": float 0-1
- "action_suggested": optional recommended action

Look for:
1. Recurring user patterns/preferences
2. Topics the AI struggled with
3. Agent routing that could be optimized
4. Knowledge gaps to fill
5. Behavioral improvements

Return ONLY valid JSON array.""",
                "system_prompt": "You are Fazle's self-learning analysis engine. Extract actionable insights from conversation data.",
                "temperature": 0.3,
                "max_tokens": 1500,
            },
        )

        insights = []
        if resp.status_code == 200:
            data = resp.json()
            raw = data.get("response", data.get("text", "[]"))
            raw = raw.strip()
            if raw.startswith("```"):
                raw = raw.split("```")[1]
                if raw.startswith("json"):
                    raw = raw[4:]
            try:
                parsed = json.loads(raw)
                for item in parsed:
                    try:
                        insight_type = InsightType(item.get("type", "pattern"))
                    except ValueError:
                        insight_type = InsightType.pattern
                    insight = LearningInsight(
                        insight_type=insight_type,
                        title=item.get("title", "Unnamed insight"),
                        description=item.get("description", ""),
                        confidence=min(max(float(item.get("confidence", 0.5)), 0), 1),
                        action_suggested=item.get("action_suggested"),
                    )
                    _insights[insight.id] = insight
                    insights.append(insight)
            except (json.JSONDecodeError, TypeError):
                logger.warning("Failed to parse insights from LLM")

    _analysis_count += 1
    _last_analysis = datetime.utcnow().isoformat()
    return insights


async def generate_improvement(area: str = None) -> dict:
    """Generate specific improvement recommendations."""
    current_insights = [
        {"type": i.insight_type, "title": i.title, "description": i.description, "confidence": i.confidence}
        for i in _insights.values() if not i.applied
    ]

    async with httpx.AsyncClient(timeout=20.0) as client:
        resp = await client.post(
            f"{settings.llm_gateway_url}/llm/generate",
            json={
                "prompt": f"""Based on these existing insights, generate concrete improvement recommendations.

{"Focus area: " + area if area else ""}

Current insights:
{json.dumps(current_insights[:20], default=str)}

Provide:
1. Top 3 priority improvements
2. Specific actions for each
3. Expected impact

Be concise and actionable.""",
                "system_prompt": "You are Fazle's improvement engine. Generate practical, specific improvements.",
                "temperature": 0.3,
                "max_tokens": 800,
            },
        )
        if resp.status_code == 200:
            data = resp.json()
            return {"recommendations": data.get("response", data.get("text", "")), "based_on_insights": len(current_insights)}
        return {"recommendations": "Unable to generate improvements", "based_on_insights": 0}


# ── Routing Analysis ────────────────────────────────────────

def record_routing_metric(agent_name: str, success: bool, latency_ms: float):
    """Record a routing metric for analysis."""
    if agent_name not in _routing_metrics:
        _routing_metrics[agent_name] = RoutingMetric(agent_name=agent_name)
    m = _routing_metrics[agent_name]
    m.total_queries += 1
    if success:
        m.successful += 1
    # Running average
    m.avg_latency_ms = (m.avg_latency_ms * (m.total_queries - 1) + latency_ms) / m.total_queries


# ── Endpoints ────────────────────────────────────────────────

@app.get("/health")
async def health():
    return {
        "status": "healthy",
        "service": "self-learning",
        "insights_count": len(_insights),
        "analysis_runs": _analysis_count,
    }


@app.post("/learning/analyze")
async def analyze(req: AnalyzeRequest):
    """Analyze conversations to extract learning insights."""
    insights = await analyze_conversations(req.conversations, req.text, req.focus_area)
    return {
        "insights": insights,
        "total_new": len(insights),
        "total_insights": len(_insights),
    }


@app.post("/learning/improve")
async def improve(req: ImproveRequest):
    """Generate improvement recommendations."""
    if req.insight_id:
        insight = _insights.get(req.insight_id)
        if not insight:
            raise HTTPException(status_code=404, detail="Insight not found")
        if req.auto_apply:
            insight.applied = True
            insight.updated_at = datetime.utcnow().isoformat()
        return {"insight": insight, "applied": req.auto_apply}

    result = await generate_improvement(req.area)
    return result


@app.get("/learning/insights")
async def list_insights(
    insight_type: Optional[str] = None,
    applied: Optional[bool] = None,
    min_confidence: float = 0.0,
    limit: int = Query(default=50, le=200),
):
    """List learning insights."""
    insights = list(_insights.values())
    if insight_type:
        insights = [i for i in insights if i.insight_type == insight_type]
    if applied is not None:
        insights = [i for i in insights if i.applied == applied]
    insights = [i for i in insights if i.confidence >= min_confidence]
    insights.sort(key=lambda i: i.confidence, reverse=True)
    return {"insights": insights[:limit], "total": len(insights)}


@app.get("/learning/insights/{insight_id}")
async def get_insight(insight_id: str):
    """Get a specific insight."""
    insight = _insights.get(insight_id)
    if not insight:
        raise HTTPException(status_code=404, detail="Insight not found")
    return insight


@app.delete("/learning/insights/{insight_id}")
async def delete_insight(insight_id: str):
    """Delete an insight."""
    if insight_id not in _insights:
        raise HTTPException(status_code=404, detail="Insight not found")
    del _insights[insight_id]
    return {"message": "Insight deleted"}


@app.post("/learning/routing/record")
async def record_routing(agent_name: str, success: bool, latency_ms: float):
    """Record an agent routing metric."""
    record_routing_metric(agent_name, success, latency_ms)
    return {"recorded": True}


@app.get("/learning/routing/metrics")
async def get_routing_metrics():
    """Get agent routing performance metrics."""
    return {"metrics": list(_routing_metrics.values())}


@app.get("/learning/stats")
async def get_stats():
    """Get overall learning statistics."""
    return LearningStats(
        total_insights=len(_insights),
        applied_insights=sum(1 for i in _insights.values() if i.applied),
        patterns_detected=sum(1 for i in _insights.values() if i.insight_type == InsightType.pattern),
        routing_optimizations=sum(1 for i in _insights.values() if i.insight_type == InsightType.routing_optimization),
        analysis_runs=_analysis_count,
        last_analysis=_last_analysis,
    )
