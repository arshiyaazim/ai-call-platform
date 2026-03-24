"""
Conftest for Phase-5 service tests.

Each service has its own main.py, so we load them under unique module names
to avoid collisions when pytest collects multiple test files.
"""
import importlib.util
import sys
import os

_SERVICE_DIR = os.path.join(os.path.dirname(__file__), "..", "fazle-system")


def _load_service(service_name: str) -> "module":
    """Import fazle-system/<service_name>/main.py as 'main_<safe_name>'."""
    safe = service_name.replace("-", "_")
    module_name = f"main_{safe}"
    if module_name in sys.modules:
        return sys.modules[module_name]
    path = os.path.join(_SERVICE_DIR, service_name, "main.py")
    spec = importlib.util.spec_from_file_location(module_name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = mod
    spec.loader.exec_module(mod)
    return mod


# Pre-load all Phase-5 services so test files can import them by alias
# Missing deps (e.g. outside Docker) are tolerated — tests that use these
# will fail at import time with a clear error rather than crashing the suite.
def _try_load(name: str):
    try:
        return _load_service(name)
    except Exception as exc:
        import warnings
        warnings.warn(f"Could not pre-load service '{name}': {exc}")
        return None

autonomy_engine = _try_load("autonomy-engine")
tool_engine = _try_load("tool-engine")
knowledge_graph = _try_load("knowledge-graph")
autonomous_runner = _try_load("autonomous-runner")
self_learning = _try_load("self-learning")
