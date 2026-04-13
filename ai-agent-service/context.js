// ============================================================
// AI Agent Service — Redis Conversation Context
// Stores per-call context: call_sid, transcript, latency.
// Shared with fazle-voice for cross-service context.
// Key pattern: voice:ctx:{room_name}
// ============================================================

"use strict";

const Redis = require("ioredis");
const { config } = require("./config");
const log = require("./logger");

let _redis = null;

function getRedis() {
  if (!_redis) {
    _redis = new Redis(config.redis.url, {
      maxRetriesPerRequest: 3,
      retryStrategy: (times) => Math.min(times * 200, 3000),
      lazyConnect: true,
    });
    _redis.on("error", (err) => {
      log.warn("Redis connection error", { error: err.message });
    });
    _redis.connect().catch(() => {});
  }
  return _redis;
}

/**
 * Store call context when AI agent is dispatched.
 * @param {string} roomName  LiveKit room name
 * @param {object} meta      Call metadata (call_sid, from, to, etc.)
 */
async function storeCallContext(roomName, meta) {
  try {
    const redis = getRedis();
    const key = `voice:ctx:${roomName}`;
    const ctx = {
      ...meta,
      started_at: new Date().toISOString(),
      transcript: [],
      ai_responses: [],
      latency: { stt: [], llm: [], tts: [] },
    };
    await redis.setex(key, config.contextTtlSec, JSON.stringify(ctx));
    log.debug("Call context stored", { room: roomName, call_sid: meta.call_sid });
  } catch (err) {
    log.warn("Failed to store call context", {
      room: roomName,
      error: err.message,
    });
  }
}

/**
 * Retrieve call context for a room.
 */
async function getCallContext(roomName) {
  try {
    const redis = getRedis();
    const raw = await redis.get(`voice:ctx:${roomName}`);
    return raw ? JSON.parse(raw) : null;
  } catch (err) {
    log.warn("Failed to get call context", {
      room: roomName,
      error: err.message,
    });
    return null;
  }
}

/**
 * Add a transcript entry to the call context.
 * @param {string} roomName
 * @param {"user"|"assistant"} role
 * @param {string} text
 */
async function addTranscript(roomName, role, text) {
  try {
    const redis = getRedis();
    const key = `voice:ctx:${roomName}`;
    const raw = await redis.get(key);
    if (!raw) return;
    const ctx = JSON.parse(raw);
    ctx.transcript.push({
      role,
      text,
      at: new Date().toISOString(),
    });
    // Keep last 50 entries
    if (ctx.transcript.length > 50) {
      ctx.transcript = ctx.transcript.slice(-50);
    }
    await redis.setex(key, config.contextTtlSec, JSON.stringify(ctx));
  } catch (err) {
    log.warn("Failed to add transcript", { room: roomName, error: err.message });
  }
}

/**
 * Record a latency measurement.
 * @param {string} roomName
 * @param {"stt"|"llm"|"tts"} stage  Pipeline stage
 * @param {number} ms                Latency in milliseconds
 */
async function recordLatency(roomName, stage, ms) {
  try {
    const redis = getRedis();
    const key = `voice:ctx:${roomName}`;
    const raw = await redis.get(key);
    if (!raw) return;
    const ctx = JSON.parse(raw);
    if (ctx.latency[stage]) {
      ctx.latency[stage].push(ms);
      // Keep last 20 measurements per stage
      if (ctx.latency[stage].length > 20) {
        ctx.latency[stage] = ctx.latency[stage].slice(-20);
      }
    }
    await redis.setex(key, config.contextTtlSec, JSON.stringify(ctx));
  } catch (err) {
    // Non-critical, don't log every time
  }
}

/**
 * Get active call count tracked in Redis.
 */
async function getActiveCallCount() {
  try {
    const redis = getRedis();
    const keys = await redis.keys("voice:ctx:*");
    return keys.length;
  } catch {
    return -1;
  }
}

/**
 * Cleanup: close Redis connection.
 */
async function close() {
  if (_redis) {
    await _redis.quit().catch(() => {});
    _redis = null;
  }
}

module.exports = {
  storeCallContext,
  getCallContext,
  addTranscript,
  recordLatency,
  getActiveCallCount,
  close,
};
