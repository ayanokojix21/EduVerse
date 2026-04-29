from __future__ import annotations

import logging
from typing import Annotated, Literal

from langchain_core.messages import ToolMessage, AnyMessage
from langchain_core.runnables import RunnableConfig
from langgraph.graph import StateGraph, START, END
from langgraph.graph.message import add_messages
from langgraph.types import Command
from langsmith import traceable
from typing_extensions import TypedDict

from app.agents.state import AgentState
from app.utils.llm_pool import RoundRobinLLM
from app.utils.agent_tools import python_repl_tool, web_search_tool
from app.agents.prompts.feedback import DIAGNOSTICIAN_PROMPT, MENTOR_PROMPT
from app.agents.schemas.feedback import (
    QuestionFeedback,
    FeedbackScoring,
    TransferToMentor,
    TransferToDiagnostician,
    FinalizeFeedback,
    FeedbackInputState,
    FeedbackOutputState,
)

logger = logging.getLogger(__name__)

# ── Nodes ────────────────────────────────────────────────────────────────────

@traceable(name="feedback_diagnostician")
async def diagnostician_node(
    state: AgentState,
    config: RunnableConfig,
) -> Command[Literal["diagnostician", "mentor"]]:
    """RCA via tool-calling loop; hands structured analysis to Mentor."""
    llm = RoundRobinLLM.for_role(
        "feedback", 
        temperature=0.3, 
        top_p=0.95, 
        top_k=64
    ).bind_tools([TransferToMentor, web_search_tool, python_repl_tool])
    
    context_lines = [f"[{i+1}] {d.get('metadata', {}).get('title', 'Doc')}: {d.get('content', '')}" for i, d in enumerate(state.get("context_docs", []))]
    context_text = "\n\n".join(context_lines)
    
    prompt = DIAGNOSTICIAN_PROMPT.format_messages(
        c=context_text,
        q=state.get("quiz_responses", []), 
        m=state["messages"][-50:]
    )
    
    # Reasoning Injection for Gemma 4
    if isinstance(prompt[-1].content, str):
        prompt[-1].content += "\n\n### REASONING INSTRUCTION\nBegin with <|thought|> to perform Root Cause Analysis (RCA)."
    
    res_raw = await llm.ainvoke(prompt, config=config)
    res = res_raw
    
    if not res.tool_calls:
        return Command(goto="diagnostician", update={"messages": [res]})

    tc = res.tool_calls[0]

    # ── Agentic Execution Loop (RCA Verification) ────────────────────────────
    if tc["name"] in ["web_search_tool", "python_repl_tool"]:
        logger.info("Feedback Diagnostician executing: %s", tc["name"])
        output = web_search_tool.invoke(tc["args"]) if tc["name"] == "web_search_tool" else python_repl_tool.invoke(tc["args"])
        return Command(
            goto="diagnostician", 
            update={"messages": [res, ToolMessage(content=output, tool_call_id=tc["id"])]}
        )

    draft = tc["args"]
    return Command(
        goto="mentor", 
        update={
            "messages": [res, ToolMessage(content="Analyzing student gaps...", tool_call_id=res.tool_calls[0]["id"])],
            "feedback_raw_responses": [res.content],
            "current_feedback_draft": draft
        }
    )

from app.agents.swarm_engine import SwarmLoop


@traceable(name="feedback_mentor")
async def mentor_node(
    state: AgentState,
    config: RunnableConfig,
) -> Command[Literal["formatter", "diagnostician"]]:
    """Quality-gates feedback with Growth Mindset scoring; loops or finalises."""
    revisions = state.get("feedback_revisions", 0)
    if revisions >= 3:
        return Command(goto="formatter")

    llm = RoundRobinLLM.for_role(
        "critic", 
        temperature=0.2, 
        top_p=0.95, 
        top_k=64
    ).bind_tools([TransferToDiagnostician, FinalizeFeedback])
    
    prompt = MENTOR_PROMPT.format_messages(m=state["messages"][-50:])
    
    res = await llm.ainvoke(prompt, config=config)
    if not res.tool_calls:
        return Command(goto="formatter", update={"messages": [res]})

    tc = res.tool_calls[0]
    
    if tc["name"] == "TransferToDiagnostician":
        return SwarmLoop.handle_rejection(
            target_node="diagnostician",
            current_revisions=revisions,
            tc_id=tc["id"],
            llm_res=res,
            current_draft=state["current_feedback_draft"],
            state_keys={"revisions": "feedback_revisions", "rejected": "feedback_rejected_draft"}
        )

    raw_chosen = "\n---\n".join(state.get("feedback_raw_responses", []))
    raw_rejected = str(state.get("feedback_rejected_draft", ""))
    
    dpo_update = SwarmLoop.extract_dpo_pairs(
        agent_name="feedback_diagnostician",
        original_query=str(state.get("quiz_responses", [])),
        chosen_content=raw_chosen,
        rejected_content=raw_rejected,
        revision_count=revisions,
        critique="Mentor forced pedagogical refinement."
    )

    return Command(goto="formatter", update={
        "messages": [res, ToolMessage(content="Mentor approved.", tool_call_id=tc["id"])],
        "dpo_pairs": dpo_update
    })

@traceable(name="feedback_formatter")
async def formatter_node(state: AgentState) -> dict:
    """Prepares structured performance response via SOTA schema validation."""
    raw_draft = state.get("current_feedback_draft", {})
    
    try:
        draft = TransferToMentor.model_validate(raw_draft)
        summary = draft.overall_summary
        q_feedback = draft.question_feedback
        weak_topics = draft.detected_weak_topics
    except Exception:
        summary = raw_draft.get("overall_summary", "Evaluation complete.")
        q_feedback = raw_draft.get("question_feedback", [])
        weak_topics = raw_draft.get("detected_weak_topics", [])

    md = f"## Performance Analysis\n\n{summary}\n\n"
    
    for i, q in enumerate(q_feedback, 1):
        is_val = hasattr(q, 'is_correct')
        is_correct = q.is_correct if is_val else q.get("is_correct")
        status = "[CORRECT]" if is_correct else "[INCORRECT]"
        text = q.question_text if is_val else q.get("question_text")
        
        md += f"### {status} Question {i}\n"
        md += f"*{text}*\n\n"
        
        if not is_correct:
            rc = q.root_cause if is_val else q.get("root_cause")
            tip = q.improvement_tip if is_val else q.get("improvement_tip")
            md += f"- **Root Cause Analysis**: {rc}\n"
            md += f"- **Mentor Recommendation**: {tip}\n"
        
        md += "\n---\n\n"
        
    return {"response_text": md, "identified_weak_topics": weak_topics}

# ── Subgraph Builder ─────────────────────────────────────────────────────────

def build_feedback_subgraph() -> StateGraph:
    g = StateGraph(AgentState, input=FeedbackInputState, output=FeedbackOutputState)
    g.add_node("diagnostician", diagnostician_node)
    g.add_node("mentor",        mentor_node)
    g.add_node("formatter",     formatter_node)
    
    g.add_edge(START, "diagnostician")
    g.add_edge("formatter", END)
    return g.compile()
