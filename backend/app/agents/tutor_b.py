"""
Node 5 — Tutor Agent B  (Explanatory / Analogy-Rich style)

Receives state dispatched via ``Send("tutor_agent_b", state)`` from the
``dispatch_tutors`` conditional edge.  Produces a ``TutorDraft`` that is
appended to ``state["tutor_drafts"]`` via the ``_reset_or_add_drafts`` reducer.

Memory handling
---------------
Uses ``trim_messages`` to extract the last 8 messages (4 Q&A turns) and
injects them via ``MessagesPlaceholder`` into a structured ``ChatPromptTemplate``.
This lets the LLM see the actual conversation roles (Human/AI) rather than a
flat text blob — critical for analogy-rich, story-driven explanations that
build on what was discussed.

Adaptive learning
-----------------
``weak_topics`` (loaded from MongoDB before the graph runs) are injected into
the system prompt so Tutor B can craft analogies that specifically target the
student's known knowledge gaps.

Style contract
--------------
* Open with a real-world analogy before formal definitions.
* Concrete examples for every concept.
* Empathetic, conversational tone.
* Inline citation references [1], [2], etc.

Output format (required by ``parse_tutor_output``)
---------------------------------------------------
The response body is followed by exactly two structured blocks::

    CITATIONS_JSON: [{...}]
    REASONING: one sentence on your approach
"""
from __future__ import annotations

import logging

from langchain_core.messages import trim_messages
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.runnables import RunnableConfig
from langsmith import traceable

from app.agents.state import AgentState, TutorDraft
from app.config import get_settings
from app.utils.llm_pool import RoundRobinLLM
from app.utils.parse_output import parse_tutor_output

logger = logging.getLogger(__name__)
settings = get_settings()


# ── LLM pool (round-robin chat pool with auto-fallback) ─────────────────────
# Pool: gpt-oss-120b → llama-3.3-70b → kimi-k2 → llama-4-scout → gpt-oss-20b → llama-3.1-8b
# Tutor B starts at a DIFFERENT round-robin index than Tutor A, spreading load across models.

_tutor_b_llm = RoundRobinLLM.for_role("chat", temperature=0.35, streaming=True)


# ── Helpers ───────────────────────────────────────────────────────────────────

def _build_context_text(context_docs: list[dict]) -> str:
    """Render numbered context passages for the prompt."""
    if not context_docs:
        return "(No classroom content retrieved — rely on general knowledge.)"
    lines = []
    for i, doc in enumerate(context_docs, 1):
        meta = doc.get("metadata", {})
        title = meta.get("title", "Unknown Source")
        content = doc.get("content", "")[:600]
        lines.append(f"[{i}] {title}\n{content}")
    return "\n\n".join(lines)


# ── Prompt template (module-level singleton) ──────────────────────────────────

_TUTOR_B_SYSTEM = (
    "You are Tutor B — an empathetic, analogy-rich AI tutor who builds deep intuition.\n\n"
    "Style rules:\n"
    "• Open with a relatable real-world analogy before introducing formal terms.\n"
    "• Follow with a concrete worked example from the course material.\n"
    "• Use conversational, encouraging language.\n"
    "• Reference sources inline with [1], [2], etc.\n"
    "• For \"{difficulty}\" difficulty, calibrate depth and analogy complexity.\n"
    "• If task is \"quiz\": create a scenario-based question that tests understanding.\n\n"
    "Task type: {task}\n\n"
    "{weak_topics_section}\n\n"
    "Course Content (use these as your primary sources):\n"
    "{context_text}\n\n"
    "---\n"
    "End your response with EXACTLY these two lines (no extra text after):\n"
    "CITATIONS_JSON: [{{\"source_index\":1,\"title\":\"...\",\"alternate_link\":\"...\","
    "\"content_type\":\"...\",\"item_id\":\"...\",\"snippet\":\"...\"}}]\n"
    "REASONING: one sentence describing your approach"
)

_tutor_b_prompt = ChatPromptTemplate.from_messages([
    ("system", _TUTOR_B_SYSTEM),
    MessagesPlaceholder("history", optional=True),
    ("human", "{question}"),
])
# Chain built at call time via pool pattern (see node function).


# ── Node ─────────────────────────────────────────────────────────────────────

@traceable(name="tutor_agent_b")
async def tutor_agent_b_node(state: AgentState, config: RunnableConfig) -> dict:
    """
    Explanatory / analogy-rich tutor.

    Returns a dict slice with ``tutor_drafts`` (a length-1 list) and
    ``agent_thoughts``.  The ``_reset_or_add_drafts`` reducer in AgentState
    accumulates both parallel tutors' lists before the Synthesizer runs.
    """
    context_text = _build_context_text(state.get("context_docs", []))
    task = state.get("task", "qa")
    difficulty = state.get("difficulty", "medium")
    weak_topics: list[str] = state.get("weak_topics") or []

    weak_topics_section = (
        f"Student weak areas to address: {', '.join(weak_topics)}"
        if weak_topics
        else "No prior weak areas identified."
    )

    # Trim to last 8 messages (4 Q&A turns) by message count.
    history = trim_messages(
        state["messages"],
        strategy="last",
        token_counter=len,
        max_tokens=8,
        start_on="human",
        include_system=False,
    )

    # Format prompt then invoke round-robin pool
    prompt_value = await _tutor_b_prompt.ainvoke(
        {
            "task": task,
            "difficulty": difficulty,
            "weak_topics_section": weak_topics_section,
            "context_text": context_text,
            "history": history,
            "question": state["original_query"],
        }
    )
    response = await _tutor_b_llm.ainvoke(
        prompt_value.to_messages(),
        config=config,
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
