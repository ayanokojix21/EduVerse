"""
Node 5 — Tutor Agent B  (Explanatory / Analogy-Rich style)
Receives state dispatched from the supervisor and produces an explanatory TutorDraft.
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
from app.utils.prompt_helpers import build_context_text

logger = logging.getLogger(__name__)
settings = get_settings()

# ── Prompt template (module-level singleton) ──────────────────────────────────

_TUTOR_B_SYSTEM = (
    "You are Tutor B — an empathetic, analogy-rich AI tutor who builds deep intuition.\n\n"
    "GROUNDING RULES:\n"
    "• Use the Course Content below as your PRIMARY source of truth. Always prioritize it.\n"
    "• Every time you use a fact from a source, cite it inline using [1], [2], etc.\n"    "â€¢ DO NOT write 'SOURCE_1' or 'SOURCE_2' in your text. Just use the brackets.\n"    "• You MUST map these indices correctly to the SOURCE_i provided in the context.\n"
    "• If multiple sources support a fact, cite them all [1, 2].\n"
    "• Be objective. Do NOT fabricate facts. If the content is missing, say so.\n\n"
    "Style rules:\n"
    "• Open with a relatable real-world analogy before introducing formal terms.\n"
    "• Follow with a concrete worked example from the course material or a helpful illustration.\n"
    "• Use conversational, encouraging language.\n"
    "• Reference course sources inline with [1], [2], etc.\n"
    "• For \"{difficulty}\" difficulty, calibrate depth and analogy complexity.\n"
    "• If task is \"quiz\": create a scenario-based question that tests understanding.\n\n"
    "Task type: {task}\n\n"
    "{weak_topics_section}\n\n"
    "Course Content (primary source — strictly grounded):\n"
    "{context_text}\n\n"
    "Generate your explanatory response text, citations, and pedagogical reasoning as structured data."
)

_tutor_b_prompt = ChatPromptTemplate.from_messages([
    ("system", _TUTOR_B_SYSTEM),
    MessagesPlaceholder("history", optional=True),
    ("human", "{question}"),
])


# ── Node ─────────────────────────────────────────────────────────────────────

@traceable(name="tutor_agent_b")
async def tutor_agent_b_node(state: AgentState, config: RunnableConfig) -> dict:
    """
    Explanatory / analogy-rich tutor.

    Returns a dict slice with ``tutor_drafts`` (a length-1 list) and
    ``agent_thoughts``.  The ``_reset_or_add_drafts`` reducer in AgentState
    accumulates both parallel tutors' lists before the Synthesizer runs.
    """
    # Lazy init to prevent import-time hangs
    tutor_b_chain = RoundRobinLLM.for_role(
        "chat", 
        temperature=0.35, 
        streaming=True, 
        schema=TutorDraft
    )
    context_text = build_context_text(state.get("context_docs", []))
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

    # Build the full prompt chain
    chain = _tutor_b_prompt | tutor_b_chain

    # Invoke with structured output parsing
    draft: TutorDraft = await chain.ainvoke(
        {
            "task": task,
            "difficulty": difficulty,
            "weak_topics_section": weak_topics_section,
            "context_text": context_text,
            "history": history,
            "question": state["original_query"],
        },
        config=config,
    )
    
    draft.agent_id = "tutor_b"
    draft.style = "explanatory"

    logger.info(
        "Tutor B → %d chars · %d citations · reasoning=%r",
        len(draft.response_text),
        len(draft.citations),
        draft.reasoning[:60],
    )

    return {
        "tutor_drafts": [draft],
        "agent_thoughts": [
            {
                "node": "tutor_b",
                "summary": f"Explanatory draft · {len(draft.citations)} citations",
                "data": {
                    "style": "explanatory",
                    "citation_count": len(draft.citations),
                    "reasoning": draft.reasoning,
                    "char_count": len(draft.response_text),
                },
            }
        ],
    }
