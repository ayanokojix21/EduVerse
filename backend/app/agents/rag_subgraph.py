from __future__ import annotations

import logging
import re
import time
from typing import Annotated, Literal

from langchain_core.messages import ToolMessage, AnyMessage
from langchain_core.runnables import RunnableConfig
from langgraph.graph import StateGraph, START
from langgraph.graph.state import CompiledStateGraph
from langgraph.graph.message import add_messages
from langgraph.types import Command, interrupt
from langsmith import traceable
from typing_extensions import TypedDict

from app.agents.state import AgentState, Citation
from app.agents.swarm_engine import SwarmLoop          # moved from mid-file
from app.config import get_settings
from app.retrieval.retriever import get_retrieval_chain
from app.utils.llm_pool import RoundRobinLLM
from app.utils.prompt_helpers import build_context_text
from app.utils.token_utils import truncate_context_docs
from app.agents.schemas.rag import (
    PlannerOutput,
    TransferToValidator,
    TransferToGenerator,
    TransferToFormatter,
    RAGInputState,
    RAGOutputState,
)
from app.utils.agent_tools import python_repl_tool, web_search_tool
from app.agents.prompts.rag import PLANNER_PROMPT, GENERATOR_PROMPT, VALIDATOR_PROMPT

logger = logging.getLogger(__name__)
# NOTE: settings is NOT loaded at module level to support test mocking.
# Each node resolves it lazily via get_settings().

# ── Model Schemas & Tools ───────────────────────────────────────────────────


@traceable(name="rag_planner")
async def planner_node(
    state: RAGInputState,
    config: RunnableConfig,
) -> Command[Literal["executor"]]:
    """Agentically optimises retrieval queries via structured output."""
    llm = RoundRobinLLM.for_role(
        "orchestrator", 
        temperature=0.3, 
        top_p=0.95, 
        top_k=64, 
        schema=PlannerOutput
    )
    prompt = PLANNER_PROMPT.format_messages(q=state["original_query"])
    
    try:
        res_raw = await llm.ainvoke(prompt, config=config)
        # Handle structured output dictionary format
        if isinstance(res_raw, dict) and res_raw.get("parsed"):
            rewritten = res_raw["parsed"].search_query
        else:
            # Fallback for Gemma models which return raw text instead of structured tools
            raw_text = res_raw.get("raw").content if isinstance(res_raw, dict) else res_raw.content
            if isinstance(raw_text, list):
                raw_text = "\n".join([str(part.get("text") or part.get("thinking") or part) for part in raw_text if isinstance(part, dict)])
            import json
            import re
            json_match = re.search(r"\{.*\}", str(raw_text), re.DOTALL)
            if json_match:
                rewritten = json.loads(json_match.group(0)).get("search_query", state["original_query"])
            else:
                rewritten = state.get("original_query", "")
    except Exception as exc:
        logger.warning("Planner LLM failed, using raw query: %s", exc)
        rewritten = state.get("original_query", "")  # safe .get() instead of KeyError
        
    return Command(goto="executor", update={"rewritten_queries": [rewritten]})

@traceable(name="rag_executor")
async def executor_node(
    state: AgentState,
    config: RunnableConfig,
) -> Command[Literal["hitl"]]:
    """Executes classroom/PYQ hybrid retrieval and labels confidence."""
    settings = get_settings()  # resolved lazily for testability
    db = config["configurable"]["db"]
    sync_client = config["configurable"]["mongo_client_sync"]
    source = state.get("quiz_topic_source", "course_material")
    document_type = "pyq" if source == "pyqs" else None
    
    query_to_search = state.get("rewritten_queries", [state.get("original_query", "")])[0]
    
    t0 = time.monotonic()  # Start retrieval timer
    chain = get_retrieval_chain(state["user_id"], state["course_id"], db, sync_client, settings, document_type=document_type)
    result = await chain.ainvoke(query_to_search, config=config)
    retrieval_ms = int((time.monotonic() - t0) * 1000)  # Capture latency
    
    from app.retrieval.explainability import build_explainability
    from langchain_core.documents import Document

    top_score = result["top_score"]
    # 3-way confidence label (matches AgentState.retrieval_label Literal type)
    if top_score >= settings.grounding_threshold:
        label = "CLASSROOM_GROUNDED"
    elif top_score >= 0.30:
        label = "CLASSROOM_LOW_CONFIDENCE"
    else:
        label = "CLASSROOM_INSUFFICIENT"

    raw_children = [Document(page_content=d["page_content"], metadata=d["metadata"]) for d in result.get("raw_docs", [])]

    explain_payload = build_explainability(
        query=query_to_search,
        reranked_children=raw_children,
        parent_docs=result["documents"],
        top_score=top_score,
        retrieval_label=label
    )
    
    # Route to hitl node (which will pass-through or pause depending on label)
    return Command(goto="hitl", update={
        "context_docs": result["documents"],
        "retrieval_label": label,
        "top_reranker_score": top_score,
        "retrieval_ms": retrieval_ms,
        "explainability": explain_payload
    })


