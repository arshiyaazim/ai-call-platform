// ============================================================
// AI Agent Service — Main Server
// Receives LiveKit webhooks, detects Twilio/SIP participants,
// and dispatches the fazle-voice AI agent to their rooms.
//
// This is NOT a duplicate voice pipeline. It is the dispatcher
// that connects Twilio inbound calls to the EXISTING fazle-voice
// agent (STT → Brain → TTS via LiveKit Agents SDK).
//
// Flow:
//   LiveKit webhook (participant_joined, kind=SIP)
//   → check AI_ENABLED
//   → check no agent already in room
//   → dispatch fazle-voice via Agent Dispatch API
//   → store call context in Redis
// ============================================================

"use strict";

const express = require("express");
const { config, validate } = require("./config");
const log = require("./logger");
const lk = require("./livekit-client");
const context = require("./context");
const stt = require("./stt");
const tts = require("./tts");
const llm = require("./llm");

// ── Metrics (in-memory counters) ───────────────────────────

const metrics = {
  webhooks_received: 0,
  dispatches_attempted: 0,
  dispatches_succeeded: 0,
  dispatches_failed: 0,
  dispatches_skipped_ai_disabled: 0,
  dispatches_skipped_agent_present: 0,
  dispatches_skipped_non_sip: 0,
  errors: 0,
  started_at: new Date().toISOString(),
};

// ── Express App ────────────────────────────────────────────

const app = express();

// LiveKit webhooks send raw JSON — we need raw body for signature validation
app.use(
  "/webhook/livekit",
  express.raw({ type: "*/*", limit: "1mb" })
);
app.use(express.json({ limit: "1mb" }));

// ── Health Check ───────────────────────────────────────────

app.get("/health", (_req, res) => {
  res.json({
    status: "ok",
    service: "ai-agent-service",
    ai_enabled: config.aiEnabled,
    uptime_sec: Math.floor(process.uptime()),
  });
});

// ── Metrics ────────────────────────────────────────────────

app.get("/metrics", (_req, res) => {
  res.json({
    ...metrics,
    uptime_sec: Math.floor(process.uptime()),
    ai_enabled: config.aiEnabled,
    providers: {
      stt: config.stt.provider,
      tts: config.tts.provider,
      llm: config.llm.provider,
    },
  });
});

// ── Provider Status ────────────────────────────────────────

