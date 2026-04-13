# ============================================================
# Fazle Voice Agent — LiveKit-based voice interface
# Joins rooms, transcribes speech, queries Brain, speaks reply
# Uses OpenAI Realtime or Whisper STT + TTS pipeline
# Enhanced with VoiceBrainManager for session management,
# interrupt handling, chunked speech output, and silence detection
#
# Supports both browser-originated (WebRTC) and Twilio/SIP calls.
# SIP participants are auto-detected and assigned social defaults.
# ============================================================
import asyncio
import json
import logging
import os
import time

import httpx
from livekit import rtc
from livekit.agents import (
    AutoSubscribe,
    JobContext,
    JobProcess,
    WorkerOptions,
    cli,
    llm,
)
from livekit.agents.pipeline import VoicePipelineAgent
from livekit.plugins import openai, silero
from pydantic_settings import BaseSettings

from voice_brain import VoiceBrainManager, SpeakingState

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("fazle-voice")


class Settings(BaseSettings):
    openai_api_key: str = ""
    brain_url: str = "http://fazle-brain:8200"
    tts_voice: str = "alloy"
    tts_engine: str = "piper"
    voice_model: str = "en_US-lessac-medium"
    voice_model_dir: str = "/models"
    livekit_url: str = "ws://livekit:7880"
    livekit_api_key: str = ""
    livekit_api_secret: str = ""
    fast_mode: bool = True
    redis_url: str = "redis://redis:6379/1"
    silence_prompt_sec: float = 8.0
    silence_hangup_sec: float = 15.0
    max_history: int = 10

    class Config:
        env_prefix = "FAZLE_VOICE_"


settings = Settings()

# Also read from common env vars
OPENAI_API_KEY = settings.openai_api_key or os.getenv("OPENAI_API_KEY", "")
BRAIN_URL = settings.brain_url or os.getenv("FAZLE_BRAIN_URL", "http://fazle-brain:8200")
TTS_ENGINE = settings.tts_engine or os.getenv("FAZLE_VOICE_TTS_ENGINE", "piper")
VOICE_MODEL = settings.voice_model or os.getenv("FAZLE_VOICE_VOICE_MODEL", "en_US-lessac-medium")
VOICE_MODEL_DIR = settings.voice_model_dir or os.getenv("FAZLE_VOICE_VOICE_MODEL_DIR", "/models")

# ── ElevenLabs (optional, hybrid TTS) ───────────────────────
ELEVENLABS_API_KEY = os.getenv("ELEVENLABS_API_KEY", "")
ELEVENLABS_VOICE_ID = os.getenv("ELEVENLABS_VOICE_ID", "")

if ELEVENLABS_API_KEY:
    logger.info("ElevenLabs API key detected — hybrid TTS available")
else:
    logger.info("No ElevenLabs API key — using Piper/OpenAI TTS only")

# ── Global Voice Brain Manager (shared across sessions) ─────
voice_brain = VoiceBrainManager(
    brain_url=BRAIN_URL,
    redis_url=settings.redis_url or os.getenv("REDIS_URL", ""),
    max_history=settings.max_history,
    silence_prompt_sec=settings.silence_prompt_sec,
    silence_hangup_sec=settings.silence_hangup_sec,
)


def build_tts():
    """Build the TTS engine — Piper (local) or OpenAI (remote)."""
    if TTS_ENGINE == "piper":
        from piper_tts import PiperTTS
        model_path = os.path.join(VOICE_MODEL_DIR, f"{VOICE_MODEL}.onnx")
        logger.info(f"Using Piper TTS: {model_path}")
        return PiperTTS(model_path=model_path)
    else:
        logger.info(f"Using OpenAI TTS: voice={settings.tts_voice}")
        return openai.TTS(api_key=OPENAI_API_KEY, voice=settings.tts_voice)


def build_piper_tts():
    """Build Piper TTS (always available as fallback)."""
    from piper_tts import PiperTTS
    model_path = os.path.join(VOICE_MODEL_DIR, f"{VOICE_MODEL}.onnx")
    return PiperTTS(model_path=model_path)


def build_session_tts(piper, voice_id: str = ""):
    """Build per-session TTS with ElevenLabs hybrid support.

    Priority: ElevenLabs cloned voice > ElevenLabs default voice > Piper.
    """
    if TTS_ENGINE == "openai":
        return openai.TTS(api_key=OPENAI_API_KEY, voice=settings.tts_voice)

    el_voice_id = voice_id or ELEVENLABS_VOICE_ID
    if ELEVENLABS_API_KEY and el_voice_id:
        from piper_tts import ElevenLabsTTS
        logger.info(f"Session TTS: ElevenLabs hybrid (voice_id={el_voice_id})")
        return ElevenLabsTTS(
            api_key=ELEVENLABS_API_KEY,
            voice_id=el_voice_id,
            piper_fallback=piper,
        )

    return piper


