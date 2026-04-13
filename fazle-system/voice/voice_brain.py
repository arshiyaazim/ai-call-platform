# ============================================================
# Fazle Voice Brain — Real-time Conversational Voice Engine
# Manages voice call sessions, interrupt handling, chunked
# speech output, silence detection, and context-aware routing.
# Plugs into existing LiveKit + Whisper + Piper pipeline.
# ============================================================
import asyncio
import json
import logging
import re
import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import AsyncGenerator, Optional

import httpx

logger = logging.getLogger("fazle-voice-brain")


# ── Session State ───────────────────────────────────────────

class SpeakingState(str, Enum):
    IDLE = "idle"
    USER_SPEAKING = "user_speaking"
    AI_SPEAKING = "ai_speaking"
    INTERRUPTED = "interrupted"


@dataclass
class VoiceSession:
    """Per-call conversational state."""
    session_id: str
    user_id: str
    user_name: str
    relationship: str  # "social" for external callers
    voice_id: str = ""  # ElevenLabs cloned voice ID for this session
    history: list[dict] = field(default_factory=list)
    last_intent: str = "COLD"
    speaking_state: SpeakingState = SpeakingState.IDLE
    last_activity: float = 0.0
    silence_prompted: bool = False
    created_at: float = 0.0
    # Interrupt control
    _cancel_event: asyncio.Event = field(default_factory=asyncio.Event)

    def __post_init__(self):
        now = time.monotonic()
        if not self.created_at:
            self.created_at = now
        if not self.last_activity:
            self.last_activity = now


# ── Sentence Chunker ────────────────────────────────────────

# Split on Bangla purno biram (।), English period/exclamation/question, or comma pause
_CHUNK_RE = re.compile(r'(?<=[।.!?])\s+|(?<=,)\s+(?=\S)')


def chunk_response(text: str) -> list[str]:
    """Split a response into natural speech chunks for sequential TTS.

    Splits on sentence boundaries (।.!?) and comma pauses.
    Returns list of non-empty trimmed chunks.
    """
    if not text or not text.strip():
        return []
    parts = _CHUNK_RE.split(text.strip())
    return [p.strip() for p in parts if p and p.strip()]


# ── Complex Query Detection ─────────────────────────────────

_COMPLEX_KEYWORDS = frozenset([
    "remember", "schedule", "remind", "search", "find", "look up",
    "what did i", "what do you know", "tell me about", "who is",
    "create", "set up", "configure",
    # Bangla complex triggers
    "মনে রাখো", "খুঁজে দাও", "কে ছিল", "কি জানো", "বলো তো",
])


def is_complex_query(message: str) -> bool:
    """Determine if a message needs full agent pipeline or can use fast path."""
    msg_lower = message.lower()
    if len(msg_lower.split()) > 15:
        return True
    return any(kw in msg_lower for kw in _COMPLEX_KEYWORDS)


# ── Voice Brain Manager ────────────────────────────────────

