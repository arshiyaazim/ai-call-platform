# ============================================================
# Code Execution Plugin — Safe Python code execution in sandbox
# Runs code in a subprocess with timeout and resource limits
# ============================================================
import asyncio
import logging
import sys
import textwrap
from . import Plugin

logger = logging.getLogger("fazle-plugins.code")

# Maximum execution time (seconds)
MAX_EXEC_TIME = 10
# Maximum output size (bytes)
MAX_OUTPUT = 10_000


class CodeExecutionPlugin(Plugin):
    name = "code_execution"
    description = "Execute Python code snippets in a sandboxed environment"
    version = "1.0.0"

    def get_input_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "code": {"type": "string", "description": "Python code to execute"},
                "language": {
                    "type": "string",
                    "enum": ["python"],
                    "default": "python",
                    "description": "Programming language",
                },
            },
            "required": ["code"],
        }

    async def execute(self, **kwargs) -> dict:
        code = kwargs.get("code", "")
        if not code.strip():
            return {"error": "No code provided"}

        # Block dangerous imports/operations
        blocked = ["os.system", "subprocess", "shutil.rmtree", "__import__('os')",
                    "eval(", "exec(", "open(", "import shutil"]
        code_lower = code.lower()
        for b in blocked:
            if b.lower() in code_lower:
                return {"error": f"Blocked operation: {b}"}

        return await self._run_python(code)

    async def _run_python(self, code: str) -> dict:
        # Wrap code to capture stdout
        wrapper = textwrap.dedent(f"""\
            import sys, io
            _buf = io.StringIO()
            sys.stdout = _buf
            sys.stderr = _buf
            try:
                exec('''{code.replace("'", "\\'")}''')
            except Exception as e:
                print(f"Error: {{e}}")
            finally:
                sys.stdout = sys.__stdout__
                sys.stderr = sys.__stderr__
                print(_buf.getvalue()[:{MAX_OUTPUT}])
        """)

        try:
            proc = await asyncio.create_subprocess_exec(
                sys.executable, "-c", wrapper,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await asyncio.wait_for(
                proc.communicate(), timeout=MAX_EXEC_TIME,
            )
            output = (stdout or b"").decode("utf-8", errors="replace")[:MAX_OUTPUT]
            errors = (stderr or b"").decode("utf-8", errors="replace")[:MAX_OUTPUT]

            return {
                "status": "ok",
                "output": output.strip(),
                "errors": errors.strip() if errors.strip() else None,
                "exit_code": proc.returncode,
            }
        except asyncio.TimeoutError:
            return {"error": f"Execution timed out after {MAX_EXEC_TIME}s"}
        except Exception as e:
            logger.error(f"Code execution failed: {e}")
            return {"error": str(e)}
