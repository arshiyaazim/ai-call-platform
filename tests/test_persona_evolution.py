# ============================================================
# Tests for Feature #1 — Memory Reflection + Persona Evolution
# Verifies persona_engine async builder, persona overrides
# fallback behavior, and reflection endpoint data flow.
#
# Run:  pytest tests/test_persona_evolution.py -v
# ============================================================
import pytest
import httpx
import json
import sys
import os

# Allow importing from brain and learning-engine directories
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "fazle-system", "brain"))

from persona_engine import (
    build_system_prompt,
    build_system_prompt_async,
    _fetch_persona_overrides,
    BASE_IDENTITY,
    RELATIONSHIP_PROMPTS,
    CAPABILITIES_CONTEXT,
)


# ── Static prompt tests ────────────────────────────────────

def test_build_system_prompt_contains_identity():
    prompt = build_system_prompt("Azim", "self")
    assert "You are Azim" in prompt
    assert "not an AI" in prompt


def test_build_system_prompt_wife_has_privacy_rule():
    prompt = build_system_prompt("Sarah", "wife")
    assert "Privacy rule" in prompt
    assert "Sarah" in prompt
    assert "loving husband" in prompt


def test_build_system_prompt_self_no_privacy_rule():
    prompt = build_system_prompt("Azim", "self")
    assert "Privacy rule" not in prompt


def test_build_system_prompt_unknown_relationship_defaults_to_self():
    prompt = build_system_prompt("Unknown", "stranger")
    assert "self-assistant" in prompt


@pytest.mark.parametrize("relationship", ["wife", "daughter", "son", "parent", "sibling"])
def test_all_relationships_have_tone(relationship):
    prompt = build_system_prompt("Test", relationship)
    assert RELATIONSHIP_PROMPTS[relationship]["tone"] in prompt


# ── Async prompt builder — overrides integration ───────────

@pytest.mark.asyncio
async def test_async_prompt_falls_back_gracefully(monkeypatch):
    """When learning engine is unreachable, async builder returns base prompt."""

    async def mock_get(self, *args, **kwargs):
        raise httpx.ConnectError("Connection refused")

    monkeypatch.setattr(httpx.AsyncClient, "get", mock_get)

    prompt = await build_system_prompt_async(
        "Sarah", "wife", learning_engine_url="http://localhost:99999"
    )
    # Should still contain base identity
    assert "You are Azim" in prompt
    # Should NOT contain evolution section (no overrides available)
    assert "Persona Evolution" not in prompt


@pytest.mark.asyncio
async def test_async_prompt_applies_tone_override(monkeypatch):
    """When learning engine returns a tone override, it appears in prompt."""
    mock_response = httpx.Response(
        200,
        json={"overrides": {"tone": "warmer and more playful"}, "source": "cache"},
    )

    async def mock_get(self, url, **kwargs):
        return mock_response

    monkeypatch.setattr(httpx.AsyncClient, "get", mock_get)

    prompt = await build_system_prompt_async(
        "Sarah", "wife", learning_engine_url="http://fake:8900"
    )
    assert "Persona Evolution" in prompt
    assert "Adjusted tone: warmer and more playful" in prompt


@pytest.mark.asyncio
async def test_async_prompt_applies_high_initiative(monkeypatch):
    mock_response = httpx.Response(
        200,
        json={"overrides": {"initiative_level": "0.9"}, "source": "cache"},
    )

    async def mock_get(self, url, **kwargs):
        return mock_response

    monkeypatch.setattr(httpx.AsyncClient, "get", mock_get)

    prompt = await build_system_prompt_async(
        "Azim", "self", learning_engine_url="http://fake:8900"
    )
    assert "proactive" in prompt


@pytest.mark.asyncio
async def test_async_prompt_applies_low_humor(monkeypatch):
    mock_response = httpx.Response(
        200,
        json={"overrides": {"humor": "0.1"}, "source": "cache"},
    )

    async def mock_get(self, url, **kwargs):
        return mock_response

    monkeypatch.setattr(httpx.AsyncClient, "get", mock_get)

    prompt = await build_system_prompt_async(
        "Test", "daughter", learning_engine_url="http://fake:8900"
    )
    assert "Minimal jokes" in prompt


@pytest.mark.asyncio
async def test_async_prompt_applies_high_affection(monkeypatch):
    mock_response = httpx.Response(
        200,
        json={"overrides": {"affection": "0.85"}, "source": "cache"},
    )

    async def mock_get(self, url, **kwargs):
        return mock_response

    monkeypatch.setattr(httpx.AsyncClient, "get", mock_get)

    prompt = await build_system_prompt_async(
        "Sarah", "wife", learning_engine_url="http://fake:8900"
    )
    assert "warm, affectionate" in prompt


