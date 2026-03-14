# Zero-Downtime Deployment Guide

## Overview

This system supports zero-downtime rolling deployments for four Fazle AI services:

| Service | Method | Ports | Build Context |
|---------|--------|-------|---------------|
| `fazle-api` | Nginx upstream (blue/green) | 8101 / 8102 | `fazle-system/api` |
| `fazle-brain` | Docker DNS round-robin | internal only | `fazle-system/brain` |
| `fazle-memory` | Docker DNS round-robin | internal only | `fazle-system/memory` |
| `fazle-web-intelligence` | Docker DNS round-robin | internal only | `fazle-system/tools` |

## How It Works

### Nginx Upstream Method (fazle-api)

The API gateway is the only Fazle service exposed to nginx. Rolling deployment uses **blue/green port slots**:

```
                    ┌── port 8101 ── fazle-api-blue
nginx upstream ─────┤
                    └── port 8102 ── fazle-api-green
```

**Deployment flow:**

1. New image is built from updated source
2. Environment variables are extracted from the running container
3. A new container starts in the **inactive slot** (e.g., port 8102)
4. Health check verifies the new container is ready
5. Nginx upstream is updated to include both old and new servers
6. Connections drain from the old container (5s)
7. Old container is stopped and removed
8. Nginx upstream is updated to only the new server

**Zero downtime** is achieved because nginx briefly routes to both containers during the transition. No requests are dropped.

### Docker DNS Method (brain, memory, web-intelligence)

Internal services are reached by other containers via Docker network DNS. Rolling deployment uses **DNS round-robin**:

1. New image is built from updated source
2. A new container starts on the same networks with the **same DNS alias**
3. Docker DNS round-robins requests between old and new containers
4. Health check verifies the new container
5. Old container is stopped (DNS resolves only to the new one)
6. New container is renamed to the original name

---

## Prerequisites

### Nginx Upstream Directory

The nginx config uses an include file for the fazle-api upstream. On the VPS:

```bash
sudo mkdir -p /etc/nginx/upstreams
sudo cp configs/nginx/upstreams/fazle-api.conf /etc/nginx/upstreams/
sudo nginx -t && sudo nginx -s reload
```

### State Directory

The rolling deploy scripts store state in `/var/lib/rolling-deploy/`:

```bash
sudo mkdir -p /var/lib/rolling-deploy
sudo chown azim:azim /var/lib/rolling-deploy
```

---

## Deploying Updates

### Step 1: Dry Run

Always test with `--dry-run` first:

```bash
bash scripts/deploy-rolling.sh fazle-api --dry-run
```

This shows:
- Current deployment state (active slot, running containers)
- What would happen during deployment
- No changes are made

### Step 2: Deploy

```bash
# Deploy a single service
bash scripts/deploy-rolling.sh fazle-api
bash scripts/deploy-rolling.sh fazle-brain
bash scripts/deploy-rolling.sh fazle-memory
bash scripts/deploy-rolling.sh fazle-web-intelligence
```

### Step 3: Verify

```bash
# Check container status
docker ps --filter name=fazle-api

# Check health endpoint
curl -s http://127.0.0.1:8101/health   # or 8102 depending on active slot

# Check logs
docker logs --tail 20 fazle-api-blue   # or fazle-api-green
```

### Deploy Multiple Services

Deploy services in dependency order:

```bash
bash scripts/deploy-rolling.sh fazle-memory
bash scripts/deploy-rolling.sh fazle-brain
bash scripts/deploy-rolling.sh fazle-web-intelligence
bash scripts/deploy-rolling.sh fazle-api
```

**Order rationale:** Memory and brain are upstream dependencies of the API. Update them first so the API picks up any interface changes when it restarts.

---

## Rolling Back

If a deployment causes issues, roll back to the previous image:

```bash
# Dry run first
bash scripts/rollback-rolling.sh fazle-api --dry-run

# Execute rollback
bash scripts/rollback-rolling.sh fazle-api
```

The rollback script:
1. Starts a new container with the **previous image** (`rolling-previous` tag)
2. Waits for health check
3. Switches traffic (nginx or DNS)
4. Stops the current container

**Rollback images are preserved** automatically. Each deploy tags the current image as `rolling-previous` before building the new one.

---

## Architecture Details

### Nginx Configuration

The upstream block in `fazle.iamazim.com.conf`:

```nginx
upstream fazle_api_cluster {
    include /etc/nginx/upstreams/fazle-api.conf;
    keepalive 16;
}
```

The include file is managed by `deploy-rolling.sh`:

