#!/usr/bin/env python3
"""
Auto Repair Engine — Executes whitelisted repair actions safely.
All repairs are rate-limited and logged. Volumes are never deleted.
"""

import logging
from datetime import datetime, timedelta

import docker

log = logging.getLogger("control-plane.repair")

client = docker.from_env()

# Track repairs to enforce rate limits
_repair_history: list[dict] = []
_restart_counts: dict[str, list[datetime]] = {}


def execute_repairs(actions: list[dict], config: dict) -> list[dict]:
    """Execute a list of recommended actions. Returns results."""
    allowed = set(config.get("allowed_actions", []))
    protected = set(config.get("protected_containers", []))
    max_per_hour = config.get("max_repairs_per_hour", 5)
    max_restarts = config.get("max_restarts_per_container_per_hour", 2)

    # Check global rate limit
    now = datetime.now()
    cutoff = now - timedelta(hours=1)
    recent_repairs = [r for r in _repair_history if r["time"] > cutoff]
    if len(recent_repairs) >= max_per_hour:
        log.warning("Global repair limit reached (%d/%d per hour) — skipping", len(recent_repairs), max_per_hour)
        return [{"action": "rate_limited", "success": False, "reason": "global limit reached"}]

    results = []
    for action_spec in actions:
        action = action_spec.get("action", "")
        target = action_spec.get("target", "")
        reason = action_spec.get("reason", "")

        if action not in allowed:
            log.warning("Action '%s' not in whitelist — SKIPPING", action)
            results.append({"action": action, "target": target, "success": False, "reason": "not whitelisted"})
            continue

        log.info("Executing: %s on %s (reason: %s)", action, target, reason)

        try:
            if action == "restart_container":
                result = _restart_container(target, protected, max_restarts)
            elif action == "rebuild_service":
                result = _rebuild_service(target, protected)
            elif action == "redeploy_service":
                result = _redeploy_service(target, protected)
            elif action == "scale_workers":
                result = _scale_workers(target, config)
            elif action == "clean_docker":
                result = _clean_docker()
            else:
                result = {"success": False, "reason": f"unknown action: {action}"}

            result["action"] = action
            result["target"] = target
            results.append(result)

            if result.get("success"):
                _repair_history.append({"action": action, "target": target, "time": now})

        except Exception as e:
            log.error("Repair failed: %s on %s: %s", action, target, e)
            results.append({"action": action, "target": target, "success": False, "reason": str(e)})

    return results


def _restart_container(name: str, protected: set, max_restarts: int) -> dict:
    """Restart a container with rate limiting."""
    now = datetime.now()
    cutoff = now - timedelta(hours=1)

    # Check per-container rate limit
    history = _restart_counts.get(name, [])
    history = [t for t in history if t > cutoff]
    _restart_counts[name] = history

    if len(history) >= max_restarts:
        log.warning("Container %s hit restart limit (%d/%d) — SKIPPING", name, len(history), max_restarts)
        return {"success": False, "reason": f"restart limit ({len(history)}/{max_restarts})"}

    try:
        container = client.containers.get(name)
        container.restart(timeout=30)
        _restart_counts.setdefault(name, []).append(now)
        log.info("Restarted container %s successfully", name)
        return {"success": True, "reason": "restarted"}
    except docker.errors.NotFound:
        log.error("Container %s not found", name)
        return {"success": False, "reason": "container not found"}
    except docker.errors.APIError as e:
        log.error("API error restarting %s: %s", name, e)
        return {"success": False, "reason": str(e)}


def _rebuild_service(name: str, protected: set) -> dict:
    """Rebuild a service image. Uses Docker SDK to pull/rebuild."""
    # For safety, only log the recommendation — rebuilds need compose context
    log.warning("REBUILD recommended for %s — logging for human review (requires compose context)", name)
    return {"success": True, "reason": "rebuild flagged for review"}


def _redeploy_service(name: str, protected: set) -> dict:
    """Redeploy a container by restarting it."""
    try:
        container = client.containers.get(name)
        if container.status != "running":
            container.start()
            log.info("Started stopped container %s", name)
        else:
            container.restart(timeout=30)
            log.info("Redeployed container %s", name)
        return {"success": True, "reason": "redeployed"}
    except docker.errors.NotFound:
        return {"success": False, "reason": "container not found"}
    except Exception as e:
        return {"success": False, "reason": str(e)}


def _scale_workers(target_str: str, config: dict) -> dict:
    """Scale fazle-workers. Target should be a number."""
    try:
        target = int(target_str)
    except (ValueError, TypeError):
        # Try extracting a number from target string
        workers_max = config.get("workers_max", 4)
        workers_min = config.get("workers_min", 2)
        target = workers_max

    workers_min = config.get("workers_min", 2)
    workers_max = config.get("workers_max", 4)
    target = max(workers_min, min(workers_max, target))

    current_workers = client.containers.list(filters={"name": "fazle-workers", "status": "running"})
    current = len(current_workers)

    if target == current:
        return {"success": True, "reason": f"already at {current} workers"}

    if target > current:
        # Scale up by cloning from existing worker
        existing = [c for c in current_workers if c.status == "running"]
        if not existing:
            return {"success": False, "reason": "no running workers to clone"}

        template = existing[0]
        image = template.image
        net_names = list(template.attrs.get("NetworkSettings", {}).get("Networks", {}).keys())
        env = template.attrs.get("Config", {}).get("Env", [])

        for i in range(current + 1, target + 1):
            name = f"fazle-workers-{i}"
            try:
                old = client.containers.get(name)
                if old.status != "running":
                    old.start()
                continue
            except docker.errors.NotFound:
                pass
            c = client.containers.run(
                image, detach=True, name=name, environment=env,
                network=net_names[0] if net_names else None,
                restart_policy={"Name": "unless-stopped"},
                labels={"com.docker.compose.project": "fazle-ai", "controlplane.managed": "true"},
            )
            for net in net_names[1:]:
                try:
                    client.networks.get(net).connect(c)
                except Exception:
                    pass
            log.info("Created worker %s", name)

    elif target < current:
        managed = client.containers.list(filters={"label": "controlplane.managed=true", "name": "fazle-workers"})
        to_remove = sorted(managed, key=lambda c: c.name, reverse=True)
        removed = 0
        for c in to_remove:
            if current - removed <= target:
                break
            c.stop(timeout=30)
            c.remove()
            removed += 1
            log.info("Removed worker %s", c.name)

    return {"success": True, "reason": f"scaled to {target} workers"}


def _clean_docker() -> dict:
    """Prune unused images and stopped containers. Never delete volumes."""
    try:
        cr = client.containers.prune()
        ir = client.images.prune(filters={"dangling": True})
        deleted_containers = len(cr.get("ContainersDeleted") or [])
        deleted_images = len(ir.get("ImagesDeleted") or [])
        reclaimed = ir.get("SpaceReclaimed", 0)
        log.info("Cleaned: %d containers, %d images, %.1f MB reclaimed",
                 deleted_containers, deleted_images, reclaimed / (1024 * 1024))
        return {"success": True, "reason": f"cleaned {deleted_containers}c/{deleted_images}i, {reclaimed / (1024*1024):.0f}MB"}
    except Exception as e:
        return {"success": False, "reason": str(e)}
