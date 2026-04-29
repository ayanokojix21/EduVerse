"""
app/utils/agent_tools.py
─────────────────────────
Agent Tooling
- Code Execution: Local subprocess sandbox 
- Web Search: SerperAPI
"""
import logging
import os
import subprocess
import tempfile

from langchain_core.tools import tool

logger = logging.getLogger(__name__)

# ── Security: Blocked patterns for local code sandbox ─────────────────────────
_BLOCKED_PATTERNS = frozenset([
    "import os", "import sys", "import subprocess", "import shutil",
    "import pathlib", "__import__", "exec(", "eval(",
    "open(", "os.system", "os.popen", "os.remove", "os.unlink",
    "shutil.rmtree", "subprocess.run", "subprocess.call",
])


@tool
def python_repl_tool(code: str) -> str:
    """
    Executes Python code in a secure local subprocess sandbox.
    Use this for validating math, logic, coding concepts, or verifying student solutions.
    Runs with a 10-second timeout and blocked dangerous operations.
    """
    code_lower = code.lower()
    for pattern in _BLOCKED_PATTERNS:
        if pattern.lower() in code_lower:
            return f"Security: '{pattern}' is not allowed in the sandbox."

    tmp_file = None
    try:
        tmp_file = tempfile.NamedTemporaryFile(
            mode="w", suffix=".py", delete=False, dir=tempfile.gettempdir()
        )
        tmp_file.write(code)
        tmp_file.flush()
        tmp_file.close()

        result = subprocess.run(
            ["python", tmp_file.name],
            capture_output=True,
            text=True,
            timeout=10,
            cwd=tempfile.gettempdir(),
        )

        output = ""
        if result.stdout:
            output += f"Output:\n{result.stdout}\n"
        if result.stderr:
            output += f"Error:\n{result.stderr}\n"
        if result.returncode != 0 and not output:
            output = f"Process exited with code {result.returncode}"

        return output.strip() if output else "Execution successful (no output)."

    except subprocess.TimeoutExpired:
        return "Execution timed out (10s limit). Simplify the code and try again."
    except FileNotFoundError:
        return "Python interpreter not found. Ensure Python is installed."
    except Exception as e:
        return f"Sandbox error: {e}"
    finally:
        if tmp_file and os.path.exists(tmp_file.name):
            try:
                os.unlink(tmp_file.name)
            except OSError:
                pass


@tool
def web_search_tool(query: str) -> str:
    """
    Searches the live web for the latest educational content, news, or validation facts.
    Ideal for finding recent events, contemporary research, or current news.
    """
    from app.config import get_settings
    from langchain_community.utilities import SerperAPIWrapper

    settings = get_settings()
    if not settings.serper_api_key:
        return "Web search is currently disabled (missing SERPER_API_KEY). Use local documentation instead."
    
    try:
        search = SerperAPIWrapper(serper_api_key=settings.serper_api_key)
        return search.run(query)
    except Exception as exc:
        logger.warning("Serper search failed: %s", exc)
        return "Web search failed. Please rely on local course documents."
