#!/usr/bin/env python3
"""Comprehensive Phase-5 patcher for VPS deployment.

Patches:
  1. API Settings class — adds Phase-5 service URLs
  2. API routes — appends Phase-5 proxy endpoints
  3. Brain Settings class — adds Phase-5 service URLs
  4. Docker-compose is handled separately via SCP
"""
import sys
import os
import re

BASE = '/home/azim/ai-call-platform'

PHASE5_SETTINGS_BLOCK = """\
    # Phase-5 Autonomous AI services
    autonomy_engine_url: str = 'http://fazle-autonomy-engine:9100'
    tool_engine_url: str = 'http://fazle-tool-engine:9200'
    knowledge_graph_url: str = 'http://fazle-knowledge-graph:9300'
    autonomous_runner_url: str = 'http://fazle-autonomous-runner:9400'
    self_learning_url: str = 'http://fazle-self-learning:9500'
"""

PHASE5_API_ROUTES = '''

# ── Phase-5: Autonomy Engine proxy ──────────────────────────

@app.post("/fazle/autonomy/plan", dependencies=[Depends(verify_auth)])
async def autonomy_plan(body: dict):
    async with httpx.AsyncClient(timeout=60.0) as client:
        try:
            resp = await client.post(f"{settings.autonomy_engine_url}/autonomy/plan", json=body)
            resp.raise_for_status()
            return resp.json()
        except httpx.HTTPError as e:
            logger.error(f"Autonomy engine error: {e}")
            raise HTTPException(status_code=502, detail="Autonomy engine unavailable")


@app.post("/fazle/autonomy/execute", dependencies=[Depends(verify_auth)])
async def autonomy_execute(body: dict):
    async with httpx.AsyncClient(timeout=60.0) as client:
        try:
            resp = await client.post(f"{settings.autonomy_engine_url}/autonomy/execute", json=body)
            resp.raise_for_status()
            return resp.json()
        except httpx.HTTPError as e:
            logger.error(f"Autonomy execute error: {e}")
            raise HTTPException(status_code=502, detail="Autonomy engine unavailable")


@app.get("/fazle/autonomy/plans", dependencies=[Depends(verify_auth)])
async def autonomy_plans(limit: int = 20):
    async with httpx.AsyncClient(timeout=15.0) as client:
        try:
            resp = await client.get(f"{settings.autonomy_engine_url}/autonomy/plans", params={"limit": limit})
            resp.raise_for_status()
            return resp.json()
        except httpx.HTTPError as e:
            logger.error(f"Autonomy list error: {e}")
            raise HTTPException(status_code=502, detail="Autonomy engine unavailable")


@app.get("/fazle/autonomy/plan/{plan_id}", dependencies=[Depends(verify_auth)])
async def autonomy_plan_detail(plan_id: str):
    async with httpx.AsyncClient(timeout=15.0) as client:
        try:
            resp = await client.get(f"{settings.autonomy_engine_url}/autonomy/plan/{plan_id}")
            resp.raise_for_status()
            return resp.json()
        except httpx.HTTPError as e:
            logger.error(f"Autonomy plan detail error: {e}")
            raise HTTPException(status_code=502, detail="Autonomy engine unavailable")


# ── Phase-5: Tool Engine proxy ──────────────────────────────

@app.get("/fazle/tool-engine/list", dependencies=[Depends(verify_auth)])
async def tool_engine_list():
    async with httpx.AsyncClient(timeout=15.0) as client:
        try:
            resp = await client.get(f"{settings.tool_engine_url}/tools/list")
            resp.raise_for_status()
            return resp.json()
        except httpx.HTTPError as e:
            logger.error(f"Tool engine list error: {e}")
            raise HTTPException(status_code=502, detail="Tool engine unavailable")


@app.post("/fazle/tool-engine/execute", dependencies=[Depends(verify_auth)])
async def tool_engine_execute(body: dict):
    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            resp = await client.post(f"{settings.tool_engine_url}/tools/execute", json=body)
            resp.raise_for_status()
            return resp.json()
        except httpx.HTTPError as e:
            logger.error(f"Tool engine execute error: {e}")
            raise HTTPException(status_code=502, detail="Tool engine unavailable")


@app.put("/fazle/tool-engine/{tool_name}/toggle", dependencies=[Depends(verify_auth)])
async def tool_engine_toggle(tool_name: str):
    async with httpx.AsyncClient(timeout=10.0) as client:
        try:
            resp = await client.put(f"{settings.tool_engine_url}/tools/{tool_name}/toggle")
            resp.raise_for_status()
            return resp.json()
        except httpx.HTTPError as e:
            logger.error(f"Tool engine toggle error: {e}")
            raise HTTPException(status_code=502, detail="Tool engine unavailable")


# ── Phase-5: Knowledge Graph proxy ──────────────────────────

@app.post("/fazle/knowledge-graph/query", dependencies=[Depends(verify_auth)])
async def kg_query(body: dict):
    async with httpx.AsyncClient(timeout=15.0) as client:
        try:
            resp = await client.post(f"{settings.knowledge_graph_url}/graph/query", json=body)
            resp.raise_for_status()
            return resp.json()
        except httpx.HTTPError as e:
            logger.error(f"Knowledge graph query error: {e}")
            raise HTTPException(status_code=502, detail="Knowledge graph unavailable")


@app.get("/fazle/knowledge-graph/stats", dependencies=[Depends(verify_auth)])
async def kg_stats():
    async with httpx.AsyncClient(timeout=10.0) as client:
        try:
            resp = await client.get(f"{settings.knowledge_graph_url}/graph/stats")
            resp.raise_for_status()
            return resp.json()
        except httpx.HTTPError as e:
            logger.error(f"Knowledge graph stats error: {e}")
            raise HTTPException(status_code=502, detail="Knowledge graph unavailable")


@app.get("/fazle/knowledge-graph/nodes", dependencies=[Depends(verify_auth)])
async def kg_nodes(node_type: str = None, limit: int = 50):
    async with httpx.AsyncClient(timeout=10.0) as client:
        try:
            params = {"limit": limit}
            if node_type:
                params["node_type"] = node_type
            resp = await client.get(f"{settings.knowledge_graph_url}/graph/nodes", params=params)
            resp.raise_for_status()
            return resp.json()
        except httpx.HTTPError as e:
            logger.error(f"Knowledge graph nodes error: {e}")
            raise HTTPException(status_code=502, detail="Knowledge graph unavailable")


@app.get("/fazle/knowledge-graph/context/{node_id}", dependencies=[Depends(verify_auth)])
async def kg_context(node_id: str, depth: int = 2):
    async with httpx.AsyncClient(timeout=10.0) as client:
        try:
            resp = await client.get(f"{settings.knowledge_graph_url}/graph/context/{node_id}", params={"depth": depth})
            resp.raise_for_status()
            return resp.json()
        except httpx.HTTPError as e:
            logger.error(f"Knowledge graph context error: {e}")
            raise HTTPException(status_code=502, detail="Knowledge graph unavailable")


# ── Phase-5: Autonomous Task Runner proxy ───────────────────

@app.post("/fazle/autonomous-tasks", dependencies=[Depends(verify_auth)])
async def create_autonomous_task(body: dict):
    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            resp = await client.post(f"{settings.autonomous_runner_url}/tasks/autonomous", json=body)
            resp.raise_for_status()
            return resp.json()
        except httpx.HTTPError as e:
            logger.error(f"Autonomous runner error: {e}")
            raise HTTPException(status_code=502, detail="Autonomous runner unavailable")


@app.get("/fazle/autonomous-tasks", dependencies=[Depends(verify_auth)])
async def list_autonomous_tasks(status: str = None, limit: int = 50):
    async with httpx.AsyncClient(timeout=15.0) as client:
        try:
            params = {"limit": limit}
            if status:
                params["status"] = status
            resp = await client.get(f"{settings.autonomous_runner_url}/tasks/autonomous", params=params)
            resp.raise_for_status()
            return resp.json()
        except httpx.HTTPError as e:
            logger.error(f"Autonomous runner list error: {e}")
            raise HTTPException(status_code=502, detail="Autonomous runner unavailable")


@app.post("/fazle/autonomous-tasks/{task_id}/run", dependencies=[Depends(verify_auth)])
async def run_autonomous_task(task_id: str):
    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            resp = await client.post(f"{settings.autonomous_runner_url}/tasks/autonomous/{task_id}/run")
            resp.raise_for_status()
            return resp.json()
        except httpx.HTTPError as e:
            logger.error(f"Autonomous runner run error: {e}")
            raise HTTPException(status_code=502, detail="Autonomous runner unavailable")


@app.post("/fazle/autonomous-tasks/{task_id}/pause", dependencies=[Depends(verify_auth)])
async def pause_autonomous_task(task_id: str):
    async with httpx.AsyncClient(timeout=10.0) as client:
        try:
            resp = await client.post(f"{settings.autonomous_runner_url}/tasks/autonomous/{task_id}/pause")
            resp.raise_for_status()
            return resp.json()
        except httpx.HTTPError as e:
            logger.error(f"Autonomous runner pause error: {e}")
            raise HTTPException(status_code=502, detail="Autonomous runner unavailable")


@app.get("/fazle/autonomous-tasks/history", dependencies=[Depends(verify_auth)])
async def autonomous_task_history(task_id: str = None, limit: int = 50):
    async with httpx.AsyncClient(timeout=10.0) as client:
        try:
            params = {"limit": limit}
            if task_id:
                params["task_id"] = task_id
            resp = await client.get(f"{settings.autonomous_runner_url}/tasks/autonomous/history", params=params)
            resp.raise_for_status()
            return resp.json()
        except httpx.HTTPError as e:
            logger.error(f"Autonomous runner history error: {e}")
            raise HTTPException(status_code=502, detail="Autonomous runner unavailable")


# ── Phase-5: Self-Learning Engine proxy ─────────────────────

@app.post("/fazle/self-learning/analyze", dependencies=[Depends(verify_auth)])
async def self_learning_analyze(body: dict = None):
    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            resp = await client.post(f"{settings.self_learning_url}/learning/analyze", json=body or {})
            resp.raise_for_status()
            return resp.json()
        except httpx.HTTPError as e:
            logger.error(f"Self-learning analyze error: {e}")
            raise HTTPException(status_code=502, detail="Self-learning engine unavailable")


@app.post("/fazle/self-learning/improve", dependencies=[Depends(verify_auth)])
async def self_learning_improve(body: dict = None):
    async with httpx.AsyncClient(timeout=20.0) as client:
        try:
            resp = await client.post(f"{settings.self_learning_url}/learning/improve", json=body or {})
            resp.raise_for_status()
            return resp.json()
        except httpx.HTTPError as e:
            logger.error(f"Self-learning improve error: {e}")
            raise HTTPException(status_code=502, detail="Self-learning engine unavailable")


@app.get("/fazle/self-learning/insights", dependencies=[Depends(verify_auth)])
async def self_learning_insights(limit: int = 50, insight_type: str = None):
    async with httpx.AsyncClient(timeout=10.0) as client:
        try:
            params = {"limit": limit}
            if insight_type:
                params["insight_type"] = insight_type
            resp = await client.get(f"{settings.self_learning_url}/learning/insights", params=params)
            resp.raise_for_status()
            return resp.json()
        except httpx.HTTPError as e:
            logger.error(f"Self-learning insights error: {e}")
            raise HTTPException(status_code=502, detail="Self-learning engine unavailable")


@app.get("/fazle/self-learning/stats", dependencies=[Depends(verify_auth)])
async def self_learning_stats():
    async with httpx.AsyncClient(timeout=10.0) as client:
        try:
            resp = await client.get(f"{settings.self_learning_url}/learning/stats")
            resp.raise_for_status()
            return resp.json()
        except httpx.HTTPError as e:
            logger.error(f"Self-learning stats error: {e}")
            raise HTTPException(status_code=502, detail="Self-learning engine unavailable")
'''


