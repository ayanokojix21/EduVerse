from __future__ import annotations

import logging
import operator
from typing import Annotated, Literal

from langchain_core.messages import ToolMessage, AnyMessage
from langchain_core.runnables import RunnableConfig
from langgraph.graph import StateGraph, START
from langgraph.graph.message import add_messages
from langgraph.graph.state import CompiledStateGraph
from langgraph.types import Command, interrupt, Send
from langsmith import traceable
from typing_extensions import TypedDict

from app.agents.state import AgentState, merge_or_reset
from app.agents.swarm_engine import SwarmLoop          # top-level import
from app.config import get_settings
from app.utils.llm_pool import RoundRobinLLM
from app.retrieval.retriever import get_retrieval_chain
from app.utils.agent_tools import python_repl_tool, web_search_tool
from app.agents.prompts.quiz import DRAFTER_PROMPT, REVIEWER_PROMPT
from app.utils.thinking_utils import normalize_content
from app.agents.schemas.quiz import (
    QuizQuestion, 
    TransferToDrafter, 
    FinalizeQuiz,
    QuizInputState,
    QuizOutputState,
    QuestionDrafterState,
    QuizState,
)

logger = logging.getLogger(__name__)
# NOTE: settings is NOT loaded at module level to support test mocking.


# ── Nodes ────────────────────────────────────────────────────────────────────

@traceable(name="quiz_topic_selector")
async def topic_selector_node(
    state: QuizState,
) -> Command[Literal["retriever"]]:
    """HITL gate: asks student for quiz focus area if not already set."""
    if state.get("quiz_topic_source"):
        return Command(goto="retriever")
    
    source = interrupt({
        "question": "What's the focus of this quiz?",
        "options": ["Course Material", "PYQs", "Weak Topics"]
    })
    
    return Command(goto="retriever", update={"quiz_topic_source": source.lower().replace(" ", "_")})

@traceable(name="quiz_retriever")
async def retriever_node(
    state: QuizState,
    config: RunnableConfig,
) -> Command[Literal["distributor"]]:
    """Fetches retrieval context based on selected topic source."""
    settings = get_settings()  # resolved lazily for testability
    db = config["configurable"]["db"]
    sync_client = config["configurable"]["mongo_client_sync"]
    source = state.get("quiz_topic_source", "course_material")
    
    chain = get_retrieval_chain(state["user_id"], state["course_id"], db, sync_client, settings, document_type=("pyq" if source == "pyqs" else None))
    result = await chain.ainvoke(state["original_query"], config=config)
    
    return Command(goto="distributor", update={"context_docs": result["documents"]})

@traceable(name="quiz_distributor")
async def distributor_node(
    state: QuizState,
) -> Command[Literal["drafter_worker"]]:
    """Map step: fans out 3 parallel Drafter Workers via the Send API."""
    n = 3 
    return Command(goto=[
        Send("drafter_worker", {
            "messages": state["messages"],
            "context_docs": state.get("context_docs", []),
            "difficulty": state.get("difficulty", "medium"),
            "source_type": state.get("quiz_topic_source", "material"),
            "index": i,
            "image_data": state.get("image_data"),
            "image_mimetype": state.get("image_mimetype"),
            "is_multimodal": state.get("is_multimodal", False)
        }) for i in range(n)
    ])

@traceable(name="quiz_drafter_worker")
async def drafter_worker_node(state: QuestionDrafterState, config: RunnableConfig) -> dict:
    """Isolated parallel worker producing one MCQ."""
    llm = RoundRobinLLM.for_role(
        "quiz", 
        temperature=1.0, 
        top_p=0.95, 
        top_k=64, 
        schema=QuizQuestion
    )
    context_lines = [f"[{i+1}] {d.get('metadata', {}).get('title', 'Doc')}: {d.get('content', '')}" for i, d in enumerate(state.get("context_docs", []))]
    context_text = "\n\n".join(context_lines)
    
    prompt = DRAFTER_PROMPT.format_messages(
        c=context_text,
        d=state["difficulty"], 
        s=state["source_type"], 
        m=state["messages"][-50:]
    )
    
    # Reasoning Trigger & Multimodal Vision Injection for Gemma 4
    reasoning_instr = "\n\n### REASONING INSTRUCTION\nThink step-by-step to map distractors to misconceptions."
    
    if state.get("image_data"):
        from langchain_core.messages import HumanMessage
        last_msg = prompt[-1]
        text_content = (last_msg.content if isinstance(last_msg.content, str) else "") + reasoning_instr
        
        mm_content = [
            {"type": "text", "text": text_content},
            {
                "type": "image_url",
                "image_url": {"url": f"data:{state.get('image_mimetype', 'image/png')};base64,{state['image_data']}"}
            }
        ]
        prompt[-1] = HumanMessage(content=mm_content)
    else:
        if isinstance(prompt[-1].content, str):
            prompt[-1].content += reasoning_instr
    
    res_raw = await llm.ainvoke(prompt, config=config)
    res: QuizQuestion | None = res_raw.get("parsed")
    
    # Normalize raw content to string for DPO extraction
    raw_res = normalize_content(
        res_raw["raw"].content if hasattr(res_raw["raw"], "content") else str(res_raw["raw"]),
        include_thinking=True
    )
    
    if not res:
        logger.warning(f"Drafter worker failed to return structured schema for index {state.get('index')}")
        return {
            "quiz_raw_responses": [raw_res]
        }
        
    dump = res.model_dump() if hasattr(res, "model_dump") else res

    return {
        "quiz_current_draft": [dump],
        "quiz_raw_responses": [raw_res]
    }



