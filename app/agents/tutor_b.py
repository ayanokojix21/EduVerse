"""
Node 5 — Tutor Agent B  (Explanatory / Analogy-Rich style)

Mirror of tutor_a but with a different LLM (Llama 4 Maverick) and a
clearly different pedagogical persona.  Runs in parallel with Tutor A
via LangGraph's Send API.

Style contract
--------------
* Teach deeply with intuition-building.
* Use real-world analogies and concrete examples.
* Prefer narrative ("imagine you're...") over bullet points.
* Inline citation references [1], [2], etc.

The ``operator.add`` reducer on ``state["tutor_drafts"]`` ensures both
drafts are accumulated before the Synthesizer fan-in node runs.
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

_tutor_b_llm = ChatGroq(
    model=settings.groq_tutor_b_model,
    temperature=0.4,
    api_key=settings.groq_api_key,
    streaming=True,
)


# ── Helpers ───────────────────────────────────────────────────────────────────

def _build_context_text(context_docs: list[dict]) -> str:
    if not context_docs:
        return "(No classroom content retrieved — rely on general knowledge.)"
    lines = []
    for i, doc in enumerate(context_docs, 1):
        meta = doc.get("metadata", {})
        title = meta.get("title", "Unknown Source")
        content = doc.get("content", "")[:600]
        lines.append(f"[{i}] {title}\n{content}")
    return "\n\n".join(lines)


# ── Node ─────────────────────────────────────────────────────────────────────

@traceable(name="tutor_agent_b")
async def tutor_agent_b_node(state: AgentState, config: RunnableConfig) -> dict:
    """
    Explanatory / analogy-rich tutor.

    Returns a dict slice with ``tutor_drafts`` (length-1 list) and
    ``agent_thoughts``.
    """
    context_text = _build_context_text(state.get("context_docs", []))
    task = state.get("task", "qa")
    difficulty = state.get("difficulty", "medium")

    prompt = f"""You are Tutor B — a patient, story-driven teacher who builds deep intuition.

Style rules:
• Open with a relatable real-world analogy before introducing formal terms.
• Explain the "why" behind every concept, not just the "what".
• Use conversational prose; reserve bullet points for step-by-step processes.
• Reference sources inline with [1], [2], etc.
• For "{difficulty}" difficulty, calibrate depth accordingly.
• If task is "quiz": create a scenario-based question that tests understanding.

Task type: {task}
Student question: {state['original_query']}

Course Content:
{context_text}

---
End your response with EXACTLY these two lines (no extra text after):
CITATIONS_JSON: [{{"source_index":1,"title":"...","alternate_link":"...","content_type":"...","item_id":"...","snippet":"..."}}]
REASONING: one sentence describing your approach"""

    response = await _tutor_b_llm.ainvoke(
        [HumanMessage(content=prompt)], config=config
    )
    response_text, citations, reasoning = parse_tutor_output(
        response.content, state.get("context_docs", [])
    )

    draft: TutorDraft = {
        "agent_id": "tutor_b",
        "style": "explanatory",
        "response_text": response_text,
        "citations": citations,
        "reasoning": reasoning,
    }

    logger.info(
        "Tutor B → %d chars · %d citations · reasoning=%r",
        len(response_text),
        len(citations),
        reasoning[:60] if reasoning else "",
    )

    return {
        "tutor_drafts": [draft],
        "agent_thoughts": [
            {
                "node": "tutor_agent_b",
                "summary": f"Explanatory draft · {len(citations)} citations",
                "data": {
                    "style": "explanatory",
                    "citation_count": len(citations),
                    "reasoning": reasoning,
                    "char_count": len(response_text),
                },
            }
        ],
    }