@traceable(name="rag_hitl")
async def hitl_node(
    state: AgentState,
) -> Command[Literal["distiller"]]:
    """
    2026 LangGraph HITL Pattern — 'Socratic Intervention'.
    
    Fires ONLY when classroom materials are insufficient (CLASSROOM_INSUFFICIENT).
    Pauses the graph via interrupt() and presents the student with a choice:
      - 'search_web'    → approve web search for analogies from trusted sources
      - 'socratic_only' → proceed with pure Socratic scaffolding from course material
    
    The graph resumes when the frontend calls POST /chat/stream/resume with the
    student's decision. If the student approves web search, sets 
    tutor_web_search_approved=True so the generator can use the web_search_tool.
    """
    retrieval_label = state.get("retrieval_label", "CLASSROOM_GROUNDED")
    
    # Only pause if classroom materials are genuinely insufficient (not just low confidence)
    # LOW_CONFIDENCE → generator handles with appropriate disclaimers, no HITL needed
    if retrieval_label != "CLASSROOM_INSUFFICIENT":
        return Command(goto="distiller", update={})
    
    # ── Pause the graph and surface a structured choice to the student ──────────
    # interrupt() checkpoints the state to MongoDB, then raises an exception
    # that LangGraph catches. The graph is paused until resumed via Command(resume=...).
    student_decision = interrupt({
        "type": "hitl_required",
        "message": (
            "I searched your course materials but couldn't find enough information to answer this question with confidence. "
            "Would you like me to search trusted educational sources on the web to supplement your learning?"
        ),
        "options": [
            {"value": "search_web",    "label": "Yes, search the web for analogies and explanations"},
            {"value": "socratic_only", "label": "No, guide me from what's in my course materials"},
        ],
        "retrieval_label": retrieval_label,
        "top_reranker_score": state.get("top_reranker_score", 0.0),
    })
    
    # ── Graph resumes here with student_decision = the value sent by the frontend
    web_search_approved = (student_decision == "search_web")
    
    return Command(
        goto="distiller",
        update={"tutor_web_search_approved": web_search_approved},
    )

@traceable(name="rag_distiller")
async def distiller_node(
    state: AgentState,
) -> Command[Literal["generator"]]:
    """Ranks and token-budgets the context window before generation."""
    docs = state.get("context_docs", [])
    distilled = sorted(docs, key=lambda d: d.get("metadata", {}).get("relevance_score", 0.0), reverse=True)
    # truncate_context_docs is imported at the top of this module
    return Command(goto="generator", update={"context_docs": truncate_context_docs(distilled)})

@traceable(name="tutor_generator")
async def generator_node(
    state: AgentState,
    config: RunnableConfig,
) -> Command[Literal["generator", "validator"]]:
    """Drafts educational content using Gemma 4's native Chain-of-Thought capabilities."""
    is_multi = state.get("is_multimodal", False) and state.get("image_data")
    llm = RoundRobinLLM.for_role(
        "tutor", 
        temperature=1.0, 
        top_p=0.95, 
        top_k=64, 
        vision=is_multi
    ).bind_tools([TransferToValidator])
    
    context = build_context_text(state["context_docs"])
    label = state.get("retrieval_label", "CLASSROOM_GROUNDED")
    prompt = GENERATOR_PROMPT.format_messages(c=context, m=state["messages"][-50:], l=label)
    
    reasoning_trigger = (
        "\n\n### REASONING INSTRUCTION\n"
        "Begin your response with <think> to plan the Socratic scaffolding and analogy anchoring."
    )
    
    if is_multi:
        from langchain_core.messages import HumanMessage
        last_msg = prompt[-1]
        text_content = last_msg.content if isinstance(last_msg.content, str) else ""
        
        # Append reasoning trigger to the text part
        text_content += reasoning_trigger
        
        mm_content = [
            {"type": "text", "text": text_content}, 
            {
                "type": "image_url",
                "image_url": {"url": f"data:{state.get('image_mimetype', 'image/png')};base64,{state['image_data']}"}
            }
        ]
        prompt[-1] = HumanMessage(content=mm_content)
        final_prompt = prompt
    else:
        if isinstance(prompt[-1].content, str):
            prompt[-1].content += reasoning_trigger
        final_prompt = prompt

    res_raw = await llm.ainvoke(final_prompt, config=config)

    if isinstance(res_raw, dict):
        res = res_raw.get("raw", res_raw.get("parsed"))
    else:
        res = res_raw
        
    # Normalize content to string (handles Gemma 4's multimodal/thinking list format)
    raw_content = res.content
    if isinstance(raw_content, list):
        raw_content = "\n".join([
            (part.get("text") or part.get("thinking") or str(part)) if isinstance(part, dict) else str(part)
            for part in raw_content
        ])
    else:
        raw_content = str(raw_content)
    
    if not res.tool_calls:
        logger.warning("Generator failed to call tools; falling back to Validator.")
        return Command(
            goto="validator", 
            update={
                "messages": [res],
                "tutor_raw_responses": [raw_content],
                "tutor_current_draft": raw_content
            }
        )
        
    tc_args = res.tool_calls[0].get("args", {})
    draft = tc_args.get("draft_answer", "")
    
    if not draft:
        logger.warning("Generator tool-call missing draft_answer; using content fallback.")
        draft = raw_content

    return Command(
        goto="validator", 
        update={
            "messages": [res, ToolMessage(content="Analyzing draft...", tool_call_id=res.tool_calls[0]["id"])], 
            "tutor_current_draft": draft,
            "tutor_raw_responses": [raw_content]
        }
    )


