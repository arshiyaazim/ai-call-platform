# ============================================================
# Fazle Knowledge Graph Engine — Entity & Relationship Store
# Maintains a graph of people, projects, companies, tasks,
# and conversations with relationship tracking
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
logger = logging.getLogger("fazle-knowledge-graph")


class Settings(BaseSettings):
    memory_url: str = "http://fazle-memory:8300"
    llm_gateway_url: str = "http://fazle-llm-gateway:8800"
    redis_url: str = "redis://redis:6379/8"
    max_nodes: int = 10000
    max_relationships: int = 50000

    class Config:
        env_prefix = "KNOWLEDGE_GRAPH_"


settings = Settings()

app = FastAPI(title="Fazle Knowledge Graph Engine", version="1.0.0")
Instrumentator().instrument(app).expose(app, endpoint="/metrics")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://fazle.iamazim.com", "https://iamazim.com"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Models ───────────────────────────────────────────────────

class NodeType(str, Enum):
    person = "person"
    project = "project"
    company = "company"
    conversation = "conversation"
    task = "task"
    topic = "topic"
    location = "location"
    concept = "concept"


class RelationshipType(str, Enum):
    works_with = "works_with"
    belongs_to = "belongs_to"
    discussed_in = "discussed_in"
    related_to = "related_to"
    created_by = "created_by"
    depends_on = "depends_on"
    mentions = "mentions"
    located_in = "located_in"
    manages = "manages"
    friend_of = "friend_of"


class GraphNode(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str
    node_type: NodeType
    properties: dict[str, Any] = Field(default_factory=dict)
    created_at: str = Field(default_factory=lambda: datetime.utcnow().isoformat())
    updated_at: Optional[str] = None
    mention_count: int = 1


class GraphRelationship(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4())[:12])
    source_id: str
    target_id: str
    relationship_type: RelationshipType
    properties: dict[str, Any] = Field(default_factory=dict)
    weight: float = 1.0
    created_at: str = Field(default_factory=lambda: datetime.utcnow().isoformat())


class AddNodeRequest(BaseModel):
    name: str
    node_type: NodeType
    properties: dict[str, Any] = Field(default_factory=dict)


class AddRelationshipRequest(BaseModel):
    source_id: str
    target_id: str
    relationship_type: RelationshipType
    properties: dict[str, Any] = Field(default_factory=dict)
    weight: float = 1.0


class UpdateFromConversationRequest(BaseModel):
    conversation_id: str
    text: str
    user_id: Optional[str] = None


class GraphQueryRequest(BaseModel):
    query: str
    node_types: Optional[list[NodeType]] = None
    max_depth: int = 2
    limit: int = 20


# ── In-memory graph store ───────────────────────────────────

_nodes: dict[str, GraphNode] = {}
_relationships: list[GraphRelationship] = []
# Index: node_id → list of relationship indices
_adjacency: dict[str, list[int]] = defaultdict(list)
# Index: name → node_id (lowercase)
_name_index: dict[str, str] = {}


# ── Graph Operations ────────────────────────────────────────

def add_node(name: str, node_type: NodeType, properties: dict = None) -> GraphNode:
    """Add a node, or increment mention_count if exists."""
    key = name.lower().strip()
    if key in _name_index:
        existing = _nodes[_name_index[key]]
        existing.mention_count += 1
        existing.updated_at = datetime.utcnow().isoformat()
        if properties:
            existing.properties.update(properties)
        return existing

    if len(_nodes) >= settings.max_nodes:
        raise HTTPException(status_code=507, detail="Maximum node limit reached")

    node = GraphNode(name=name, node_type=node_type, properties=properties or {})
    _nodes[node.id] = node
    _name_index[key] = node.id
    return node


def add_relationship(source_id: str, target_id: str, rel_type: RelationshipType,
                     properties: dict = None, weight: float = 1.0) -> GraphRelationship:
    """Add a relationship between two nodes."""
    if source_id not in _nodes:
        raise HTTPException(status_code=404, detail=f"Source node {source_id} not found")
    if target_id not in _nodes:
        raise HTTPException(status_code=404, detail=f"Target node {target_id} not found")

    # Check for duplicate
    for idx in _adjacency[source_id]:
        rel = _relationships[idx]
        if rel.target_id == target_id and rel.relationship_type == rel_type:
            rel.weight += 0.1  # Strengthen existing relationship
            return rel

    if len(_relationships) >= settings.max_relationships:
        raise HTTPException(status_code=507, detail="Maximum relationship limit reached")

    rel = GraphRelationship(
        source_id=source_id,
        target_id=target_id,
        relationship_type=rel_type,
        properties=properties or {},
        weight=weight,
    )
    idx = len(_relationships)
    _relationships.append(rel)
    _adjacency[source_id].append(idx)
    _adjacency[target_id].append(idx)
    return rel


