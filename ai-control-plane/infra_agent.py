#!/usr/bin/env python3
"""
Infrastructure Agent — Main control loop.
Runs every 60s: collect snapshot → AI analysis → auto-repair → log.
Generates daily infrastructure reports.
"""

import os
import sys
import json
import time
import signal
import logging
from datetime import datetime, date
from pathlib import Path

import yaml

import ai_devops_brain as brain
import system_analyzer as analyzer
import auto_repair_engine as repair_engine

# ── Logging ──────────────────────────────────────────────────

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    stream=sys.stdout,
)
log = logging.getLogger("control-plane")

# ── Config ───────────────────────────────────────────────────

CONFIG_PATH = os.getenv("CONFIG_PATH", "/app/config.yaml")


def load_config() -> dict:
    with open(CONFIG_PATH, "r") as f:
        return yaml.safe_load(f)


# ── Report ───────────────────────────────────────────────────

class DailyReport:
    """Accumulates events for a daily infrastructure report."""

    def __init__(self, report_dir: str):
        self.report_dir = Path(report_dir)
        self.report_dir.mkdir(parents=True, exist_ok=True)
        self.today = date.today()
        self.events: list[dict] = []
        self.repairs: list[dict] = []
        self.snapshots_count = 0

    def add_cycle(self, snapshot: dict, analysis: dict, repair_results: list[dict]):
        self.snapshots_count += 1
        if analysis.get("status") != "ok":
            self.events.append({
                "time": datetime.utcnow().isoformat(),
                "status": analysis.get("status"),
                "root_cause": analysis.get("root_cause"),
                "actions_recommended": len(analysis.get("recommended_actions", [])),
            })
        for r in repair_results:
            if r.get("action") != "rate_limited":
                self.repairs.append({
                    "time": datetime.utcnow().isoformat(),
                    "action": r.get("action"),
                    "target": r.get("target"),
                    "success": r.get("success"),
                    "reason": r.get("reason"),
                })

        # Check if day rolled over
        if date.today() != self.today:
            self.flush()
            self.today = date.today()
            self.events = []
            self.repairs = []
            self.snapshots_count = 0

        # Flush after every cycle to protect against crashes
        self.flush()

    def flush(self):
        """Write daily report to file."""
        report = {
            "date": self.today.isoformat(),
            "generated_at": datetime.utcnow().isoformat(),
            "total_cycles": self.snapshots_count,
            "events_detected": len(self.events),
            "repairs_executed": len(self.repairs),
            "events": self.events,
            "repairs": self.repairs,
        }
        path = self.report_dir / f"report-{self.today.isoformat()}.json"
        with open(path, "w") as f:
            json.dump(report, f, indent=2, default=str)
        log.info("Daily report written: %s", path)

        # Rotate: keep last 30 days
        reports = sorted(self.report_dir.glob("report-*.json"))
        while len(reports) > 30:
            old = reports.pop(0)
            old.unlink()
            log.info("Rotated old report: %s", old.name)


# ── Graceful Shutdown ────────────────────────────────────────

shutdown = False


def handle_signal(signum, _frame):
    global shutdown
    log.info("Received signal %d — shutting down gracefully...", signum)
    shutdown = True


signal.signal(signal.SIGTERM, handle_signal)
signal.signal(signal.SIGINT, handle_signal)


# ── Main Loop ────────────────────────────────────────────────