@pytest.mark.asyncio
async def test_async_prompt_applies_prompt_override(monkeypatch):
    custom_text = "Always ask about her garden project."
    mock_response = httpx.Response(
        200,
        json={"overrides": {"prompt_override": custom_text}, "source": "cache"},
    )

    async def mock_get(self, url, **kwargs):
        return mock_response

    monkeypatch.setattr(httpx.AsyncClient, "get", mock_get)

    prompt = await build_system_prompt_async(
        "Sarah", "wife", learning_engine_url="http://fake:8900"
    )
    assert custom_text in prompt


@pytest.mark.asyncio
async def test_async_prompt_multiple_overrides(monkeypatch):
    mock_response = httpx.Response(
        200,
        json={
            "overrides": {
                "tone": "gentle and encouraging",
                "humor": "0.8",
                "affection": "0.9",
                "verbosity": "0.2",
            },
            "source": "cache",
        },
    )

    async def mock_get(self, url, **kwargs):
        return mock_response

    monkeypatch.setattr(httpx.AsyncClient, "get", mock_get)

    prompt = await build_system_prompt_async(
        "Test", "son", learning_engine_url="http://fake:8900"
    )
    assert "gentle and encouraging" in prompt
    assert "playful" in prompt  # high humor
    assert "warm, affectionate" in prompt  # high affection
    assert "brief" in prompt  # low verbosity


@pytest.mark.asyncio
async def test_async_prompt_mid_range_values_no_adjustment(monkeypatch):
    """Mid-range values (0.3-0.7) should not add specific adjustments."""
    mock_response = httpx.Response(
        200,
        json={"overrides": {"humor": "0.5", "affection": "0.5"}, "source": "cache"},
    )

    async def mock_get(self, url, **kwargs):
        return mock_response

    monkeypatch.setattr(httpx.AsyncClient, "get", mock_get)

    prompt = await build_system_prompt_async(
        "Azim", "self", learning_engine_url="http://fake:8900"
    )
    # Mid-range values shouldn't add adjustments → no Persona Evolution section
    assert "Persona Evolution" not in prompt


@pytest.mark.asyncio
async def test_async_prompt_memory_weight_high(monkeypatch):
    mock_response = httpx.Response(
        200,
        json={"overrides": {"memory_weight": "0.9"}, "source": "cache"},
    )

    async def mock_get(self, url, **kwargs):
        return mock_response

    monkeypatch.setattr(httpx.AsyncClient, "get", mock_get)

    prompt = await build_system_prompt_async(
        "Sarah", "wife", learning_engine_url="http://fake:8900"
    )
    assert "Frequently reference past conversations" in prompt


# ── _fetch_persona_overrides tests ─────────────────────────

@pytest.mark.asyncio
async def test_fetch_overrides_returns_empty_on_timeout(monkeypatch):
    async def mock_get(self, *args, **kwargs):
        raise httpx.ConnectTimeout("Timeout")

    monkeypatch.setattr(httpx.AsyncClient, "get", mock_get)

    result = await _fetch_persona_overrides("wife", "http://fake:8900")
    assert result == {}


@pytest.mark.asyncio
async def test_fetch_overrides_returns_empty_on_404(monkeypatch):
    async def mock_get(self, *args, **kwargs):
        return httpx.Response(404, json={"detail": "not found"})

    monkeypatch.setattr(httpx.AsyncClient, "get", mock_get)

    result = await _fetch_persona_overrides("unknown_person", "http://fake:8900")
    assert result == {}


@pytest.mark.asyncio
async def test_fetch_overrides_returns_data_on_success(monkeypatch):
    expected = {"tone": "warm", "humor": "0.8"}

    async def mock_get(self, *args, **kwargs):
        return httpx.Response(200, json={"overrides": expected, "source": "cache"})

    monkeypatch.setattr(httpx.AsyncClient, "get", mock_get)

    result = await _fetch_persona_overrides("wife", "http://fake:8900")
    assert result == expected


# ── Prompt structure integrity ─────────────────────────────

def test_base_identity_not_empty():
    assert len(BASE_IDENTITY) > 50


def test_capabilities_context_has_json_format():
    assert "JSON" in CAPABILITIES_CONTEXT


def test_all_relationships_defined():
    expected = {"self", "wife", "daughter", "son", "parent", "sibling"}
    assert set(RELATIONSHIP_PROMPTS.keys()) == expected