async def query_brain(message: str, user_id: str, user_name: str, relationship: str) -> str:
    """Send transcribed text to Fazle Brain and get a response."""
    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            resp = await client.post(
                f"{BRAIN_URL}/chat",
                json={
                    "message": message,
                    "user": user_name,
                    "user_id": user_id,
                    "user_name": user_name,
                    "relationship": relationship,
                },
            )
            resp.raise_for_status()
            data = resp.json()
            return data.get("reply", "I didn't catch that. Could you say it again?")
        except Exception as e:
            logger.error(f"Brain query failed: {e}")
            return "Sorry, I'm having trouble thinking right now. Give me a moment."


# Keywords that signal a complex query needing full AI pipeline
_COMPLEX_KEYWORDS = frozenset([
    "remember", "schedule", "remind", "search", "find", "look up",
    "what did i", "what do you know", "tell me about", "who is",
    "create", "set up", "configure",
])


def route_query(message: str) -> str:
    """Decide endpoint: /chat/agent/stream (agent pipeline) or /chat/fast (ultra-low latency).
    Returns the endpoint path to use."""
    if not settings.fast_mode:
        return "/chat/agent/stream"
    msg_lower = message.lower()
    if any(kw in msg_lower for kw in _COMPLEX_KEYWORDS):
        return "/chat/agent/stream"
    # Short conversational messages → fast path
    return "/chat/fast"


async def query_brain_fast(message: str):
    """Stream from Brain /chat/fast — ultra-low latency, no preprocessing."""
    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            async with client.stream(
                "POST",
                f"{BRAIN_URL}/chat/fast",
                json={"message": message, "source": "voice"},
            ) as resp:
                resp.raise_for_status()
                async for line in resp.aiter_lines():
                    if line.startswith("data: "):
                        chunk_str = line[6:].strip()
                        if not chunk_str:
                            continue
                        try:
                            chunk = json.loads(chunk_str)
                            text = chunk.get("content", "")
                            done = chunk.get("done", False)
                            if text:
                                yield text
                            if done:
                                break
                        except json.JSONDecodeError:
                            continue
        except Exception as e:
            logger.error(f"Brain fast stream failed, falling back to agent stream: {e}")
            async for text in query_brain_stream(message, "", "", "self"):
                yield text


