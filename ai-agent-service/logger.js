// ============================================================
// AI Agent Service — Structured Logger
// JSON logging with request_id, latency, and context fields.
// ============================================================

"use strict";

const crypto = require("crypto");

const LEVELS = { debug: 10, info: 20, warn: 30, error: 40 };
const currentLevel = LEVELS[process.env.LOG_LEVEL || "info"] || LEVELS.info;

function log(level, msg, fields = {}) {
  if (LEVELS[level] < currentLevel) return;
  const entry = {
    ts: new Date().toISOString(),
    level,
    service: "ai-agent-service",
    msg,
    ...fields,
  };
  const line = JSON.stringify(entry);
  if (level === "error" || level === "warn") {
    process.stderr.write(line + "\n");
  } else {
    process.stdout.write(line + "\n");
  }
}

function requestId() {
  return crypto.randomUUID();
}

module.exports = {
  debug: (msg, f) => log("debug", msg, f),
  info: (msg, f) => log("info", msg, f),
  warn: (msg, f) => log("warn", msg, f),
  error: (msg, f) => log("error", msg, f),
  requestId,
};
