// ============================================================
// AI Agent Service — TTS Provider Configuration
// Defines which Text-to-Speech provider is active and provides
// health checks. Actual TTS runs inside fazle-voice
// (Piper local + ElevenLabs hybrid fallback).
// ============================================================

"use strict";

const { config } = require("./config");
const log = require("./logger");

const PROVIDERS = {
  piper: {
    name: "Piper TTS",
    description: "Local ONNX model synthesis (zero-latency, free)",
    requiresApiKey: false,
    service: "fazle-voice",
    async healthCheck() {
      return { status: "active", note: "Runs locally inside fazle-voice" };
    },
  },
  elevenlabs: {
    name: "ElevenLabs",
    description: "Cloud TTS with cloned voices (hybrid: ElevenLabs + Piper fallback)",
    requiresApiKey: true,
    service: "fazle-voice",
    async healthCheck() {
      if (!config.tts.elevenLabsApiKey) {
        return { status: "no_api_key", note: "ELEVENLABS_API_KEY not set" };
      }
      try {
        const resp = await fetch("https://api.elevenlabs.io/v1/user", {
          headers: { "xi-api-key": config.tts.elevenLabsApiKey },
          signal: AbortSignal.timeout(5000),
        });
        if (resp.ok) {
          const data = await resp.json();
          return {
            status: "active",
            character_count: data.subscription?.character_count || 0,
            character_limit: data.subscription?.character_limit || 0,
          };
        }
        return { status: "error", http_status: resp.status };
      } catch (err) {
        return { status: "unreachable", error: err.message };
      }
    },
  },
  openai: {
    name: "OpenAI TTS",
    description: "OpenAI TTS-1 (cloud, high quality)",
    requiresApiKey: true,
    service: "fazle-voice",
    async healthCheck() {
      if (!config.llm.openaiApiKey) {
        return { status: "no_api_key", note: "OPENAI_API_KEY not set" };
      }
      return { status: "available", note: "Uses shared OpenAI API key" };
    },
  },
};

function getCurrentProvider() {
  return PROVIDERS[config.tts.provider] || PROVIDERS.piper;
}

async function getStatus() {
  const provider = getCurrentProvider();
  const health = await provider.healthCheck();
  return {
    provider: config.tts.provider,
    name: provider.name,
    description: provider.description,
    service: provider.service,
    health,
    voice_id: config.tts.elevenLabsVoiceId || "(default)",
  };
}

module.exports = { PROVIDERS, getCurrentProvider, getStatus };