def get_neighbors(node_id: str, max_depth: int = 1) -> dict:
    """BFS to find connected nodes up to max_depth."""
    if node_id not in _nodes:
        return {"nodes": [], "relationships": []}

    visited = {node_id}
    result_nodes = [_nodes[node_id]]
    result_rels = []
    frontier = [node_id]

    for _ in range(max_depth):
        next_frontier = []
        for nid in frontier:
            for idx in _adjacency.get(nid, []):
                rel = _relationships[idx]
                result_rels.append(rel)
                neighbor_id = rel.target_id if rel.source_id == nid else rel.source_id
                if neighbor_id not in visited:
                    visited.add(neighbor_id)
                    if neighbor_id in _nodes:
                        result_nodes.append(_nodes[neighbor_id])
                        next_frontier.append(neighbor_id)
        frontier = next_frontier

    return {"nodes": result_nodes, "relationships": result_rels}


def search_nodes(query: str, node_types: Optional[list[NodeType]] = None, limit: int = 20) -> list[GraphNode]:
    """Simple text search across node names and properties."""
    query_lower = query.lower()
    results = []
    for node in _nodes.values():
        if node_types and node.node_type not in node_types:
            continue
        name_match = query_lower in node.name.lower()
        prop_match = any(query_lower in str(v).lower() for v in node.properties.values())
        if name_match or prop_match:
            results.append(node)
    results.sort(key=lambda n: n.mention_count, reverse=True)
    return results[:limit]


# ── LLM-powered entity extraction ───────────────────────────

async def extract_entities(text: str) -> list[dict]:
    """Use LLM to extract entities and relationships from text."""
    async with httpx.AsyncClient(timeout=20.0) as client:
        try:
            resp = await client.post(
                f"{settings.llm_gateway_url}/llm/generate",
                json={
                    "prompt": f"""Extract entities and relationships from this text.

Text: {text[:3000]}

Return a JSON object with:
- "entities": array of {{"name": "...", "type": "person|project|company|topic|location|concept", "properties": {{}}}}
- "relationships": array of {{"source": "entity_name", "target": "entity_name", "type": "works_with|belongs_to|related_to|mentions|manages|friend_of"}}

Return ONLY valid JSON, no markdown.""",
                    "system_prompt": "You are an entity extraction engine. Extract named entities and relationships accurately.",
                    "temperature": 0.1,
                    "max_tokens": 1000,
                },
            )
            resp.raise_for_status()
            data = resp.json()
            raw = data.get("response", data.get("text", "{}"))
            raw = raw.strip()
            if raw.startswith("```"):
                raw = raw.split("```")[1]
                if raw.startswith("json"):
                    raw = raw[4:]
            return json.loads(raw) if raw else {}
        except Exception as e:
            logger.error(f"Entity extraction failed: {e}")
            return {}


# ── Endpoints ────────────────────────────────────────────────

@app.get("/health")
async def health():
    return {
        "status": "healthy",
        "service": "knowledge-graph",
        "nodes": len(_nodes),
        "relationships": len(_relationships),
    }


@app.post("/graph/node")
async def create_node(req: AddNodeRequest):
    """Add a node to the graph."""
    node = add_node(req.name, req.node_type, req.properties)
    return node


@app.get("/graph/node/{node_id}")
async def get_node(node_id: str):
    """Get a specific node."""
    node = _nodes.get(node_id)
    if not node:
        raise HTTPException(status_code=404, detail="Node not found")
    return node


@app.delete("/graph/node/{node_id}")
async def delete_node(node_id: str):
    """Remove a node and its relationships."""
    if node_id not in _nodes:
        raise HTTPException(status_code=404, detail="Node not found")
    node = _nodes.pop(node_id)
    _name_index.pop(node.name.lower().strip(), None)
    # Remove relationships
    _adjacency.pop(node_id, None)
    return {"message": f"Node '{node.name}' deleted"}


