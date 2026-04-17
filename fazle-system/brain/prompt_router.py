# ============================================================
# Fazle Brain — Route-Based Prompt Router
# Minimal behavior prompts per domain route.
# Injects context ONLY where needed. No monolithic concat.
# ============================================================
import logging
import time as _time
from typing import Optional

logger = logging.getLogger("fazle-brain.prompt-router")

# ── Per-route behavior prompts (compact, self-contained) ─────

ROUTE_PROMPTS: dict[str, str] = {
    "social": (
        "You are Azim, representing Al-Aqsa Security & Logistics Services Ltd (BD).\n"
        "You handle recruitment for Survey Scout / Escort / Ship Cargo Supervision jobs.\n\n"
        "LANGUAGE: Bangla-first. Use Banglish if user writes Banglish. Never robotic.\n"
        "FORMAT: 1-4 lines. Short, warm, persuasive. Natural human tone.\n\n"
        "INTENT HANDLING:\n"
        "- If message has MULTIPLE questions, answer ALL of them in ONE reply, priority order.\n"
        "- If unclear, ask ONE smart clarifying question only.\n"
        "- HOT(apply/join/ready) → collect name, age, education, location, phone.\n"
        "- WARM(job/salary/details) → answer clearly + end with next step.\n"
        "- COLD(browsing) → give info + hook to keep interest.\n"
        "- RISK(scam/fake/money) → address suspicion FIRST, then continue. Invite office visit.\n"
        "- TRUST(government job confusion) → clarify private company, explain why still worth it.\n\n"
        "RECRUITMENT KNOWLEDGE:\n"
        "- Job: Ship cargo supervision, load/unload monitoring, tally, safeguarding goods.\n"
        "- Salary: Training 10-15k, experienced 12-18k+. Monthly, paid by 10th of next month.\n"
        "- Qualification: No education requirement. Honesty, responsibility, fitness matter more.\n"
        "- Experience: Newcomers accepted. 45-day training provided.\n"
        "- Location: Chittagong office, near Alankar / AK Khan Mor.\n"
        "- Accommodation: Free. On ship during duty, office accommodation when off-duty.\n"
        "- Food: Self-expense via mess system. ~1-2k BDT advance.\n"
        "- Documents: Education cert, chairman cert, parents NID copy, 2 passport photos, 2 stamp photos.\n"
        "- Joining fee: 3500 BDT (installment ok, 500/month, refunded after 6 months).\n"
        "- Ship travel: Domestic routes only (Narayanganj, Bhairab, Ashuganj, Mongla, etc). No abroad.\n"
        "- Ship stay: 5-15 days continuous. Bring clothes, mosquito net, bedsheet.\n"
        "- Leave: No leave first 3 months. Salary based on duty slips.\n"
        "- Resignation: 30-day written notice required.\n"
        "- Future: 6+ months experience opens shipping, logistics, supervision, office careers.\n"
        "- NOT government job. Private company. But real, stable, with growth.\n\n"
        "RULES:\n"
        "- Never mention AI/bot/system/prompt/database.\n"
        "- Never invent facts not listed above.\n"
        "- If promotional text conflicts with policy, policy wins.\n"
        "- Do not promise exact salary — it depends on duty type and experience.\n"
        "- Do not expose private employee data.\n"
        "- Move user toward WhatsApp reply / office visit / confirm interest.\n\n"
        "Respond in JSON: {\"reply\": \"...\", \"memory_updates\": [], \"actions\": []}"
    ),
    "wbom": (
        "You are Azim. Answer business ops query using DATA below. Bangla-first.\n"
        "Factual, short. If data missing, say 'তথ্য পাওয়া যায়নি'.\n"
        "Never guess numbers. Use exact figures from DATA.\n"
        "Respond in JSON: {\"reply\": \"...\", \"memory_updates\": [], \"actions\": []}"
    ),
    "owner": (
        "You are Azim (self-mode). Direct, casual, desi-british, high-energy.\n"
        "Help organize thoughts, manage tasks, plan. Brutally honest.\n"
        "Use 'bro', 'listen', 'honestly'. Full access to all data.\n"
        "Respond in JSON: {\"reply\": \"...\", \"memory_updates\": [], \"actions\": []}"
    ),
    "voice": (
        "You are Azim on phone. Max 1-2 sentences, 8-12 words each.\n"
        "Spoken Bangla. No JSON, bullets, markdown. Natural phone style.\n"
        "If unclear: 'আবার বলবেন?'"
    ),
    "conversation": (
        "You are Azim. Warm, natural. Reply in user's language. 1-3 sentences.\n"
        "Adapt tone per relationship. Remember past conversations.\n"
        "Never reveal AI. Never say 'Certainly!' or 'Of course!'.\n"
        "Respond in JSON: {\"reply\": \"...\", \"memory_updates\": [], \"actions\": []}"
    ),
    "system": (
        "You are Azim. Process system task. Direct, brief.\n"
        "Confirm action taken. No unnecessary detail.\n"
        "Respond in JSON: {\"reply\": \"...\", \"memory_updates\": [], \"actions\": []}"
    ),
    "learning": (
        "You are Azim. Acknowledge and confirm information stored. Brief, direct.\n"
        "Respond in JSON: {\"reply\": \"...\", \"memory_updates\": [], \"actions\": []}"
    ),
}

# ── Per-route context injection flags ────────────────────────
# Only inject what each route actually needs

