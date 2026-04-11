"""
Node 4 — Tutor Agent A  (Concise / Formula-First style)

Receives state dispatched via ``Send("tutor_agent_a", state)`` from the
``dispatch_tutors`` conditional edge.  Produces a ``TutorDraft`` that is
appended to ``state["tutor_drafts"]`` via the ``_reset_or_add_drafts`` reducer.

Memory handling
---------------
Uses ``trim_messages`` to extract the last 8 messages (4 Q&A turns) and
injects them via ``MessagesPlaceholder`` into a structured ``ChatPromptTemplate``.
This lets the LLM see the actual conversation roles (Human/AI) rather than a
flat text blob, significantly improving instruction-following on contextual
follow-up questions.

Adaptive learning
-----------------
``weak_topics`` (loaded from MongoDB before the graph runs) are injected into
the system prompt so Tutor A can proactively address known knowledge gaps.

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
* Module-level prompt + chain singletons (avoids warm-up on every request).
* ``@traceable`` with a descriptive name for LangSmith span clarity.
"""
from __future__ import annotations

import logging

from langchain_core.messages import trim_messages
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.runnables import RunnableConfig
from langchain_groq import ChatGroq
from langsmith import traceable

from app.agents.state import AgentState, TutorDraft
from app.config import get_settings
from app.utils.llm_pool import RoundRobinLLM
from app.utils.parse_output import parse_tutor_output

logger = logging.getLogger(__name__)
settings = get_settings()


# ── LLM pool (round-robin chat pool with auto-fallback) ─────────────────────
# Pool: gpt-oss-120b → llama-3.3-70b → kimi-k2 → llama-4-scout → gpt-oss-20b → llama-3.1-8b

_tutor_a_llm = RoundRobinLLM.for_role("chat", temperature=0.2, streaming=True)


# ── Helpers ───────────────────────────────────────────────────────────────────

def _build_context_text(context_docs: list[dict]) -> str:
    """Render numbered context passages for the prompt."""
    if not context_docs:
        return "(No classroom content was retrieved for this query. Use your general knowledge to help, but let the student know that this answer is not based on their course materials.)"
    lines = []
    for i, doc in enumerate(context_docs, 1):
        meta = doc.get("metadata", {})
        title = meta.get("title", "Unknown Source")
        content = doc.get("content", "")  # Use full parent chunk content to ensure missing data is captured
        lines.append(f"[{i}] {title}\n{content}")
    return "\n\n".join(lines)


# ── Prompt template (module-level singleton) ──────────────────────────────────

_TUTOR_A_SYSTEM = (
    "You are Tutor A — a precise, formula-first AI tutor.\n\n"
    "GROUNDING RULES:\n"
    "• Use the Course Content below as your PRIMARY source of truth. Always prioritize it.\n"
    "• You MAY add helpful supplementary explanations, examples, or clarifications beyond the course content "
    "to make the answer more complete and useful.\n"
    "• DO NOT fabricate facts, make up formulas, or invent information. If you are unsure, say so.\n"
    "• If the student's question is completely unrelated to the course subject "
    "(e.g. asking about cooking in a physics course), politely redirect them: "
    "'That topic doesn't seem related to this course. Feel free to ask me anything about your course material!'\n\n"
    "Style rules:\n"
    "• Lead with the exact definition or formula.\n"
    "• Use bullet points for structured answers.\n"
    "• Reference course sources inline with [1], [2], etc.\n"
    "• Be concise — eliminate all fluff.\n"
    "• For \"{difficulty}\" difficulty, calibrate depth accordingly.\n"
    "• If task is \"quiz\": provide a focused practice question with a worked answer.\n\n"
    "Task type: {task}\n\n"
    "{weak_topics_section}\n\n"
    "Course Content (primary source — supplement with your knowledge where helpful):\n"
    "{context_text}\n\n"
    "---\n"
    "End your response with EXACTLY these two lines (no extra text after):\n"
    "CITATIONS_JSON: [{{\"source_index\":1,\"title\":\"...\",\"alternate_link\":\"...\","
    "\"content_type\":\"...\",\"item_id\":\"...\",\"snippet\":\"...\"}}]\n"
    "REASONING: one sentence describing your approach"
)

_tutor_a_prompt = ChatPromptTemplate.from_messages([
    ("system", _TUTOR_A_SYSTEM),
    MessagesPlaceholder("history", optional=True),
    ("human", "{question}"),
])
# Chain is built per request via ainvoke on the pool (streaming=True is passed at pool level).


# ── Node ─────────────────────────────────────────────────────────────────────

@traceable(name="tutor_agent_a")
async def tutor_agent_a_node(state: AgentState, config: RunnableConfig) -> dict:
    """
    Concise / formula-first tutor.

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

    # Format the prompt into messages, then invoke the round-robin pool
    prompt_value = await _tutor_a_prompt.ainvoke(
        {
            "task": task,
            "difficulty": difficulty,
            "weak_topics_section": weak_topics_section,
            "context_text": context_text,
            "history": history,
            "question": state["original_query"],
        }
    )
    response = await _tutor_a_llm.ainvoke(
        prompt_value.to_messages(),
        config=config,
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