@app.post("/graph/relationship")
async def create_relationship(req: AddRelationshipRequest):
    """Add a relationship between two nodes."""
    rel = add_relationship(req.source_id, req.target_id, req.relationship_type, req.properties, req.weight)
    return rel


@app.post("/graph/query")
async def query_graph(req: GraphQueryRequest):
    """Search the graph with text query."""
    nodes = search_nodes(req.query, req.node_types, req.limit)
    # Expand results with relationships
    all_rels = []
    node_ids = {n.id for n in nodes}
    for node in nodes:
        for idx in _adjacency.get(node.id, []):
            rel = _relationships[idx]
            if rel not in all_rels:
                all_rels.append(rel)
                # Include connected nodes
                other_id = rel.target_id if rel.source_id == node.id else rel.source_id
                if other_id not in node_ids and other_id in _nodes:
                    nodes.append(_nodes[other_id])
                    node_ids.add(other_id)

    return {"nodes": nodes[:req.limit], "relationships": all_rels, "total_nodes": len(nodes)}


@app.get("/graph/context/{node_id}")
async def get_context(node_id: str, depth: int = Query(default=2, le=5)):
    """Get a node with its connected subgraph (for contextual understanding)."""
    result = get_neighbors(node_id, max_depth=depth)
    return result


@app.post("/graph/update")
async def update_from_conversation(req: UpdateFromConversationRequest):
    """Extract entities from conversation text and update graph."""
    extracted = await extract_entities(req.text)

    added_nodes = []
    added_rels = []

    # Add conversation node
    conv_node = add_node(
        f"conversation_{req.conversation_id[:8]}",
        NodeType.conversation,
        {"conversation_id": req.conversation_id, "user_id": req.user_id},
    )
    added_nodes.append(conv_node)

    # Add extracted entities
    entities = extracted.get("entities", [])
    entity_map = {}
    for ent in entities:
        name = ent.get("name", "")
        if not name:
            continue
        try:
            node_type = NodeType(ent.get("type", "concept"))
        except ValueError:
            node_type = NodeType.concept
        node = add_node(name, node_type, ent.get("properties", {}))
        added_nodes.append(node)
        entity_map[name.lower()] = node.id

        # Link to conversation
        rel = add_relationship(node.id, conv_node.id, RelationshipType.discussed_in)
        added_rels.append(rel)

    # Add extracted relationships
    relationships = extracted.get("relationships", [])
    for r in relationships:
        src_name = r.get("source", "").lower()
        tgt_name = r.get("target", "").lower()
        if src_name in entity_map and tgt_name in entity_map:
            try:
                rel_type = RelationshipType(r.get("type", "related_to"))
            except ValueError:
                rel_type = RelationshipType.related_to
            rel = add_relationship(entity_map[src_name], entity_map[tgt_name], rel_type)
            added_rels.append(rel)

    return {
        "added_nodes": len(added_nodes),
        "added_relationships": len(added_rels),
        "total_nodes": len(_nodes),
        "total_relationships": len(_relationships),
    }


@app.get("/graph/stats")
async def graph_stats():
    """Get graph statistics."""
    type_counts = defaultdict(int)
    for node in _nodes.values():
        type_counts[node.node_type] += 1

    rel_type_counts = defaultdict(int)
    for rel in _relationships:
        rel_type_counts[rel.relationship_type] += 1

    return {
        "total_nodes": len(_nodes),
        "total_relationships": len(_relationships),
        "node_types": dict(type_counts),
        "relationship_types": dict(rel_type_counts),
        "top_entities": sorted(
            [{"name": n.name, "type": n.node_type, "mentions": n.mention_count} for n in _nodes.values()],
            key=lambda x: x["mentions"],
            reverse=True,
        )[:10],
    }


@app.get("/graph/nodes")
async def list_nodes(
    node_type: Optional[NodeType] = None,
    limit: int = Query(default=50, le=200),
    offset: int = 0,
):
    """List all nodes with optional type filter."""
    nodes = list(_nodes.values())
    if node_type:
        nodes = [n for n in nodes if n.node_type == node_type]
    nodes.sort(key=lambda n: n.mention_count, reverse=True)
    return {"nodes": nodes[offset:offset + limit], "total": len(nodes)}
