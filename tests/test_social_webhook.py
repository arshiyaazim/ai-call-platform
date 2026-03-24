# ============================================================
# Tests for Fazle Social Engine — Webhook Security
#
# Run inside Docker:  docker exec fazle-social-engine pytest /app/tests/ -v -k social
# Run locally (needs deps):  pytest tests/test_social_webhook.py -v
# ============================================================
import hashlib
import hmac
import json
import sys
import os

import pytest

# Skip the whole module gracefully when FastAPI is not installed
# (running outside Docker). Tests still run in CI / inside the container.
fastapi = pytest.importorskip("fastapi", reason="FastAPI not installed — run tests inside Docker")

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "fazle-system", "social-engine"))


# ── _verify_meta_signature ─────────────────────────────────

def test_valid_signature_accepted():
    """A correctly computed X-Hub-Signature-256 must be accepted."""
    from main import _verify_meta_signature

    secret = "test_app_secret"
    body = b'{"object":"whatsapp_business_account"}'
    digest = "sha256=" + hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
    assert _verify_meta_signature(body, secret, digest) is True


def test_invalid_signature_rejected():
    """A tampered or wrong signature must be rejected."""
    from main import _verify_meta_signature

    secret = "test_app_secret"
    body = b'{"object":"whatsapp_business_account"}'
    assert _verify_meta_signature(body, secret, "sha256=deadbeef") is False


def test_missing_secret_rejects():
    """If no app secret is configured, verification must fail closed."""
    from main import _verify_meta_signature

    body = b'{"object":"whatsapp_business_account"}'
    digest = "sha256=" + hmac.new(b"some_secret", body, hashlib.sha256).hexdigest()
    assert _verify_meta_signature(body, "", digest) is False


def test_missing_header_rejects():
    """A missing X-Hub-Signature-256 header must be rejected."""
    from main import _verify_meta_signature

    assert _verify_meta_signature(b"{}", "secret", "") is False


def test_malformed_header_rejects():
    """A header without 'sha256=' prefix must be rejected."""
    from main import _verify_meta_signature

    assert _verify_meta_signature(b"{}", "secret", "md5=abc123") is False


# ── Verify-token env fallback ──────────────────────────────

def test_verify_token_env_fallback(monkeypatch):
    """Settings.verify_token must read from SOCIAL_VERIFY_TOKEN env var."""
    monkeypatch.setenv("SOCIAL_VERIFY_TOKEN", "fallback-token-xyz")
    # Re-import to pick up the new env
    import importlib
    import main as social_main
    importlib.reload(social_main)
    assert social_main.settings.verify_token == "fallback-token-xyz"


def test_verify_token_default_empty(monkeypatch):
    """Without SOCIAL_VERIFY_TOKEN set, verify_token must default to empty string."""
    monkeypatch.delenv("SOCIAL_VERIFY_TOKEN", raising=False)
    import importlib
    import main as social_main
    importlib.reload(social_main)
    assert social_main.settings.verify_token == ""


# ── Curl validation reference ──────────────────────────────
# These are not automated — run them against a live VPS to validate end-to-end.
#
# 1. Webhook GET verification (WhatsApp):
#    curl -sS "https://fazle.iamazim.com/api/fazle/social/whatsapp/webhook\
#      ?hub.mode=subscribe&hub.verify_token=<SOCIAL_VERIFY_TOKEN>&hub.challenge=1234567890"
#    Expected: 1234567890
#
# 2. Webhook POST with valid signature:
#    BODY='{"object":"whatsapp_business_account","entry":[]}'
#    SECRET=<SOCIAL_META_APP_SECRET>
#    SIG="sha256=$(printf '%s' "$BODY" | openssl dgst -sha256 -hmac "$SECRET" | awk '{print $2}')"
#    curl -sS -X POST "https://fazle.iamazim.com/api/fazle/social/whatsapp/webhook" \
#      -H "Content-Type: application/json" \
#      -H "X-Hub-Signature-256: $SIG" \
#      -d "$BODY"
#    Expected: {"status":"ok"}
#
# 3. Webhook POST without signature (must be rejected):
#    curl -sS -X POST "https://fazle.iamazim.com/api/fazle/social/whatsapp/webhook" \
#      -H "Content-Type: application/json" \
#      -d '{"object":"whatsapp_business_account","entry":[]}'
#    Expected: HTTP 403 {"detail":"Invalid webhook signature"}
#
# 4. Proxy forwards X-Hub-Signature-256 (confirmed by Fix 4 in social_routes.py):
#    The proxy reads raw request bytes and passes the original header unmodified
#    to the social engine, so the HMAC computed by Meta over the original body
#    will match the HMAC recomputed by the social engine.
