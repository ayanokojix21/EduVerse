"""
Node 6 — Synthesizer

Fan-in node that runs after BOTH parallel tutors have completed.
Operates in two modes depending on ``state["critic_feedback"]``:

Mode A — First pass (no critic feedback)
    Merges Tutor A (concise) and Tutor B (explanatory) into a single,
    superior answer. Structure: precise core → analogy → merged citations.

Mode B — Retry (critic provided specific issues)
    Rewrite ONLY the parts the critic flagged. Everything else stays identical.
    This targeted rewrite avoids regressing on correct content.

Memory handling
---------------
The synthesizer appends an ``AIMessage`` with the final response back into
``state["messages"]``.  This ensures subsequent turns have the complete
conversation history (Human questions + AI answers) available to all agents
via ``trim_messages``.

tutor_drafts fix
-----------------
The ``_reset_or_add_drafts`` reducer (state.py) + supervisor's ``None`` reset
guarantees ``state["tutor_drafts"]`` only ever contains the two drafts from
THIS turn.  The old ``reversed()`` hack is removed.

Streaming
---------
The synthesizer LLM is instantiated with ``streaming=True``.
When the chat endpoint uses ``graph.astream_events(version="v2")``,
``on_chat_model_stream`` events from this node carry the ``synthesizer``
run tag, enabling the frontend to show tokens as they arrive.
"""
from __future__ import annotations

import logging

from langchain_core.messages import AIMessage, HumanMessage
from langchain_core.runnables import RunnableConfig
from langsmith import traceable

from app.agents.state import AgentState
from app.config import get_settings
from app.utils.llm_pool import RoundRobinLLM
from app.utils.parse_output import parse_response_and_citations

logger = logging.getLogger(__name__)
settings = get_settings()


# ── LLM pool ───────────────────────────────────────────────────
# streaming=True so astream_events surfaces per-token events under the "synthesizer" tag.

_synthesizer_llm = RoundRobinLLM.for_role("chat", temperature=0.15, streaming=True)


# ── Node ─────────────────────────────────────────────────────────────────────

@traceable(name="synthesizer")
async def synthesizer_node(state: AgentState, config: RunnableConfig) -> dict:
    """
    Merge or refine the tutors' outputs into a single grounded answer.
    Appends an AIMessage to state["messages"] for future conversation context.
    """
    critic_feedback: list[str] = state.get("critic_feedback") or []
    is_retry = len(critic_feedback) > 0

    if is_retry:
        # ── Mode B: targeted critic-guided rewrite ────────────────────────
        issues_text = "\n".join(f"  • {issue}" for issue in critic_feedback)
        prompt = f"""The previous tutoring response requires targeted corrections.

Specific issues identified by the quality reviewer:
{issues_text}

Previous answer (do NOT rewrite sections that are not listed above):
{state.get("response_text", "")}

Instructions:
1. Fix ONLY the issues listed above.
2. Maintain all correct content verbatim.
3. Keep all citation references [1], [2], etc.

End with:
CITATIONS_JSON: [{{"source_index":1,"title":"...","alternate_link":"...","content_type":"...","item_id":"...","snippet":"..."}}]"""

    else:
        # ── Mode A: first-pass merge of both tutor drafts ─────────────────
        # Thanks to the _reset_or_add_drafts reducer + supervisor's None reset,
        # tutor_drafts only contains THIS turn's two drafts — no stale data.
        drafts = state.get("tutor_drafts") or []
        draft_a = next((d for d in drafts if d["agent_id"] == "tutor_a"), {})
        draft_b = next((d for d in drafts if d["agent_id"] == "tutor_b"), {})

        a_text = draft_a.get("response_text", "(Tutor A draft not available)")
        b_text = draft_b.get("response_text", "(Tutor B draft not available)")
        a_reasoning = draft_a.get("reasoning", "")
        b_reasoning = draft_b.get("reasoning", "")

        prompt = f"""Two specialist tutors answered the same student question in different styles.
Your task: synthesise their answers into a single, superior response.

RULES:
- Combine the best of both drafts into one clear, helpful answer.
- You MAY add brief clarifications or connecting explanations to make the answer flow better.
- DO NOT fabricate facts or invent information. Keep it accurate.
- If both tutors indicate the question is off-topic for the course, maintain that message.

Tutor A (concise/formula-first) — reasoning: {a_reasoning}
{a_text}

---
Tutor B (explanatory/analogy-rich) — reasoning: {b_reasoning}
{b_text}

Synthesis rules:
1. Lead with Tutor A's precise answer (formulas, definitions, structure).
2. Follow with Tutor B's best analogy or real-world example.
3. Cut all redundant content — every sentence must add value.
4. Merge and deduplicate citations from both tutors.
5. The merged answer must be better than either draft alone.
6. Maintain inline citation references [1], [2], etc.

Student question (for verification): {state.get("original_query", "")}

End with:
CITATIONS_JSON: [{{"source_index":1,"title":"...","alternate_link":"...","content_type":"...","item_id":"...","snippet":"..."}}]"""

    # Inject "synthesizer" tag so astream_events can filter this node's tokens
    invoke_config = {
        **config,
        "tags": [*(config.get("tags") or []), "synthesizer"],
    }

    result = await _synthesizer_llm.ainvoke(
        [HumanMessage(content=prompt)], config=invoke_config
    )
    response_text, citations = parse_response_and_citations(
        result.content, state.get("context_docs", [])
    )

    action = "Targeted critic-guided rewrite" if is_retry else "Merged A+B drafts"
    logger.info(
        "Synthesizer → %s · %d chars · %d citations",
        action,
        len(response_text),
        len(citations),
    )

    return {
        "response_text": response_text,
        "citations": citations,
        # Append the AI response to messages so all future agents see the
        # complete conversation history (Human questions + AI answers).
        "messages": [AIMessage(content=response_text)],
        # Clear critic feedback so a second pass doesn't loop again
        "critic_feedback": [],
        "agent_thoughts": [
            {
                "node": "synthesizer",
                "summary": f"{action} · {len(citations)} citations",
                "data": {
                    "is_retry": is_retry,
                    "citation_count": len(citations),
                    "char_count": len(response_text),
                },
            }
        ],
    }