@traceable(name="tutor_validator")
async def validator_node(
    state: AgentState,
    config: RunnableConfig,
) -> Command[Literal["generator", "formatter", "validator"]]:
    """Adversarially fact-checks the draft; loops, approves, or requests revision."""
    revisions = state.get("tutor_revisions", 0)
    
    # ── Record DPO Pair (if this is a revision) ─────────────────────────────
    raw_chosen = "\n---\n".join(state.get("tutor_raw_responses", []))
    raw_rejected = state.get("tutor_rejected_draft", "")
    
    dpo_update = SwarmLoop.extract_dpo_pairs(
        agent_name="rag_tutor_generator",
        original_query=state["original_query"],
        chosen_content=raw_chosen,
        rejected_content=raw_rejected,
        revision_count=revisions
    )

    if revisions >= 2:
        return Command(
            goto="formatter", 
            update={
                "dpo_pairs": dpo_update,
                "tutor_verified_draft": state.get("tutor_current_draft", "")
            }
        )

    llm = RoundRobinLLM.for_role(
        "critic", 
        temperature=0.2, 
        top_p=0.95, 
        top_k=64
    ).bind_tools([
        TransferToGenerator, TransferToFormatter, web_search_tool, python_repl_tool
    ])
    
    prompt = VALIDATOR_PROMPT.format_messages(
        c=build_context_text(state["context_docs"]), 
        d=state["tutor_current_draft"], 
        m=state["messages"][-50:]
    )

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
        return Command(goto="validator", update={"messages": [res, ToolMessage(content=output, tool_call_id=tc["id"])]})

    if tc["name"] == "TransferToGenerator":
        return SwarmLoop.handle_rejection(
            target_node="generator",
            current_revisions=revisions,
            tc_id=tc["id"],
            llm_res=res,
            current_draft=state["tutor_current_draft"],
            state_keys={"revisions": "tutor_revisions", "rejected": "tutor_rejected_draft"}
        )

    return Command(goto="formatter", update={
        "messages": [res, ToolMessage(content="Verified.", tool_call_id=tc["id"])], 
        "tutor_verified_draft": tc["args"].get("verified_answer", ""),
        "dpo_pairs": dpo_update
    })

@traceable(name="tutor_formatter")
async def formatter_node(state: AgentState) -> dict:
    """Finalizes response structure and citation objects."""
    draft = state.get("tutor_verified_draft", state.get("tutor_current_draft", ""))
    
    citations = []
    citation_pattern = re.compile(r"\[(?:Doc|Source)[_:\s]*(\d+)\]", re.IGNORECASE)
    for ref in set(citation_pattern.findall(draft)):
        idx = int(ref)-1
        if 0 <= idx < len(state["context_docs"]):
            d = state["context_docs"][idx]
            meta = d.get("metadata", {})
            snippet = d.get("snippet") or d.get("content", "")[:150] or "Source material"
            citations.append(Citation(
                source_index=int(ref),
                title=d.get("title") or meta.get("title", "Source"),
                alternate_link=meta.get("alternate_link", "#"),
                file_url=meta.get("attachment_url") or d.get("file_url"),
                page_number=meta.get("page_number") or d.get("page_number"),
                content_type=meta.get("content_type", "classroom_material"),
                snippet=snippet,
            ))

    return {"response_text": draft, "citations": citations}

# ── Subgraph Builder ─────────────────────────────────────────────────────────

def build_rag_subgraph() -> CompiledStateGraph:
    g = StateGraph(AgentState, input_schema=RAGInputState, output_schema=RAGOutputState)
    g.add_node("planner",   planner_node)
    g.add_node("executor",  executor_node)
    g.add_node("hitl",      hitl_node)       # Socratic Intervention — fires on CLASSROOM_INSUFFICIENT
    g.add_node("distiller", distiller_node)
    g.add_node("generator", generator_node)
    g.add_node("validator", validator_node)
    g.add_node("formatter", formatter_node)
    
    g.add_edge(START, "planner")
    # executor_node routes to 'hitl' via Command(goto='hitl')
    # hitl_node routes to 'distiller' via Command(goto='distiller')
    # All other routing is Command-based inside each node
    return g.compile()
