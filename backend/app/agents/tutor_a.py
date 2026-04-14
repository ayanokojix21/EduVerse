from __future__ import annotations

import logging

from langchain_core.messages import trim_messages
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.runnables import RunnableConfig
from langsmith import traceable

from app.agents.state import AgentState, TutorDraft
from app.config import get_settings
from app.utils.prompt_helpers import build_context_text
from app.utils.llm_pool import RoundRobinLLM

logger = logging.getLogger(__name__)
settings = get_settings()

# ── Prompt template ──────────────────────────────────────────────────────────

_TUTOR_A_SYSTEM = (
    "You are Tutor A — a precise, formula-first AI tutor.\n\n"
    "GROUNDING RULES:\n"
    "• Use the Course Content below as your PRIMARY source of truth. Always prioritize it.\n"
    "• Every time you use a fact from a source, cite it inline using [1], [2], etc.\n"    "â€¢ DO NOT write 'SOURCE_1' or 'SOURCE_2' in your text. Just use the brackets.\n"    "• You MUST map these indices correctly to the SOURCE_i provided in the context.\n"
    "• If multiple sources support a fact, cite them all [1, 2].\n"
    "• Be objective. Do NOT fabricate facts. If the content is missing, say so.\n\n"
    "Style rules:\n"
    "• Lead with the exact definition or formula.\n"
    "• Use bullet points for structured answers.\n"
    "• Reference course sources inline with [1], [2], etc.\n"
    "• MATH FORMATTING: Use LaTeX for all math. Wrap inline math in $...$ (e.g. $E=mc^2$) and block equations in $$...$$. NEVER use parentheses like (x+y) for formal math symbols.\n"
    "• Be concise — eliminate all fluff.\n"
    "• For \"{difficulty}\" difficulty, calibrate depth accordingly.\n"
    "• If task is \"quiz\": provide a focused practice question with a worked answer.\n\n"
    "Task type: {task}\n\n"
    "{weak_topics_section}\n\n"
    "Course Content (primary source — strictly grounded):\n"
    "{context_text}\n\n"
    "Generate your response text, citations, and pedagogical reasoning as structured data."
)

_tutor_a_prompt = ChatPromptTemplate.from_messages([
    ("system", _TUTOR_A_SYSTEM),
    MessagesPlaceholder("history", optional=True),
    ("human", "{question}"),
])


# ── Node ─────────────────────────────────────────────────────────────────────

@traceable(name="tutor_agent_a")
async def tutor_agent_a_node(state: AgentState, config: RunnableConfig) -> dict:
    """
    Concise / formula-first tutor node using native structured output.
    """
    # Lazy init to prevent import-time hangs
    tutor_a_chain = RoundRobinLLM.for_role(
        "chat", 
        temperature=0.2, 
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

    # Trim to last 8 messages (4 Q&A turns)
    history = trim_messages(
        state["messages"],
        strategy="last",
        token_counter=len,
        max_tokens=8,
        start_on="human",
        include_system=False,
    )

    # Build the full prompt chain (Declarative)
    chain = _tutor_a_prompt | tutor_a_chain

    # Invoke with structured output parsing built-in
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
    
    # Ensure agent identification is metadata-driven
    draft.agent_id = "tutor_a"
    draft.style = "concise"

    logger.info(
        "Tutor A → %d chars · %d citations · reasoning=%r",
        len(draft.response_text),
        len(draft.citations),
        draft.reasoning[:60],
    )

    return {
        "tutor_drafts": [draft],
        "agent_thoughts": [
            {
                "node": "tutor_a",
                "summary": f"Concise draft · {len(draft.citations)} citations",
                "data": {
                    "style": "concise",
                    "citation_count": len(draft.citations),
                    "reasoning": draft.reasoning,
                    "char_count": len(draft.response_text),
                },
            }
        ],
    }
