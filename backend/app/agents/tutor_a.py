"""
Node 4 — Tutor Agent A  (Concise / Formula-First style)

Receives state dispatched via ``Send("tutor_agent_a", state)`` from the
``dispatch_tutors`` conditional edge.  Produces a ``TutorDraft`` that is
appended to ``state["tutor_drafts"]`` via the ``operator.add`` reducer.

Style contract
--------------
* Structured, precise answers.
* Lead with definitions and formulas.
* Bullet points where helpful.
* Inline citation references [1], [2], etc.

Output format (required by ``parse_tutor_output``)
---------------------------------------------------
The response body is followed by exactly two structured blocks::

    CITATIONS_JSON: [{...}]
    REASONING: one sentence on your approach

LangChain best-practices
--------------------------
* Module-level LLM singleton (avoids warm-up on every request).
* ``@traceable`` with a descriptive name for LangSmith span clarity.
* Weak topics read directly from the state — no extra DB call needed
  because ``context_docs`` and ``task`` are already in state.
"""
from __future__ import annotations

import logging

from langchain_core.messages import HumanMessage
from langchain_core.runnables import RunnableConfig
from langchain_groq import ChatGroq
from langsmith import traceable

from app.agents.state import AgentState, TutorDraft
from app.config import get_settings
from app.utils.parse_output import parse_tutor_output

logger = logging.getLogger(__name__)
settings = get_settings()


# ── LLM singleton ────────────────────────────────────────────────────────────

_tutor_a_llm = ChatGroq(
    model=settings.groq_tutor_a_model,
    temperature=0.2,
    api_key=settings.groq_api_key,
    streaming=True,
)


# ── Helpers ───────────────────────────────────────────────────────────────────

def _build_context_text(context_docs: list[dict]) -> str:
    """Render numbered context passages for the prompt."""
    if not context_docs:
        return "(No classroom content retrieved — rely on general knowledge.)"
    lines = []
    for i, doc in enumerate(context_docs, 1):
        meta = doc.get("metadata", {})
        title = meta.get("title", "Unknown Source")
        content = doc.get("content", "")[:600]  # cap per-source to keep prompt lean
        lines.append(f"[{i}] {title}\n{content}")
    return "\n\n".join(lines)


# ── Node ─────────────────────────────────────────────────────────────────────

@traceable(name="tutor_agent_a")
async def tutor_agent_a_node(state: AgentState, config: RunnableConfig) -> dict:
    """
    Concise / formula-first tutor.

    Returns a dict slice with ``tutor_drafts`` (a length-1 list) and
    ``agent_thoughts``.  The ``operator.add`` reducer in AgentState merges
    both parallel tutors' lists into one before the Synthesizer runs.
    """
    context_text = _build_context_text(state.get("context_docs", []))
    task = state.get("task", "qa")
    difficulty = state.get("difficulty", "medium")

    prompt = f"""You are Tutor A — a precise, formula-first tutor.

Style rules:
• Lead with the exact definition or formula.
• Use bullet points for structured answers.
• Reference sources inline with [1], [2], etc.
• Be concise — eliminate all fluff.
• For "{difficulty}" difficulty, calibrate depth accordingly.
• If task is "quiz": provide a focused practice question with a worked answer.

Task type: {task}
Student question: {state['original_query']}

Course Content:
{context_text}

---
End your response with EXACTLY these two lines (no extra text after):
CITATIONS_JSON: [{{"source_index":1,"title":"...","alternate_link":"...","content_type":"...","item_id":"...","snippet":"..."}}]
REASONING: one sentence describing your approach"""

    response = await _tutor_a_llm.ainvoke(
        [HumanMessage(content=prompt)], config=config
    )
    response_text, citations, reasoning = parse_tutor_output(
        response.content, state.get("context_docs", [])
    )

    draft: TutorDraft = {
        "agent_id": "tutor_a",
        "style": "concise",
        "response_text": response_text,
        "citations": citations,
        "reasoning": reasoning,
    }

    logger.info(
        "Tutor A → %d chars · %d citations · reasoning=%r",
        len(response_text),
        len(citations),
        reasoning[:60] if reasoning else "",
    )

    return {
        "tutor_drafts": [draft],
        "agent_thoughts": [
            {
                "node": "tutor_agent_a",
                "summary": f"Concise draft · {len(citations)} citations",
                "data": {
                    "style": "concise",
                    "citation_count": len(citations),
                    "reasoning": reasoning,
                    "char_count": len(response_text),
                },
            }
        ],
    }
