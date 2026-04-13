// ============================================================
// AI Agent Service — LLM Provider Configuration
// Defines which LLM provider is active and provides health
// checks. Actual LLM inference runs through fazle-brain
// (Ollama qwen2.5:1.5b → OpenAI gpt-4o fallback).
// ============================================================

"use strict";

const { config } = require("./config");
const log = require("./logger");

const PROVIDERS = {
  brain: {
    name: "Fazle Brain",
    description: "Multi-agent brain → LLM Gateway (Ollama primary, OpenAI fallback)",
    requiresApiKey: false,
    async healthCheck() {
      try {
        const resp = await fetch(`${config.llm.brainUrl}/health`, {
          signal: AbortSignal.timeout(5000),
        });
        if (resp.ok) {
          const data = await resp.json();
          return {
            status: "healthy",
            brain_version: data.version || "unknown",
            uptime: data.uptime || "unknown",
          };
        }
        return { status: "unhealthy", http_status: resp.status };
      } catch (err) {
        return { status: "unreachable", error: err.message };
      }
    },
  },
  openai: {
    name: "OpenAI Direct",
    description: "Direct OpenAI gpt-4o (bypasses brain, no memory/persona)",
    requiresApiKey: true,
    async healthCheck() {
      if (!config.llm.openaiApiKey) {
        return { status: "no_api_key", note: "OPENAI_API_KEY not set" };
      }
      try {
        const resp = await fetch("https://api.openai.com/v1/models", {
          headers: { Authorization: `Bearer ${config.llm.openaiApiKey}` },
          signal: AbortSignal.timeout(5000),
        });
        return resp.ok
          ? { status: "active" }
          : { status: "error", http_status: resp.status };
      } catch (err) {
        return { status: "unreachable", error: err.message };
      }
    },
  },
  ollama: {
    name: "Ollama Direct",
    description: "Direct Ollama qwen2.5:1.5b (bypasses brain, no memory/persona)",
    requiresApiKey: false,
    async healthCheck() {
      try {
        const resp = await fetch("http://ollama:11434/api/tags", {
          signal: AbortSignal.timeout(5000),
        });
        if (resp.ok) {
          const data = await resp.json();
          const models = (data.models || []).map((m) => m.name);
          return { status: "active", models };
        }
        return { status: "error", http_status: resp.status };
      } catch (err) {
        return { status: "unreachable", error: err.message };
      }
    },
  },
};

function getCurrentProvider() {
  return PROVIDERS[config.llm.provider] || PROVIDERS.brain;
}

async function getStatus() {
  const provider = getCurrentProvider();
  const health = await provider.healthCheck();
  return {
    provider: config.llm.provider,
    name: provider.name,
    description: provider.description,
    health,
  };
}

module.exports = { PROVIDERS, getCurrentProvider, getStatus };