@traceable(name="quiz_reviewer")
async def reviewer_node(
    state: QuizState,
    config: RunnableConfig,
) -> Command[Literal["formatter", "reviewer", "distributor"]]:
    """Reduce: evaluates all parallel candidates and approves or rejects the set."""
    revisions = state.get("quiz_revisions", 0)
    
    # ── Record DPO Pair (if this is a revision) ─────────────────────────────
    raw_chosen = "\n---\n".join(state.get("quiz_raw_responses", []))
    raw_rejected = str(state.get("quiz_rejected_draft", ""))
    
    dpo_update = SwarmLoop.extract_dpo_pairs(
        agent_name="quiz_drafter",
        original_query=state["original_query"],
        chosen_content=raw_chosen,
        rejected_content=raw_rejected,
        revision_count=revisions
    )

    if revisions >= 1:
        return Command(
            goto="formatter", 
            update={
                "dpo_pairs": dpo_update,
                "quiz_best_draft": state.get("quiz_current_draft", [])
            }
        )

    llm = RoundRobinLLM.for_role(
        "critic", 
        temperature=0.3, 
        top_p=0.95, 
        top_k=64
    ).bind_tools([TransferToDrafter, FinalizeQuiz, web_search_tool, python_repl_tool])
    prompt = REVIEWER_PROMPT.format_messages(m=state["messages"][-50:])
    
    res = await llm.ainvoke(prompt, config=config)
    if not res.tool_calls:
        return Command(goto="formatter", update={"messages": [res]})

    tc = res.tool_calls[0]
    
    if tc["name"] in ["web_search_tool", "python_repl_tool"]:
        import asyncio
        # Tools are synchronous — run in thread pool to avoid blocking the async event loop
        if tc["name"] == "web_search_tool":
            output = await asyncio.to_thread(web_search_tool.invoke, tc["args"])
        else:
            output = await asyncio.to_thread(python_repl_tool.invoke, tc["args"])
        return Command(
            goto="reviewer", 
            update={"messages": [res, ToolMessage(content=output, tool_call_id=tc["id"])]}
        )
    
    if tc["name"] == "TransferToDrafter":
        return SwarmLoop.handle_rejection(
            target_node="distributor",
            current_revisions=revisions,
            tc_id=tc["id"],
            llm_res=res,
            current_draft=state["quiz_current_draft"],
            state_keys={
                "revisions": "quiz_revisions", 
                "rejected": "quiz_rejected_draft",
                "current": "quiz_current_draft",
                "reset_signal": True
            }
        )

    return Command(goto="formatter", update={
        "messages": [res, ToolMessage(content="Quiz set approved.", tool_call_id=tc["id"])],
        "quiz_best_draft": state["quiz_current_draft"],
        "dpo_pairs": dpo_update
    })

@traceable(name="quiz_formatter")
async def formatter_node(state: QuizState) -> dict:
    """Prepares the user-facing markdown display."""
    draft = state.get("quiz_current_draft", [])
    md = "### Parallel-Generated Quiz Set\n\n"
    for i, q in enumerate(draft, 1):
        bloom = q.get('bloom_level', 'Understand')
        reasoning = q.get('distractor_reasoning', 'Focus on the core concept.')
        
        md += f"**Q{i} [{bloom}]. {q['question']}**\n"
        md += "- " + "\n- ".join(q["options"]) + "\n"
        md += f"> **Distractor Insight**: {reasoning}\n\n"
        
    return {"response_text": md}

# ── Subgraph Builder ─────────────────────────────────────────────────────────

def build_quiz_subgraph() -> CompiledStateGraph:
    g = StateGraph(QuizState, input_schema=QuizInputState, output_schema=QuizOutputState)
    g.add_node("topic_selector", topic_selector_node)
    g.add_node("retriever",      retriever_node)
    g.add_node("distributor",    distributor_node)
    g.add_node("drafter_worker", drafter_worker_node)
    g.add_node("reviewer",       reviewer_node)
    g.add_node("formatter",      formatter_node)
    
    g.add_edge(START, "topic_selector")
    g.add_edge("drafter_worker", "reviewer") 
    return g.compile()
