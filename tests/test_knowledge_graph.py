# ============================================================
# Tests for Fazle Phase-5 Knowledge Graph Engine
#
# Run:  pytest tests/test_knowledge_graph.py -v
# ============================================================
import pytest
from conftest import knowledge_graph as _m


# ── Model validation ───────────────────────────────────────

def test_add_node_request():
    """AddNodeRequest should accept name and node_type."""
    req = _m.AddNodeRequest(name="John", node_type=_m.NodeType.person)
    assert req.name == "John"
    assert req.node_type == _m.NodeType.person
    assert req.properties == {}


def test_add_node_request_with_properties():
    """AddNodeRequest should accept optional properties."""
    req = _m.AddNodeRequest(name="Project X", node_type=_m.NodeType.project, properties={"status": "active"})
    assert req.properties == {"status": "active"}


def test_add_relationship_request():
    """AddRelationshipRequest should accept source_id, target_id, and type."""
    req = _m.AddRelationshipRequest(source_id="a", target_id="b", relationship_type=_m.RelationshipType.works_with)
    assert req.source_id == "a"
    assert req.target_id == "b"
    assert req.relationship_type == _m.RelationshipType.works_with


def test_graph_query_request():
    """GraphQueryRequest should accept query and optional filters."""
    req = _m.GraphQueryRequest(query="AI research")
    assert req.query == "AI research"
    assert req.node_types is None
    assert req.max_depth == 2


# ── Graph store operations ──────────────────────────────────

def test_graph_store_is_dict():
    """In-memory graph stores should be accessible."""
    assert isinstance(_m._nodes, dict)
    assert isinstance(_m._relationships, list)


# ── Valid types ─────────────────────────────────────────────

def test_valid_node_types():
    """NodeType enum should contain expected types."""
    assert _m.NodeType.person.value == "person"
    assert _m.NodeType.project.value == "project"
    assert _m.NodeType.concept.value == "concept"
    assert _m.NodeType.topic.value == "topic"


def test_valid_relationship_types():
    """RelationshipType enum should contain expected types."""
    assert _m.RelationshipType.works_with.value == "works_with"
    assert _m.RelationshipType.related_to.value == "related_to"
    assert _m.RelationshipType.depends_on.value == "depends_on"


# ── Health & node endpoints ─────────────────────────────────

@pytest.mark.anyio
async def test_health_endpoint():
    """Health endpoint should return status healthy."""
    from httpx import AsyncClient, ASGITransport
    transport = ASGITransport(app=_m.app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "healthy"
        assert data["service"] == "knowledge-graph"


@pytest.mark.anyio
async def test_create_and_list_nodes():
    """POST /graph/node then GET /graph/nodes should return the node."""
    from httpx import AsyncClient, ASGITransport
    _m._nodes.clear()
    _m._relationships.clear()
    _m._adjacency.clear()
    _m._name_index.clear()
    transport = ASGITransport(app=_m.app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        create_resp = await client.post("/graph/node", json={"name": "TestNode", "node_type": "concept"})
        assert create_resp.status_code == 200
        node_data = create_resp.json()
        assert node_data["name"] == "TestNode"

        list_resp = await client.get("/graph/nodes")
        assert list_resp.status_code == 200
        nodes = list_resp.json()["nodes"]
        assert len(nodes) == 1
        assert nodes[0]["name"] == "TestNode"


@pytest.mark.anyio
async def test_graph_stats():
    """GET /graph/stats should return node and relationship counts."""
    from httpx import AsyncClient, ASGITransport
    _m._nodes.clear()
    _m._relationships.clear()
    _m._adjacency.clear()
    _m._name_index.clear()
    transport = ASGITransport(app=_m.app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        stats_resp = await client.get("/graph/stats")
        assert stats_resp.status_code == 200
        data = stats_resp.json()
        assert data["total_nodes"] == 0
        assert data["total_relationships"] == 0
