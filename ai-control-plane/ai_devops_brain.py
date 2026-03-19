#!/usr/bin/env python3
"""
AI DevOps Brain — Level-5 AI reasoning engine.
Sends system diagnostics to Ollama and returns structured repair recommendations.
"""

import json
import logging
import requests
from tenacity import retry, stop_after_attempt, wait_exponential

log = logging.getLogger("control-plane.brain")

OLLAMA_URL = None
OLLAMA_MODEL = None


def init(ollama_url: str, model: str):
    global OLLAMA_URL, OLLAMA_MODEL
    OLLAMA_URL = ollama_url
    OLLAMA_MODEL = model


SYSTEM_PROMPT = (
    "You are a DevOps AI engineer. Analyze the following system snapshot and propose "
    "the most probable cause of any issues and recommended repair steps.\n\n"
    "RULES:\n"
    "- Only recommend actions from this whitelist: restart_container, rebuild_service, "
    "redeploy_service, scale_workers, clean_docker\n"
    "- Never recommend deleting volumes\n"
    "- Never recommend stopping postgres, redis, qdrant, or minio unless restarting them\n"
    "- Be conservative — only recommend repairs when there is clear evidence of a problem\n"
    "- If everything looks healthy, respond with status ok and empty actions\n\n"
    "Respond ONLY with valid JSON in this exact format:\n"
    '{"status": "ok|warning|critical", "root_cause": "description or null", '
    '"recommended_actions": [{"action": "action_name", "target": "container_name", '
    '"reason": "why"}]}\n\n'
)


def _parse_ai_response(text: str) -> dict:
    """Extract JSON from Ollama response, handling markdown fences."""
    text = text.strip()
    # Strip markdown code fences
    if text.startswith("```"):
        lines = text.split("\n")
        lines = [l for l in lines if not l.strip().startswith("```")]
        text = "\n".join(lines).strip()

    # Find JSON object boundaries
    start = text.find("{")
    end = text.rfind("}") + 1
    if start == -1 or end == 0:
        return {"status": "ok", "root_cause": None, "recommended_actions": []}

    try:
        return json.loads(text[start:end])
    except json.JSONDecodeError:
        log.warning("Failed to parse AI response as JSON: %s", text[:300])
        return {"status": "ok", "root_cause": None, "recommended_actions": []}


def analyze(snapshot: dict) -> dict:
    """Send system snapshot to Ollama and return structured recommendation."""
    # Compact JSON to reduce token count
    prompt = SYSTEM_PROMPT + "SYSTEM SNAPSHOT:\n" + json.dumps(snapshot, separators=(',', ':'), default=str)

    try:
        resp = requests.post(
            f"{OLLAMA_URL}/api/generate",
            json={"model": OLLAMA_MODEL, "prompt": prompt, "stream": False,
                  "options": {"num_predict": 100, "num_ctx": 1024}},
            timeout=90,
        )
        if resp.status_code != 200:
            log.error("Ollama returned HTTP %d", resp.status_code)
            return {"status": "ok", "root_cause": None, "recommended_actions": []}

        response_text = resp.json().get("response", "")
        log.info("AI Brain raw response: %s", response_text[:500])
        return _parse_ai_response(response_text)

    except requests.exceptions.ConnectionError:
        log.warning("Cannot reach Ollama at %s", OLLAMA_URL)
        return {"status": "ok", "root_cause": None, "recommended_actions": []}
    except requests.exceptions.Timeout:
        log.warning("Ollama request timed out")
        return {"status": "ok", "root_cause": None, "recommended_actions": []}
