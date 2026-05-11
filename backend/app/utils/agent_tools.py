"""
app/utils/agent_tools.py
─────────────────────────
Agent Tooling — Cloud Native.

- Code Execution: E2B Cloud Sandbox (fully isolated container)
- Web Search:     SerperDev API
"""
import logging

from langchain_core.tools import tool

from app.config import get_settings

logger = logging.getLogger(__name__)


@tool
def python_repl_tool(code: str) -> str:
    """
    Executes Python code in a secure E2B cloud sandbox.
    Use this for validating math, logic, coding concepts, or verifying student solutions.
    Runs in a fully isolated cloud container with a 30-second timeout.
    """
    settings = get_settings()

    if not settings.e2b_api_key:
        return "Code execution is currently disabled (missing E2B_API_KEY). Please describe the solution instead."

    try:
        from e2b_code_interpreter import Sandbox

        sbx = Sandbox(api_key=settings.e2b_api_key, timeout=30)
        try:
            execution = sbx.run_code(code)
        finally:
            sbx.kill()

        # Collect outputs
        outputs = []
        if execution.results:
            for result in execution.results:
                if result.text:
                    outputs.append(result.text)

        if execution.error:
            return f"Error ({execution.error.name}): {execution.error.value}"

        if execution.logs.stdout:
            outputs.extend(execution.logs.stdout)

        if execution.logs.stderr:
            stderr_text = "".join(execution.logs.stderr).strip()
            if stderr_text:
                outputs.append(f"Stderr:\n{stderr_text}")

        return "\n".join(outputs).strip() or "Execution successful (no output)."

    except Exception as exc:
        logger.warning("E2B sandbox error: %s", exc)
        return f"Sandbox error: {exc}"


@tool
def web_search_tool(query: str) -> str:
    """
    Searches the live web for the latest educational content, news, or validation facts.
    Ideal for finding recent events, contemporary research, or current news.
    """
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
