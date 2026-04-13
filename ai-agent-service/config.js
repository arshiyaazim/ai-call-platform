// ============================================================
// AI Agent Service — Configuration
// Centralized config for agent dispatch, provider selection,
// and feature flags. Reads from environment variables.
// ============================================================

"use strict";

const config = {
  // ── Service ──────────────────────────────────────────────
  port: parseInt(process.env.AI_AGENT_PORT || "3200", 10),
  nodeEnv: process.env.NODE_ENV || "production",

  // ── Feature Flags ────────────────────────────────────────
  aiEnabled: (process.env.AI_ENABLED || "true") === "true",

  // ── LiveKit ──────────────────────────────────────────────
  livekit: {
    host: process.env.LIVEKIT_HOST || "http://livekit:7880",
    wsUrl: process.env.LIVEKIT_URL || "ws://livekit:7880",
    apiKey: process.env.LIVEKIT_API_KEY || "",
    apiSecret: process.env.LIVEKIT_API_SECRET || "",
  },

  // ── Redis ────────────────────────────────────────────────
  redis: {
    url: process.env.REDIS_URL || "redis://redis:6379/2",
  },

  // ── Provider Selection (read-only — actual processing in fazle-voice) ──
  stt: {
    provider: process.env.STT_PROVIDER || "whisper",
    // whisper = OpenAI Whisper via livekit-plugins-openai (in fazle-voice)
    // deepgram = Deepgram Nova (future, requires fazle-voice change)
  },
  tts: {
    provider: process.env.TTS_PROVIDER || "piper",
    // piper = local Piper ONNX (default, zero latency)
    // elevenlabs = ElevenLabs cloud (cloned voices)
    // openai = OpenAI TTS
    elevenLabsApiKey: process.env.ELEVENLABS_API_KEY || "",
    elevenLabsVoiceId: process.env.ELEVENLABS_VOICE_ID || "",
  },
  llm: {
    provider: process.env.LLM_PROVIDER || "brain",
    // brain = Fazle Brain (routes to Ollama → OpenAI fallback)
    brainUrl: process.env.FAZLE_BRAIN_URL || "http://fazle-brain:8200",
    openaiApiKey: process.env.OPENAI_API_KEY || "",
  },

  // ── Safety ───────────────────────────────────────────────
  safety: {
    dispatchTimeoutMs: parseInt(process.env.DISPATCH_TIMEOUT_MS || "5000", 10),
    maxResponseTimeSec: parseFloat(process.env.MAX_RESPONSE_TIME_SEC || "7"),
    maxConcurrentAgents: parseInt(process.env.MAX_CONCURRENT_AGENTS || "5", 10),
  },

  // ── Context TTL ──────────────────────────────────────────
  contextTtlSec: parseInt(process.env.CONTEXT_TTL_SEC || "3600", 10),
};

// Validate critical config
function validate() {
  const missing = [];
  if (!config.livekit.apiKey) missing.push("LIVEKIT_API_KEY");
  if (!config.livekit.apiSecret) missing.push("LIVEKIT_API_SECRET");
  if (missing.length > 0) {
    throw new Error(`Missing required env vars: ${missing.join(", ")}`);
  }
}

module.exports = { config, validate };