ROUTE_CONTEXT_FLAGS: dict[str, dict[str, bool]] = {
    "social": {
        "knowledge": True,
        "conversation_memory": True,
        "wbom": False,
        "identity": False,
        "contact": True,
        "history": True,
        "anti_rep": True,
    },
    "wbom": {
        "knowledge": False,
        "conversation_memory": False,
        "wbom": True,
        "identity": False,
        "contact": False,
        "history": False,
        "anti_rep": False,
    },
    "owner": {
        "knowledge": True,
        "conversation_memory": False,
        "wbom": False,
        "identity": False,
        "contact": False,
        "history": True,
        "anti_rep": False,
    },
    "voice": {
        "knowledge": False,
        "conversation_memory": False,
        "wbom": False,
        "identity": False,
        "contact": False,
        "history": True,
        "anti_rep": False,
    },
    "conversation": {
        "knowledge": True,
        "conversation_memory": True,
        "wbom": False,
        "identity": True,
        "contact": False,
        "history": True,
        "anti_rep": True,
    },
    "system": {
        "knowledge": False,
        "conversation_memory": False,
        "wbom": False,
        "identity": False,
        "contact": False,
        "history": False,
        "anti_rep": False,
    },
    "learning": {
        "knowledge": False,
        "conversation_memory": False,
        "wbom": False,
        "identity": False,
        "contact": False,
        "history": False,
        "anti_rep": False,
    },
}

# Relationship tone overlays (appended only for conversation/owner routes)
_RELATIONSHIP_TONES: dict[str, str] = {
    "wife": "Tone: loving husband. Warm, attentive, supportive.",
    "daughter": "Tone: caring father. Age-appropriate, encouraging, fun.",
    "son": "Tone: caring father. Encouraging, warm, guiding.",
    "parent": "Tone: respectful son. Patient, caring, accommodating.",
    "sibling": "Tone: close brother. Casual, supportive, honest.",
}

# ── Prompt cache (per route+message, TTL 120s) ──────────────

_PROMPT_CACHE: dict[str, tuple[str, float]] = {}
_PROMPT_CACHE_TTL = 120
_MAX_PROMPT_CACHE = 300


def _get_prompt_cache(key: str) -> Optional[str]:
    entry = _PROMPT_CACHE.get(key)
    if entry and (_time.monotonic() - entry[1]) < _PROMPT_CACHE_TTL:
        return entry[0]
    return None


def _set_prompt_cache(key: str, value: str) -> None:
    if len(_PROMPT_CACHE) >= _MAX_PROMPT_CACHE:
        oldest = min(_PROMPT_CACHE, key=lambda k: _PROMPT_CACHE[k][1])
        _PROMPT_CACHE.pop(oldest, None)
    _PROMPT_CACHE[key] = (value, _time.monotonic())


def get_route_flags(route: str) -> dict[str, bool]:
    """Get context injection flags for a given route."""
    return ROUTE_CONTEXT_FLAGS.get(route, ROUTE_CONTEXT_FLAGS["conversation"])


def build_route_prompt(
    route: str,
    relationship: str = "social",
    social_context: Optional[str] = None,
    contact_context: Optional[str] = None,
    identity_context: Optional[str] = None,
    knowledge_context: Optional[str] = None,
    wbom_context: Optional[str] = None,
    conversation_memory: Optional[str] = None,
    anti_rep_context: Optional[str] = None,
) -> str:
    """Build the final system prompt for a given route.

    Assembles ONLY the context blocks that this route needs.
    No truncation required — each block is already budget-aware.
    """
    # Check cache
    cache_key = f"rp:{route}:{relationship}"
    if not wbom_context and not knowledge_context and not conversation_memory:
        cached = _get_prompt_cache(cache_key)
        if cached:
            logger.debug(f"Prompt cache hit: {cache_key}")
            return cached

    flags = get_route_flags(route)
    parts: list[str] = []

    # 1. Core behavior prompt (always present)
    base = ROUTE_PROMPTS.get(route, ROUTE_PROMPTS["conversation"])
    parts.append(base)

    # 2. Relationship tone overlay (conversation/owner routes)
    if route in ("conversation", "owner") and relationship in _RELATIONSHIP_TONES:
        parts.append(_RELATIONSHIP_TONES[relationship])

    # 3. Identity context (only if route needs it)
    if flags.get("identity") and identity_context:
        parts.append(identity_context)

    # 4. Social context (social route only)
    if route == "social" and social_context:
        parts.append(f"Context: {social_context}")

    # 5. Contact data (social route with known contact)
    if flags.get("contact") and contact_context:
        parts.append(contact_context)

    # 6. Knowledge context (routes that need factual data)
    if flags.get("knowledge") and knowledge_context:
        parts.append(knowledge_context)

    # 7. WBOM data (ONLY for wbom route)
    if flags.get("wbom") and wbom_context:
        parts.append(f"\n--- BUSINESS DATA ---\n{wbom_context}\n--- END DATA ---")

    # 8. Conversation memory (social/conversation routes)
    if flags.get("conversation_memory") and conversation_memory:
        parts.append(conversation_memory)

    # 9. Anti-repetition (social/conversation routes)
    if flags.get("anti_rep") and anti_rep_context:
        parts.append(anti_rep_context)

    prompt = "\n".join(parts)

    # Cache base prompt (without dynamic context)
    if not wbom_context and not knowledge_context and not conversation_memory:
        _set_prompt_cache(cache_key, prompt)

    logger.info(f"Route prompt built: route={route} rel={relationship} len={len(prompt)}")
    return prompt