class VoiceBrainManager:
    """Manages voice call sessions and orchestrates the brain pipeline.

    Designed to be instantiated once per voice worker process and
    shared across concurrent call sessions.
    """

    def __init__(
        self,
        brain_url: str = "http://fazle-brain:8200",
        redis_url: str = "",
        max_history: int = 10,
        silence_prompt_sec: float = 8.0,
        silence_hangup_sec: float = 15.0,
    ):
        self.brain_url = brain_url
        self.max_history = max_history
        self.silence_prompt_sec = silence_prompt_sec
        self.silence_hangup_sec = silence_hangup_sec

        # In-memory session store (one voice worker = limited sessions)
        self._sessions: dict[str, VoiceSession] = {}

        # Shared HTTP client for brain calls (connection pooling)
        self._http: httpx.AsyncClient | None = None

        # Optional Redis for cross-worker persistence
        self._redis = None
        self._redis_url = redis_url

    async def _get_http(self) -> httpx.AsyncClient:
        if self._http is None or self._http.is_closed:
            self._http = httpx.AsyncClient(
                timeout=httpx.Timeout(connect=5.0, read=60.0, write=5.0, pool=5.0),
            )
        return self._http

    def _get_redis(self):
        if self._redis is None and self._redis_url:
            try:
                import redis as redis_lib
                self._redis = redis_lib.Redis.from_url(
                    self._redis_url, decode_responses=True
                )
            except Exception as e:
                logger.warning(f"Redis unavailable for voice sessions: {e}")
        return self._redis

    # ── Session lifecycle ───────────────────────────────────

    def create_session(
        self,
        user_id: str,
        user_name: str = "User",
        relationship: str = "social",
        session_id: str | None = None,
        voice_id: str = "",
    ) -> VoiceSession:
        """Create a new voice call session."""
        sid = session_id or str(uuid.uuid4())
        session = VoiceSession(
            session_id=sid,
            user_id=user_id,
            user_name=user_name,
            relationship=relationship,
            voice_id=voice_id,
        )
        self._sessions[sid] = session
        logger.info(
            f"Voice session created: {sid} user={user_name} rel={relationship}"
        )
        return session

    def get_session(self, session_id: str) -> VoiceSession | None:
        return self._sessions.get(session_id)

    def end_session(self, session_id: str) -> None:
        """Clean up a voice session and persist history if Redis available."""
        session = self._sessions.pop(session_id, None)
        if session:
            self._persist_history(session)
            logger.info(
                f"Voice session ended: {session_id} "
                f"turns={len(session.history)} "
                f"duration={time.monotonic() - session.created_at:.1f}s"
            )

    def _persist_history(self, session: VoiceSession) -> None:
        """Best-effort persist conversation to Redis for learning engine."""
        r = self._get_redis()
        if not r:
            return
        try:
            key = f"fazle:voice_conv:{session.session_id}"
            r.setex(key, 86400, json.dumps(session.history))
        except Exception as e:
            logger.warning(f"Failed to persist voice history: {e}")

    # ── Input handling ──────────────────────────────────────

    async def handle_user_speech(
        self,
        session_id: str,
        transcript: str,
        is_final: bool = True,
    ) -> AsyncGenerator[str, None]:
        """Process user speech and yield response text chunks.

        Args:
            session_id: Active session ID
            transcript: STT output text
            is_final: True for final transcript, False for partial

        Yields:
            Text chunks suitable for sequential TTS playback
        """
        session = self.get_session(session_id)
        if not session:
            logger.error(f"No session found: {session_id}")
            yield "দুঃখিত, কিছু সমস্যা হয়েছে।"
            return

        session.last_activity = time.monotonic()
        session.silence_prompted = False

        # Partial transcripts: only monitor, don't process
        if not is_final:
            session.speaking_state = SpeakingState.USER_SPEAKING
            return

        # Final transcript: process through brain
        transcript = transcript.strip()
        if not transcript:
            return

        session.speaking_state = SpeakingState.IDLE

        # Add to history
        session.history.append({"role": "user", "content": transcript})
        self._trim_history(session)

        # Clear any previous cancel signal
        session._cancel_event.clear()

        # Generate response
        session.speaking_state = SpeakingState.AI_SPEAKING
        try:
            async for chunk in self._generate_response(session, transcript):
                # Check for interruption
                if session._cancel_event.is_set():
                    logger.info(f"Response interrupted: {session_id}")
                    session.speaking_state = SpeakingState.INTERRUPTED
                    return
                yield chunk

            # Collect full response for history
            # (chunks already yielded, history updated in _generate_response)
        except Exception as e:
            logger.error(f"Response generation failed: {e}")
            fallback = "দুঃখিত, আবার বলবেন?"
            yield fallback
            session.history.append({"role": "assistant", "content": fallback})
        finally:
            if session.speaking_state == SpeakingState.AI_SPEAKING:
                session.speaking_state = SpeakingState.IDLE

    # ── Interrupt handling ──────────────────────────────────

    def interrupt_current_response(self, session_id: str) -> bool:
        """Signal the active response to stop immediately.

        Returns True if an active response was interrupted.
        """
        session = self.get_session(session_id)
        if not session:
            return False

        if session.speaking_state == SpeakingState.AI_SPEAKING:
            session._cancel_event.set()
            session.speaking_state = SpeakingState.INTERRUPTED
            logger.info(f"Interrupted AI response: {session_id}")
            return True
        return False

    # ── Silence detection ───────────────────────────────────

    async def check_silence(self, session_id: str) -> str | None:
        """Check if user has been silent too long.

        Returns:
            None: No action needed
            "prompt": Should prompt user ("আপনি আছেন?")
            "hangup": Should end the call
        """
        session = self.get_session(session_id)
        if not session:
            return None

        if session.speaking_state != SpeakingState.IDLE:
            return None

        elapsed = time.monotonic() - session.last_activity

        if elapsed >= self.silence_hangup_sec:
            return "hangup"

        if elapsed >= self.silence_prompt_sec and not session.silence_prompted:
            session.silence_prompted = True
            return "prompt"

        return None

    # ── Response generation ─────────────────────────────────

    async def _generate_response(
        self,
        session: VoiceSession,
        message: str,
    ) -> AsyncGenerator[str, None]:
        """Generate a voice-optimized response via brain.

        Routes simple queries to /chat/fast, complex to /chat/voice.
        Chunks the response for natural TTS delivery.
        """
        full_response = ""
        llm_start = time.monotonic()

        if is_complex_query(message):
            # Full pipeline: persona + memory + streaming
            full_response = await self._call_brain_voice(session, message)
        else:
            # Fast path: direct Ollama, <500ms
            full_response = await self._call_brain_fast(message)

        llm_ms = int((time.monotonic() - llm_start) * 1000)
        logger.info(f"[LATENCY] LLM response: {llm_ms}ms | complex={is_complex_query(message)} | len={len(full_response)}")

        if not full_response:
            full_response = "দুঃখিত, আবার বলবেন?"

        # Store assistant response in history
        session.history.append({"role": "assistant", "content": full_response})
        self._trim_history(session)

        # Chunk and yield for TTS
        chunks = chunk_response(full_response)
        for chunk in chunks:
            if session._cancel_event.is_set():
                return
            yield chunk

    async def _call_brain_voice(
        self, session: VoiceSession, message: str
    ) -> str:
        """Call brain /chat/voice endpoint with full persona + memory."""
        client = await self._get_http()
        try:
            resp = await client.post(
                f"{self.brain_url}/chat/voice",
                json={
                    "message": message,
                    "user_id": session.user_id,
                    "user_name": session.user_name,
                    "relationship": session.relationship,
                    "conversation_id": session.session_id,
                    "history": session.history[-self.max_history :],
                },
            )
            resp.raise_for_status()
            data = resp.json()
            return data.get("reply", "")
        except Exception as e:
            logger.error(f"Brain /chat/voice failed: {e}")
            # Fallback to streaming
            return await self._call_brain_stream_fallback(session, message)

    async def _call_brain_fast(self, message: str) -> str:
        """Call brain /chat/fast for simple queries — collect streamed chunks."""
        client = await self._get_http()
        try:
            collected = []
            async with client.stream(
                "POST",
                f"{self.brain_url}/chat/fast",
                json={"message": message, "source": "voice"},
            ) as resp:
                resp.raise_for_status()
                async for line in resp.aiter_lines():
                    if line.startswith("data: "):
                        chunk_str = line[6:].strip()
                        if not chunk_str:
                            continue
                        try:
                            data = json.loads(chunk_str)
                            text = data.get("content", "")
                            if text:
                                collected.append(text)
                            if data.get("done"):
                                break
                        except json.JSONDecodeError:
                            continue
            return "".join(collected)
        except Exception as e:
            logger.error(f"Brain /chat/fast failed: {e}")
            return ""

    async def _call_brain_stream_fallback(
        self, session: VoiceSession, message: str
    ) -> str:
        """Fallback: call /chat/stream and collect full response."""
        client = await self._get_http()
        try:
            collected = []
            async with client.stream(
                "POST",
                f"{self.brain_url}/chat/stream",
                json={
                    "message": message,
                    "user_id": session.user_id,
                    "user_name": session.user_name,
                    "relationship": session.relationship,
                    "source": "voice",
                },
            ) as resp:
                resp.raise_for_status()
                async for line in resp.aiter_lines():
                    if line.startswith("data: "):
                        chunk_str = line[6:].strip()
                        if not chunk_str:
                            continue
                        try:
                            data = json.loads(chunk_str)
                            text = data.get("content", "")
                            if text:
                                collected.append(text)
                            if data.get("done"):
                                break
                        except json.JSONDecodeError:
                            continue
            return "".join(collected)
        except Exception as e:
            logger.error(f"Brain /chat/stream fallback also failed: {e}")
            return ""

    # ── Utility ─────────────────────────────────────────────

    def _trim_history(self, session: VoiceSession) -> None:
        """Keep only the last N turns in session history."""
        max_items = self.max_history * 2  # Each turn = user + assistant
        if len(session.history) > max_items:
            session.history = session.history[-max_items:]

    async def close(self) -> None:
        """Cleanup resources."""
        if self._http and not self._http.is_closed:
            await self._http.aclose()

    # ── Greeting helper ─────────────────────────────────────

    def get_greeting(self, session: VoiceSession) -> str:
        """Generate a natural greeting based on relationship."""
        name = session.user_name
        rel = session.relationship

        if rel == "self":
            return "হ্যাঁ, বলো।"
        elif rel == "wife":
            return f"হ্যাঁ {name}, বলো।"
        elif rel in ("daughter", "son"):
            return f"হ্যাঁ বাবা, বলো কি হয়েছে?"
        elif rel == "social":
            return "আসসালামু আলাইকুম, বলুন কিভাবে সাহায্য করতে পারি?"
        else:
            return f"হ্যাঁ {name}, বলো।"

    # ── Silence prompts ─────────────────────────────────────

    SILENCE_PROMPT = "আপনি আছেন?"
    GOODBYE_MSG = "ঠিক আছে, ধন্যবাদ। পরে কথা হবে।"
