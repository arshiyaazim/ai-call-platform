// ============================================================
// AI Agent Service — Test Mode
// Simulates a Twilio call without needing actual Twilio.
// Tests the dispatch pipeline and provider health.
//
// Usage: node test-mode.js [--room <name>] [--from <number>]
// ============================================================

"use strict";

const { config, validate } = require("./config");
const lk = require("./livekit-client");
const context = require("./context");
const stt = require("./stt");
const tts = require("./tts");
const llm = require("./llm");

// ── Helpers ────────────────────────────────────────────────

function log(msg) {
  const ts = new Date().toISOString().slice(11, 23);
  process.stdout.write(`[${ts}] ${msg}\n`);
}

function parseArgs() {
  const args = process.argv.slice(2);
  const opts = {
    room: `test-room-${Date.now()}`,
    from: "+1234567890",
    callSid: `CA_TEST_${Date.now()}`,
  };
  for (let i = 0; i < args.length; i++) {
    if (args[i] === "--room" && args[i + 1]) opts.room = args[++i];
    if (args[i] === "--from" && args[i + 1]) opts.from = args[++i];
    if (args[i] === "--call-sid" && args[i + 1]) opts.callSid = args[++i];
  }
  return opts;
}

// ── Test Steps ─────────────────────────────────────────────

async function testProviders() {
  log("─── Provider Health Checks ───────────────────────");
  const [s, t, l] = await Promise.all([
    stt.getStatus(),
    tts.getStatus(),
    llm.getStatus(),
  ]);
  log(`  STT: ${s.name} → ${s.health.status}`);
  log(`  TTS: ${t.name} → ${t.health.status}`);
  log(`  LLM: ${l.name} → ${l.health.status}`);
  return { stt: s, tts: t, llm: l };
}

async function testRedisContext(roomName, callSid, from) {
  log("─── Redis Context ────────────────────────────────");
  const meta = {
    call_sid: callSid,
    from_number: from,
    to_number: "+447863767879",
    room_name: roomName,
    relationship: "social",
    dispatched_at: new Date().toISOString(),
  };

  await context.storeCallContext(roomName, meta);
  const stored = await context.getCallContext(roomName);
  if (stored) {
    log(`  Context stored: call_sid=${stored.call_sid}, from=${stored.from_number}`);
    log(`  Transcript entries: ${stored.transcript.length}`);
  } else {
    log("  ⚠ Context NOT stored (Redis may be unavailable)");
  }
  return stored;
}

async function testDispatch(roomName, meta) {
  log("─── Agent Dispatch ───────────────────────────────");
  log(`  Room: ${roomName}`);
  log(`  AI Enabled: ${config.aiEnabled}`);

  if (!config.aiEnabled) {
    log("  ⚠ AI_ENABLED=false — dispatch skipped");
    return false;
  }

  const hasAgent = await lk.hasAgentInRoom(roomName);
  log(`  Agent already in room: ${hasAgent}`);

  if (hasAgent) {
    log("  ⚠ Agent already present — dispatch skipped");
    return true;
  }

  log("  Dispatching fazle-voice agent...");
  const startMs = Date.now();
  const success = await lk.dispatchAgent(roomName, meta);
  const ms = Date.now() - startMs;

  if (success) {
    log(`  ✓ Agent dispatched (${ms}ms)`);
  } else {
    log(`  ✗ Dispatch failed (${ms}ms) — room may not exist in LiveKit`);
    log("    This is EXPECTED in pure test mode without an active LiveKit room.");
  }
  return success;
}

async function testWebhookSimulation(roomName, from) {
  log("─── Webhook Simulation ───────────────────────────");
  log("  Simulating LiveKit participant_joined event...");

  const fakeParticipant = {
    sid: "PA_TEST_001",
    identity: `sip_${from}`,
    name: from,
    kind: 3, // SIP
    metadata: JSON.stringify({ call_sid: `CA_SIM_${Date.now()}` }),
  };

  const isSip = lk.isSipParticipant(fakeParticipant);
  log(`  Is SIP participant: ${isSip}`);

  const callMeta = lk.extractCallMetadata(fakeParticipant, {
    name: roomName,
    sid: "RM_TEST_001",
  });
  log(`  Extracted: call_sid=${callMeta.call_sid}, from=${callMeta.from_number}`);
  return callMeta;
}

// ── Main ───────────────────────────────────────────────────

async function main() {
  log("═══ AI Agent Service — Test Mode ═══════════════════");
  log("");

  try {
    validate();
    log(`LiveKit: ${config.livekit.host}`);
    log(`Redis:   ${config.redis.url}`);
    log("");
  } catch (err) {
    log(`Config error: ${err.message}`);
    log("Set LIVEKIT_API_KEY and LIVEKIT_API_SECRET to run tests.");
    process.exit(1);
  }

  const opts = parseArgs();
  log(`Test params: room=${opts.room}, from=${opts.from}`);
  log("");

  // 1. Provider health
  await testProviders();
  log("");

  // 2. Redis context
  const stored = await testRedisContext(opts.room, opts.callSid, opts.from);
  log("");

  // 3. Webhook simulation
  const callMeta = await testWebhookSimulation(opts.room, opts.from);
  log("");

  // 4. Agent dispatch
  await testDispatch(opts.room, callMeta);
  log("");

  log("═══ Test Complete ══════════════════════════════════");
  log("To test with real audio, create a LiveKit room and");
  log("call the /test/simulate endpoint on the running service.");

  await context.close();
  process.exit(0);
}

main().catch((err) => {
  console.error("Test failed:", err);
  process.exit(1);
});