app.get("/status/providers", async (_req, res) => {
  try {
    const [sttStatus, ttsStatus, llmStatus] = await Promise.all([
      stt.getStatus(),
      tts.getStatus(),
      llm.getStatus(),
    ]);
    res.json({ stt: sttStatus, tts: ttsStatus, llm: llmStatus });
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

// ── Active Calls ───────────────────────────────────────────

app.get("/calls/active", async (_req, res) => {
  try {
    const count = await context.getActiveCallCount();
    res.json({ active_calls: count });
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

// ── LiveKit Webhook Handler ────────────────────────────────

app.post("/webhook/livekit", async (req, res) => {
  const reqId = log.requestId();
  const startMs = Date.now();
  metrics.webhooks_received++;

  // Parse and validate the webhook
  const rawBody =
    typeof req.body === "string"
      ? req.body
      : req.body instanceof Buffer
        ? req.body.toString("utf-8")
        : JSON.stringify(req.body);
  const authHeader = req.headers["authorization"] || "";

  const event = await lk.parseWebhook(rawBody, authHeader);
  if (!event) {
    log.warn("Invalid webhook received", { request_id: reqId });
    return res.status(401).json({ error: "invalid webhook signature" });
  }

  const eventType = event.event;
  const room = event.room || {};
  const participant = event.participant || {};

  log.debug("Webhook received", {
    request_id: reqId,
    event: eventType,
    room: room.name,
    participant_identity: participant.identity,
    participant_kind: participant.kind,
  });

  // Only process participant_joined events
  if (eventType !== "participant_joined") {
    return res.json({ status: "ignored", event: eventType });
  }

  // Only dispatch for SIP/phone participants (Twilio-originated calls)
  if (!lk.isSipParticipant(participant)) {
    metrics.dispatches_skipped_non_sip++;
    log.debug("Non-SIP participant, skipping dispatch", {
      request_id: reqId,
      room: room.name,
      identity: participant.identity,
      kind: participant.kind,
    });
    return res.json({ status: "skipped", reason: "not_sip_participant" });
  }

  // Check AI_ENABLED
  if (!config.aiEnabled) {
    metrics.dispatches_skipped_ai_disabled++;
    log.info("AI disabled, skipping agent dispatch", {
      request_id: reqId,
      room: room.name,
    });
    return res.json({ status: "skipped", reason: "ai_disabled" });
  }

  // Extract call metadata
  const callMeta = lk.extractCallMetadata(participant, room);

  log.info("SIP participant detected — dispatching AI agent", {
    request_id: reqId,
    room: room.name,
    call_sid: callMeta.call_sid,
    from: callMeta.from_number,
    participant_kind: participant.kind,
  });

  // Dispatch the voice agent (non-blocking to respond quickly)
  res.json({ status: "dispatching", room: room.name });

  // Perform dispatch + context storage in background
  setImmediate(async () => {
    metrics.dispatches_attempted++;
    try {
      const success = await lk.dispatchAgent(room.name, callMeta);
      if (success) {
        metrics.dispatches_succeeded++;
        // Store call context in Redis for fazle-voice to read
        await context.storeCallContext(room.name, callMeta);
      } else {
        metrics.dispatches_failed++;
      }
    } catch (err) {
      metrics.dispatches_failed++;
      metrics.errors++;
      log.error("Background dispatch error", {
        request_id: reqId,
        room: room.name,
        error: err.message,
      });
    }

    const latencyMs = Date.now() - startMs;
    log.info("Dispatch complete", {
      request_id: reqId,
      room: room.name,
      latency_ms: latencyMs,
    });
  });
});

// ── Test Simulate Endpoint ─────────────────────────────────

app.post("/test/simulate", async (req, res) => {
  if (config.nodeEnv === "production" && !req.query.force) {
    return res.status(403).json({
      error: "Test simulation disabled in production. Use ?force=true to override.",
    });
  }

  const {
    room_name = `test-room-${Date.now()}`,
    from_number = "+1234567890",
    call_sid = `CA_TEST_${Date.now()}`,
  } = req.body || {};

  log.info("Test simulation started", { room_name, from_number, call_sid });

  const meta = {
    call_sid,
    from_number,
    to_number: "+447863767879",
    room_name,
    participant_identity: `sip_${from_number}`,
    relationship: "social",
    dispatched_at: new Date().toISOString(),
  };

  // Store context
  await context.storeCallContext(room_name, meta);

  // Attempt dispatch (will fail if room doesn't exist in LiveKit, which is expected in test)
  const dispatched = await lk.dispatchAgent(room_name, meta);

  // Check provider health
  const [sttStatus, ttsStatus, llmStatus] = await Promise.all([
    stt.getStatus(),
    tts.getStatus(),
    llm.getStatus(),
  ]);

  res.json({
    test: true,
    room_name,
    call_sid,
    dispatch_attempted: true,
    dispatch_success: dispatched,
    context_stored: true,
    providers: {
      stt: sttStatus,
      tts: ttsStatus,
      llm: llmStatus,
    },
    note: dispatched
      ? "Agent dispatched — check LiveKit room for agent participant"
      : "Dispatch failed — room may not exist in LiveKit (expected in pure test mode)",
  });
});

// ── Startup ────────────────────────────────────────────────

function start() {
  validate();

  app.listen(config.port, "0.0.0.0", () => {
    log.info("AI Agent Service started", {
      port: config.port,
      ai_enabled: config.aiEnabled,
      stt_provider: config.stt.provider,
      tts_provider: config.tts.provider,
      llm_provider: config.llm.provider,
      livekit_host: config.livekit.host,
    });
  });
}

// Graceful shutdown
process.on("SIGTERM", async () => {
  log.info("Shutting down...");
  await context.close();
  process.exit(0);
});

process.on("SIGINT", async () => {
  log.info("Shutting down...");
  await context.close();
  process.exit(0);
});

start();