async def query_brain_stream(message: str, user_id: str, user_name: str, relationship: str):
    """Stream response from Fazle Brain /chat/agent/stream endpoint. Yields text chunks."""
    async with httpx.AsyncClient(timeout=60.0) as client:
        try:
            async with client.stream(
                "POST",
                f"{BRAIN_URL}/chat/agent/stream",
                json={
                    "message": message,
                    "user": user_name,
                    "user_id": user_id,
                    "user_name": user_name,
                    "relationship": relationship,
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
                            chunk = json.loads(chunk_str)
                            text = chunk.get("content", "")
                            done = chunk.get("done", False)
                            if text:
                                yield text
                            if done:
                                break
                        except json.JSONDecodeError:
                            continue
        except Exception as e:
            logger.error(f"Brain stream failed: {e}")
            yield "Sorry, I'm having trouble thinking right now."


class FazleLLM(llm.LLM):
    """Custom LLM adapter that routes through VoiceBrainManager + Fazle Brain."""

    def __init__(self):
        super().__init__()
        self._session_id = ""
        self._user_id = ""
        self._user_name = "User"
        self._relationship = "self"

    def set_user_context(self, user_id: str, user_name: str, relationship: str):
        self._user_id = user_id
        self._user_name = user_name
        self._relationship = relationship

    def set_session_id(self, session_id: str):
        self._session_id = session_id

    async def chat(
        self,
        *,
        chat_ctx: llm.ChatContext,
        **kwargs,
    ) -> "llm.LLMStream":
        # Extract the last user message
        last_message = ""
        for msg in reversed(chat_ctx.messages):
            if msg.role == "user" and msg.content:
                last_message = msg.content
                break

        return _VoiceBrainStream(
            session_id=self._session_id,
            message=last_message,
            chat_ctx=chat_ctx,
        )


class _VoiceBrainStream(llm.LLMStream):
    """Streams voice brain response chunks as an LLM stream for TTS."""

    def __init__(self, session_id: str, message: str, chat_ctx: llm.ChatContext):
        super().__init__(chat_ctx=chat_ctx)
        self._session_id = session_id
        self._message = message
        self._gen = None
        self._done = False

    async def __anext__(self) -> llm.ChatChunk:
        if self._done:
            raise StopAsyncIteration
        if self._gen is None:
            self._gen = voice_brain.handle_user_speech(
                self._session_id, self._message, is_final=True
            )
        try:
            text = await self._gen.__anext__()
            delta = llm.ChoiceDelta(role="assistant", content=text)
            choice = llm.Choice(delta=delta, index=0)
            return llm.ChatChunk(choices=[choice])
        except StopAsyncIteration:
            self._done = True
            raise

    async def aclose(self):
        self._done = True


class _SingleResponseStream(llm.LLMStream):
    """Wraps a single string response as an LLM stream (fallback)."""

    def __init__(self, text: str, chat_ctx: llm.ChatContext):
        super().__init__(chat_ctx=chat_ctx)
        self._text = text
        self._sent = False

    async def __anext__(self) -> llm.ChatChunk:
        if self._sent:
            raise StopAsyncIteration
        self._sent = True
        delta = llm.ChoiceDelta(role="assistant", content=self._text)
        choice = llm.Choice(delta=delta, index=0)
        return llm.ChatChunk(choices=[choice])

    async def aclose(self):
        pass


def prewarm(proc: JobProcess):
    """Preload VAD + TTS models for faster startup."""
    proc.userdata["vad"] = silero.VAD.load()
    proc.userdata["piper_tts"] = build_piper_tts()
    logger.info("Prewarmed: VAD + Piper TTS")


# ── SIP / Twilio Participant Detection ──────────────────────

def _is_sip_participant(participant) -> bool:
    """Detect if a participant originated from SIP/Twilio (phone call)."""
    # LiveKit protocol: kind 3 = SIP
    if hasattr(participant, "kind") and participant.kind == 3:
        return True
    identity = (participant.identity or "").lower()
    return (
        identity.startswith("sip_")
        or identity.startswith("sip:")
        or identity.startswith("phone_")
        or identity.startswith("phone:")
        or bool(
            identity.startswith("+") and len(identity) > 7 and identity[1:].replace("-", "").isdigit()
        )
    )


def _extract_phone_from_identity(identity: str) -> str:
    """Extract phone number from SIP-style identity (e.g., 'sip_+447863767879')."""
    import re
    match = re.search(r"\+\d+", identity)
    return match.group(0) if match else ""


def _try_load_redis_context(room_name: str):
    """Best-effort load call context from Redis (stored by ai-agent-service)."""
    try:
        redis_url = settings.redis_url or os.getenv("REDIS_URL", "")
        if not redis_url:
            return
        # Use DB 2 for ai-agent-service context
        ctx_redis_url = redis_url.rsplit("/", 1)[0] + "/2"
        import redis as redis_lib
        r = redis_lib.Redis.from_url(ctx_redis_url, decode_responses=True)
        raw = r.get(f"voice:ctx:{room_name}")
        r.close()
        if raw:
            ctx = json.loads(raw)
            logger.info(f"Loaded Redis context for room {room_name}: call_sid={ctx.get('call_sid')}")
    except Exception as e:
        logger.debug(f"Redis context load skipped: {e}")


async def entrypoint(ctx: JobContext):
    """Main entrypoint for each voice session."""
    logger.info(f"Voice agent joining room: {ctx.room.name}")

    # ── AI_ENABLED check (dispatched by ai-agent-service) ───
    ai_enabled = os.getenv("AI_ENABLED", "true").lower()
    if ai_enabled == "false":
        logger.info(f"AI_ENABLED=false, skipping room: {ctx.room.name}")
        return

    # Extract user context from participant metadata
    # The token endpoint sets: identity=user_id, name=user_name, metadata=relationship
    await ctx.connect(auto_subscribe=AutoSubscribe.AUDIO_ONLY)

    participant = await ctx.wait_for_participant()
    user_id = participant.identity or "unknown"
    user_name = participant.name or "User"

    # ── Detect SIP/Twilio participants ──────────────────────
    is_sip = _is_sip_participant(participant)

    # Parse metadata — supports JSON (new) and plain string (legacy)
    raw_metadata = participant.metadata or ""
    try:
        meta = json.loads(raw_metadata)
        relationship = meta.get("relationship", "social" if is_sip else "self")
        session_voice_id = meta.get("voice_id", "")
        call_sid = meta.get("call_sid", "")
    except (json.JSONDecodeError, TypeError, ValueError):
        relationship = raw_metadata if raw_metadata and not is_sip else ("social" if is_sip else "self")
        session_voice_id = ""
        call_sid = ""

    # For SIP participants, extract phone number from identity
    if is_sip:
        phone = _extract_phone_from_identity(user_id)
        if phone:
            user_name = phone
        if not call_sid:
            call_sid = ctx.room.name  # Room name may encode call_sid
        logger.info(f"SIP/Twilio call detected: phone={phone or user_id}, call_sid={call_sid}")

    # Try to read context from Redis (stored by ai-agent-service)
    _try_load_redis_context(ctx.room.name)

    logger.info(f"Voice session: user={user_name}, relationship={relationship}, id={user_id}, voice_id={session_voice_id or 'none'}, sip={is_sip}")

    # Create a voice brain session for this call
    session = voice_brain.create_session(
        user_id=user_id,
        user_name=user_name,
        relationship=relationship,
        session_id=ctx.room.name,
        voice_id=session_voice_id,
    )

    # Build per-session TTS (ElevenLabs hybrid if available, else Piper)
    piper_tts = ctx.proc.userdata["piper_tts"]
    session_tts = build_session_tts(piper_tts, voice_id=session_voice_id)

    # Build the voice pipeline with brain-backed LLM
    fazle_llm = FazleLLM()
    fazle_llm.set_user_context(user_id, user_name, relationship)
    fazle_llm.set_session_id(session.session_id)

    initial_ctx = llm.ChatContext()
    initial_ctx.append(
        role="system",
        text=(
            f"You are Azim speaking to {user_name} (your {relationship}). "
            "Keep responses concise and natural for voice conversation. "
            "Max 1-2 sentences per response. Speak warmly and directly. "
            "Use natural spoken Bangla. No bullet points or long explanations."
        ),
    )

    agent = VoicePipelineAgent(
        vad=ctx.proc.userdata["vad"],
        stt=openai.STT(api_key=OPENAI_API_KEY),
        llm=fazle_llm,
        tts=session_tts,
        chat_ctx=initial_ctx,
        min_endpointing_delay=0.5,
        allow_interruptions=True,
    )

    agent.start(ctx.room, participant)

    # Log pipeline latency on speech events
    _stt_start = [0.0]
    _llm_start = [0.0]

    @agent.on("user_speech_committed")
    def on_user_speech(msg):
        _stt_start[0] = time.monotonic()
        logger.info(f"[LATENCY] User speech committed: {str(msg)[:80]}")

    @agent.on("agent_speech_committed")
    def on_agent_speech(msg):
        if _stt_start[0] > 0:
            total_ms = int((time.monotonic() - _stt_start[0]) * 1000)
            logger.info(f"[LATENCY] Full pipeline (STT→LLM→TTS): {total_ms}ms")
            _stt_start[0] = 0.0

    # Natural greeting via voice brain
    greeting = voice_brain.get_greeting(session)
    await agent.say(greeting, allow_interruptions=True)

    # Register interrupt handler: when user starts speaking, interrupt AI
    @ctx.room.on("track_subscribed")
    def on_track_subscribed(track: rtc.Track, *args):
        if track.kind == rtc.TrackKind.KIND_AUDIO:
            voice_brain.interrupt_current_response(session.session_id)

    # Silence detection loop
    async def silence_monitor():
        while session.session_id in voice_brain._sessions:
            await asyncio.sleep(2.0)
            action = await voice_brain.check_silence(session.session_id)
            if action == "prompt":
                try:
                    await agent.say(
                        voice_brain.SILENCE_PROMPT,
                        allow_interruptions=True,
                    )
                except Exception:
                    pass
            elif action == "hangup":
                try:
                    await agent.say(
                        voice_brain.GOODBYE_MSG,
                        allow_interruptions=False,
                    )
                except Exception:
                    pass
                logger.info(f"Silence hangup: {session.session_id}")
                break

    silence_task = asyncio.create_task(silence_monitor())

    # Wait for the room to close (call ends)
    try:
        await ctx.room.disconnected()
    finally:
        silence_task.cancel()
        voice_brain.end_session(session.session_id)
        logger.info(f"Voice call ended: {session.session_id}")


if __name__ == "__main__":
    cli.run_app(
        WorkerOptions(
            entrypoint_fnc=entrypoint,
            prewarm_fnc=prewarm,
            initialize_process_timeout=60.0,
            api_key=settings.livekit_api_key or os.getenv("LIVEKIT_API_KEY", ""),
            api_secret=settings.livekit_api_secret or os.getenv("LIVEKIT_API_SECRET", ""),
            ws_url=settings.livekit_url or os.getenv("LIVEKIT_URL", "ws://livekit:7880"),
        ),
    )
