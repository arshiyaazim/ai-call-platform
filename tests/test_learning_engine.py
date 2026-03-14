# ============================================================
# Tests for Fazle Learning Engine — Knowledge extraction models,
# correction recording, and relationship graph logic
#
# Run:  pytest tests/test_learning_engine.py -v
# ============================================================
import pytest
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "fazle-system", "learning-engine"))


# ── Model validation ───────────────────────────────────────

def test_correction_request_defaults():
    """CorrectionRequest should default user_feedback to empty string."""
    from main import CorrectionRequest
    req = CorrectionRequest(
        original_response="Hello",
        corrected_response="Hi there",
    )
    assert req.user_feedback == ""
    assert req.context == {}


def test_person_request_defaults():
    """PersonRequest should default relationship to 'unknown'."""
    from main import PersonRequest
    req = PersonRequest(person_name="Rahim")
    assert req.relationship == "unknown"
    assert req.attributes == {}


def test_learn_request_defaults():
    """LearnRequest should default user to Azim."""
    from main import LearnRequest
    req = LearnRequest(transcript="some conversation")
    assert req.user == "Azim"
    assert req.conversation_id is None


def test_learn_request_requires_transcript():
    """LearnRequest must have a transcript."""
    from main import LearnRequest
    with pytest.raises(Exception):
        LearnRequest()


# ── Learning prompt structure ──────────────────────────────

def test_learning_prompt_contains_extraction_types():
    """The LEARNING_PROMPT should mention knowledge, people, corrections, personality."""
    from main import LEARNING_PROMPT
    assert "knowledge" in LEARNING_PROMPT.lower()
    assert "people" in LEARNING_PROMPT.lower()
    assert "corrections" in LEARNING_PROMPT.lower()
    assert "personality" in LEARNING_PROMPT.lower()


def test_learning_prompt_requests_json():
    """The LEARNING_PROMPT should request JSON output."""
    from main import LEARNING_PROMPT
    assert "json" in LEARNING_PROMPT.lower()