def patch_api_settings():
    """Patch API Settings class with Phase-5 URLs."""
    path = os.path.join(BASE, 'fazle-system/api/main.py')
    with open(path, 'r') as f:
        content = f.read()

    # Remove any broken sed insertions (lines with both markers on same line)
    lines = content.split('\n')
    clean_lines = []
    for line in lines:
        # Skip lines that are clearly broken sed output (multiple fields on one line)
        if 'autonomy_engine_url' in line and 'tool_engine_url' in line:
            print(f'  Removing broken sed line: {line[:80]}...')
            continue
        clean_lines.append(line)
    content = '\n'.join(clean_lines)

    # Check if already patched properly (single field on its own line)
    if re.search(r'^\s+autonomy_engine_url:\s+str\s*=', content, re.MULTILINE):
        print('API Settings: already has Phase-5 URLs (properly formatted)')
        return True

    target = '    minio_secure: bool = False\n'
    if target not in content:
        print('ERROR: Could not find "    minio_secure: bool = False" in API main.py')
        return False

    content = content.replace(target, target + PHASE5_SETTINGS_BLOCK)
    with open(path, 'w') as f:
        f.write(content)
    print('API Settings: Phase-5 URLs added successfully')
    return True


def patch_api_routes():
    """Append Phase-5 proxy routes to API main.py."""
    path = os.path.join(BASE, 'fazle-system/api/main.py')
    with open(path, 'r') as f:
        content = f.read()

    if 'Phase-5: Autonomy Engine proxy' in content:
        print('API Routes: Phase-5 proxy routes already present')
        return True

    # Append routes
    content = content.rstrip() + PHASE5_API_ROUTES
    with open(path, 'w') as f:
        f.write(content)
    print('API Routes: Phase-5 proxy routes appended successfully')
    return True


