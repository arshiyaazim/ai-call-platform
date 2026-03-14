# ============================================================
# Tests for Fazle LLM Gateway — Caching, Routing, Rate Limiting
#
# Run:  pytest tests/test_llm_gateway.py -v
# ============================================================
import pytest
import httpx
import sys
import os
import json

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "fazle-system", "llm-gateway"))


# ── Cache key determinism ───────────────────────────────────

def test_cache_key_deterministic():
    """Same inputs must produce the same cache key."""
    from main import _cache_key
    messages = [{"role": "user", "content": "hello"}]
    k1 = _cache_key(messages, "gpt-4o", "json")
    k2 = _cache_key(messages, "gpt-4o", "json")
    assert k1 == k2
    assert k1.startswith("llm_cache:")


def test_cache_key_varies_by_model():
    """Different models must produce different cache keys."""
    from main import _cache_key
    messages = [{"role": "user", "content": "hello"}]
    k1 = _cache_key(messages, "gpt-4o", "json")
    k2 = _cache_key(messages, "llama3.1", "json")
    assert k1 != k2


def test_cache_key_varies_by_format():
    """Different response_format must produce different cache keys."""
    from main import _cache_key
    messages = [{"role": "user", "content": "hello"}]
    k1 = _cache_key(messages, "gpt-4o", "json")
    k2 = _cache_key(messages, "gpt-4o", None)
    assert k1 != k2


# ── Token estimation ───────────────────────────────────────

def test_estimate_tokens_basic():
    """Token estimator should approximate 4 chars per token."""
    from main import _estimate_tokens
    messages = [{"role": "user", "content": "a" * 400}]
    est = _estimate_tokens(messages)
    assert est == 100


def test_estimate_tokens_empty():
    """Empty messages should estimate to 0 tokens."""
    from main import _estimate_tokens
    messages = [{"role": "user", "content": ""}]
    est = _estimate_tokens(messages)
    assert est == 0


def test_estimate_tokens_multiple_messages():
    """Token estimation should sum across all messages."""
    from main import _estimate_tokens
    messages = [
        {"role": "system", "content": "a" * 200},
        {"role": "user", "content": "b" * 200},
    ]
    est = _estimate_tokens(messages)
    assert est == 100


# ── Request model validation ───────────────────────────────

def test_generate_request_defaults():
    """GenerateRequest should have sensible defaults."""
    from main import GenerateRequest
    req = GenerateRequest(messages=[{"role": "user", "content": "hi"}])
    assert req.temperature == 0.7
    assert req.stream is False
    assert req.cache is True
    assert req.caller == "unknown"
    assert req.provider is None
    assert req.model is None


def test_generate_request_temperature_validation():
    """Temperature must be between 0 and 2."""
    from main import GenerateRequest
    with pytest.raises(Exception):
        GenerateRequest(messages=[{"role": "user", "content": "hi"}], temperature=3.0)


def test_embedding_request_defaults():
    """EmbeddingRequest should default to text-embedding-3-small."""
    from main import EmbeddingRequest
    req = EmbeddingRequest(text="test")
    assert req.model == "text-embedding-3-small"


# ── Provider call structure ─────────────────────────────────

@pytest.mark.asyncio
async def test_call_ollama_builds_correct_payload(monkeypatch):
    """_call_ollama should build the correct request payload."""
    captured = {}

    async def mock_post(self, url, json=None, **kwargs):
        captured["url"] = url
        captured["json"] = json
        resp = httpx.Response(
            200,
            json={"message": {"content": '{"reply": "hi"}'}, "model": "llama3.1", "prompt_eval_count": 10, "eval_count": 5},
        )
        resp._request = httpx.Request("POST", url)
        return resp

    monkeypatch.setattr(httpx.AsyncClient, "post", mock_post)

    from main import _call_ollama
    result = await _call_ollama(
        [{"role": "user", "content": "hello"}],
        model="llama3.1",
        temperature=0.7,
        response_format="json",
    )

    assert "ollama" in captured["url"]
    assert captured["json"]["model"] == "llama3.1"
    assert captured["json"]["stream"] is False
    assert captured["json"]["format"] == "json"
    assert result["content"] == '{"reply": "hi"}'
    assert result["provider"] == "ollama"
    assert result["usage"]["total_tokens"] == 15


@pytest.mark.asyncio
async def test_call_openai_builds_correct_payload(monkeypatch):
    """_call_openai should build the correct request payload."""
    captured = {}

    async def mock_post(self, url, headers=None, json=None, **kwargs):
        captured["url"] = url
        captured["json"] = json
        captured["headers"] = headers
        resp = httpx.Response(
            200,
            json={
                "choices": [{"message": {"content": '{"reply": "hi"}'}}],
                "model": "gpt-4o",
                "usage": {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15},
            },
        )
        resp._request = httpx.Request("POST", url)
        return resp

    monkeypatch.setattr(httpx.AsyncClient, "post", mock_post)

    from main import _call_openai
    result = await _call_openai(
        [{"role": "user", "content": "hello"}],
        model="gpt-4o",
        temperature=0.7,
        response_format="json",
        api_key="sk-test",
    )

    assert "openai.com" in captured["url"]
    assert captured["json"]["model"] == "gpt-4o"
    assert captured["json"]["response_format"] == {"type": "json_object"}
    assert result["content"] == '{"reply": "hi"}'
    assert result["provider"] == "openai"
    assert result["usage"]["total_tokens"] == 15