```nginx
# During steady state (one active slot):
server 127.0.0.1:8101;

# During transition (both active):
server 127.0.0.1:8101;
server 127.0.0.1:8102;
```

### Compose File Relationship

The compose files define the **steady-state** configuration (single instance per service). The rolling deploy scripts manage instances **outside of compose** using `docker run`.

After a rolling deploy for `fazle-api`:
- The compose-defined container (`fazle-api` on port 8100) is replaced
- The active container is `fazle-api-blue` (port 8101) or `fazle-api-green` (port 8102)
- Running `docker compose up` in `fazle-ai/` would recreate the single-instance setup

For DNS-based services, the container is renamed back to the original name, so compose compatibility is preserved.

### State Files

Rolling deploy state is stored in `/var/lib/rolling-deploy/`:

| File | Purpose |
|------|---------|
| `<service>.slot` | Active slot (blue/green/none) |
| `<service>.rollback-image` | Image ID of previous deployment |
| `<service>.rollback-container` | Container name of previous deployment |

### Image Tags

| Tag | Purpose |
|-----|---------|
| `<service>:rolling-<timestamp>` | Unique tag per deployment |
| `<service>:rolling-latest` | Currently deployed image |
| `<service>:rolling-previous` | Previous image (rollback target) |

---

## Transition: Compose → Rolling Deploy

The first rolling deploy migrates a service from compose-managed to rolling-managed:

1. The compose container (`fazle-api` on port 8100) is running
2. `deploy-rolling.sh fazle-api` starts `fazle-api-blue` on port 8101
3. Nginx upstream switches from port 8100 to 8101
4. The compose container is stopped

After this transition:
- Use `deploy-rolling.sh` for subsequent deployments
- The compose file remains valid for fresh deployments or disaster recovery
- The nginx upstream include file must point to the correct port

### Reverting to Compose Management

To return fazle-api to compose-managed mode:

```bash
# Stop rolling containers
docker rm -f fazle-api-blue fazle-api-green 2>/dev/null

# Reset nginx upstream to port 8100
echo "server 127.0.0.1:8100;" > /etc/nginx/upstreams/fazle-api.conf
sudo nginx -s reload

# Restart via compose
cd fazle-ai
docker compose --env-file ../.env up -d fazle-api

# Clear rolling state
rm -f /var/lib/rolling-deploy/fazle-api.*
```

---

## Troubleshooting

### Health Check Failure

If the new container fails its health check, the deploy script automatically cleans it up. No traffic is affected.

```bash
# Check build logs
docker build fazle-system/api 2>&1 | tail -30

# Check container logs
docker logs fazle-api-blue 2>&1 | tail -30

# Test health endpoint manually
docker run --rm --network app-network fazle-api:rolling-latest \
    python -c "import urllib.request; print(urllib.request.urlopen('http://localhost:8100/health').read())"
```

### Nginx Upstream Errors

```bash
# Verify upstream config
cat /etc/nginx/upstreams/fazle-api.conf

# Test nginx config
sudo nginx -t

# Check which ports are listening
ss -tlnp | grep -E '810[012]'
```

### Port Conflicts

```bash
# Check what's using the rolling ports
ss -tlnp | grep -E '8101|8102'

# Kill stale containers on those ports
docker rm -f fazle-api-blue fazle-api-green 2>/dev/null
```

### State Corruption

```bash
# Reset rolling state
rm -f /var/lib/rolling-deploy/fazle-api.*

# Verify and clean up containers
docker ps -a --filter name=fazle-api
docker rm -f fazle-api-blue fazle-api-green 2>/dev/null

# Restore compose mode
echo "server 127.0.0.1:8100;" > /etc/nginx/upstreams/fazle-api.conf
sudo nginx -s reload
cd fazle-ai && docker compose --env-file ../.env up -d fazle-api
```

---

## Services NOT Covered

The following services are **not** part of rolling deployment:

| Service | Reason |
|---------|--------|
| `fazle-task-engine` | Background scheduler — brief restart is acceptable |
| `fazle-trainer` | Batch training — not user-facing |
| `fazle-voice` | LiveKit agent — handles reconnection internally |
| `fazle-ui` | Frontend — served via CDN/cache, not latency-critical |
| All Dograh services | Pre-built images, separate release cycle |
| All infra services | Stateful (postgres, redis, etc.) — requires different strategy |

To add rolling deploy support for additional services, add a configuration entry to the `get_config()` function in both `deploy-rolling.sh` and `rollback-rolling.sh`.