def main():
    config = load_config()
    interval = config.get("check_interval", 60)

    ollama_url = os.getenv("OLLAMA_URL", "http://ollama:11434")
    model = config.get("ollama_model", "qwen2.5:3b")
    brain.init(ollama_url, model)

    report_dir = config.get("report_dir", "/var/log/ai-infra-reports")
    daily_report = DailyReport(report_dir)

    log.info("=" * 60)
    log.info("  AI CONTROL PLANE — Level-5 Autonomous Infrastructure")
    log.info("  Check interval: %ds", interval)
    log.info("  Ollama model: %s", model)
    log.info("  Monitored containers: %d", len(config.get("monitored_containers", [])))
    log.info("=" * 60)

    cycle = 0
    while not shutdown:
        cycle += 1
        log.info("━━━ Control Plane Cycle #%d ━━━", cycle)
        start = time.time()

        # Step 1: Collect system snapshot
        try:
            snapshot = analyzer.collect_snapshot(config)
            log.info("Snapshot collected: %d containers, disk %d%%, queue len %d",
                     len(snapshot.get("containers", [])),
                     snapshot.get("disk", {}).get("usage_percent", 0),
                     snapshot.get("queue", {}).get("length", 0))
        except Exception as e:
            log.error("Snapshot collection failed: %s", e)
            _sleep(interval, start)
            continue

        # Step 2a: Deterministic pre-screening — catch obvious failures instantly
        deterministic_actions = _deterministic_checks(snapshot, config)
        if deterministic_actions:
            log.info("Deterministic checks found %d issues", len(deterministic_actions))

        # Step 2b: AI analysis for complex diagnostics
        try:
            ai_snapshot = _trim_snapshot(snapshot)
            if ai_snapshot.get("problem_containers"):
                log.info("Sending %d problem containers to AI: %s",
                         len(ai_snapshot["problem_containers"]),
                         [c["name"] for c in ai_snapshot["problem_containers"]])
            analysis = brain.analyze(ai_snapshot)
            log.info("AI Analysis: status=%s, root_cause=%s, actions=%d",
                     analysis.get("status", "unknown"),
                     analysis.get("root_cause", "none"),
                     len(analysis.get("recommended_actions", [])))
        except Exception as e:
            log.error("AI analysis failed: %s", e)
            analysis = {"status": "ok", "root_cause": None, "recommended_actions": []}

        # Merge deterministic + AI actions (deterministic take priority)
        ai_actions = analysis.get("recommended_actions", [])
        det_targets = {a["target"] for a in deterministic_actions}
        for a in ai_actions:
            if a.get("target") not in det_targets:
                deterministic_actions.append(a)
        analysis["recommended_actions"] = deterministic_actions

        # Step 3: Execute repairs if needed
        repair_results = []
        actions = analysis.get("recommended_actions", [])
        if actions:
            log.info("Executing %d recommended actions...", len(actions))
            try:
                repair_results = repair_engine.execute_repairs(actions, config)
                for r in repair_results:
                    log.info("  Repair: %s on %s → %s (%s)",
                             r.get("action"), r.get("target"),
                             "SUCCESS" if r.get("success") else "FAILED",
                             r.get("reason"))
            except Exception as e:
                log.error("Repair execution failed: %s", e)
        else:
            log.info("No repairs needed — system healthy")

        # Step 4: Update daily report
        try:
            daily_report.add_cycle(snapshot, analysis, repair_results)
        except Exception as e:
            log.error("Report update failed: %s", e)

        elapsed = time.time() - start
        log.info("Cycle #%d complete in %.1fs", cycle, elapsed)

        _sleep(interval, start)

    # Flush report on shutdown
    log.info("Shutting down — flushing final report...")
    daily_report.flush()
    log.info("AI Control Plane stopped.")


def _trim_snapshot(snapshot: dict) -> dict:
    """Trim snapshot for AI prompt to avoid token overflow."""
    trimmed = {}
    # Only include containers with problems — omit healthy ones entirely
    problem_containers = []
    healthy_count = 0
    for c in snapshot.get("containers", []):
        if c.get("status") != "running" or c.get("health") == "unhealthy":
            problem_containers.append(c)
        else:
            healthy_count += 1
    trimmed["healthy_containers"] = healthy_count
    trimmed["problem_containers"] = problem_containers
    trimmed["disk"] = snapshot.get("disk", {})
    trimmed["system"] = snapshot.get("system", {})
    trimmed["queue"] = snapshot.get("queue", {})
    # Only include prometheus anomalies
    prom = snapshot.get("prometheus", {})
    if prom.get("high_cpu_containers"):
        trimmed["high_cpu"] = prom["high_cpu_containers"]
    return trimmed


def _deterministic_checks(snapshot: dict, config: dict) -> list:
    """Catch obvious failures that don't need AI reasoning."""
    actions = []
    protected = set(config.get("protected_containers", []))

    # Check for stopped/exited containers (not protected)
    for c in snapshot.get("containers", []):
        name = c.get("name", "")
        status = c.get("status", "")
        if status in ("exited", "dead", "created") and name not in protected:
            actions.append({
                "action": "restart_container",
                "target": name,
                "reason": f"Container {name} is {status} — auto-restart",
            })
            log.warning("Deterministic: %s is %s — scheduling restart", name, status)

    # Check for unhealthy containers (not protected)
    for c in snapshot.get("containers", []):
        name = c.get("name", "")
        health = c.get("health", "")
        status = c.get("status", "")
        if status == "running" and health == "unhealthy" and name not in protected:
            actions.append({
                "action": "restart_container",
                "target": name,
                "reason": f"Container {name} is unhealthy — auto-restart",
            })
            log.warning("Deterministic: %s unhealthy — scheduling restart", name)

    # Check disk critical threshold
    disk_pct = snapshot.get("disk", {}).get("usage_percent", 0)
    disk_critical = config.get("thresholds", {}).get("disk_critical_percent", 85)
    if disk_pct >= disk_critical:
        actions.append({
            "action": "clean_docker",
            "target": "system",
            "reason": f"Disk usage {disk_pct}% >= critical threshold {disk_critical}%",
        })
        log.warning("Deterministic: disk critical %d%% — scheduling cleanup", disk_pct)

    return actions


def _sleep(interval: float, start: float):
    """Sleep remaining interval time."""
    elapsed = time.time() - start
    remaining = max(0, interval - elapsed)
    if remaining > 0 and not shutdown:
        time.sleep(remaining)


if __name__ == "__main__":
    main()