def patch_brain_settings():
    """Patch Brain Settings class with Phase-5 URLs."""
    path = os.path.join(BASE, 'fazle-system/brain/main.py')
    with open(path, 'r') as f:
        content = f.read()

    if re.search(r'^\s+autonomy_engine_url:\s+str\s*=', content, re.MULTILINE):
        print('Brain Settings: already has Phase-5 URLs')
        return True

    # Try single-quote variant
    target = "    redis_url: str = 'redis://redis:6379/1'\n"
    if target not in content:
        # Try double-quote variant
        target = '    redis_url: str = "redis://redis:6379/1"\n'
    if target not in content:
        # Try with password placeholder (VPS may have actual redis password)
        # Search for any redis_url line
        m = re.search(r'^(    redis_url: str = [^\n]+\n)', content, re.MULTILINE)
        if m:
            target = m.group(1)
            print(f'  Found redis_url line: {target.strip()}')
        else:
            print('ERROR: Could not find redis_url line in Brain main.py')
            return False

    content = content.replace(target, target + PHASE5_SETTINGS_BLOCK)
    with open(path, 'w') as f:
        f.write(content)
    print('Brain Settings: Phase-5 URLs added successfully')
    return True


if __name__ == '__main__':
    print('='*60)
    print('Phase-5 VPS Patcher')
    print('='*60)

    ok = True
    print('\n[1/3] Patching API Settings...')
    ok = patch_api_settings() and ok

    print('\n[2/3] Patching API Routes...')
    ok = patch_api_routes() and ok

    print('\n[3/3] Patching Brain Settings...')
    ok = patch_brain_settings() and ok

    print('\n' + '='*60)
    if ok:
        print('All patches applied successfully!')
    else:
        print('Some patches FAILED — check output above')
        sys.exit(1)
