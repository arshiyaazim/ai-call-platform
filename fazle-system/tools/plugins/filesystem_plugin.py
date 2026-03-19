# ============================================================
# Filesystem Plugin — Safe file listing and reading
# Only allows access within a configured safe directory
# ============================================================
import os
from pathlib import Path
from . import Plugin


class FilesystemPlugin(Plugin):
    name = "filesystem"
    description = "List and read files within the allowed workspace directory"
    version = "1.0.0"

    def __init__(self, base_dir: str = "/data/workspace"):
        self._base = Path(base_dir).resolve()

    def get_input_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "enum": ["list", "read"],
                    "description": "Filesystem action",
                },
                "path": {
                    "type": "string",
                    "description": "Relative path within the workspace",
                    "default": ".",
                },
            },
            "required": ["action"],
        }

    def _safe_path(self, rel: str) -> Path | None:
        """Resolve path and ensure it's within the base directory."""
        try:
            target = (self._base / rel).resolve()
            if target == self._base or self._base in target.parents:
                return target
        except (ValueError, OSError):
            pass
        return None

    async def execute(self, **kwargs) -> dict:
        action = kwargs.get("action", "list")
        rel_path = kwargs.get("path", ".")

        safe = self._safe_path(rel_path)
        if safe is None:
            return {"error": "Path outside allowed workspace"}

        if action == "list":
            if not safe.is_dir():
                return {"error": "Not a directory"}
            entries = []
            for entry in sorted(safe.iterdir()):
                entries.append({
                    "name": entry.name,
                    "type": "dir" if entry.is_dir() else "file",
                    "size": entry.stat().st_size if entry.is_file() else 0,
                })
            return {"status": "ok", "path": rel_path, "entries": entries}

        if action == "read":
            if not safe.is_file():
                return {"error": "Not a file"}
            if safe.stat().st_size > 100_000:
                return {"error": "File too large (>100KB)"}
            try:
                text = safe.read_text(encoding="utf-8", errors="replace")
                return {"status": "ok", "path": rel_path, "content": text}
            except Exception as e:
                return {"error": f"Read failed: {e}"}

        return {"error": "Unknown action"}
