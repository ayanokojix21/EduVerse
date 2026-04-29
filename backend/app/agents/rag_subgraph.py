from __future__ import annotations

import logging
import re
from typing import Annotated, Literal

from langchain_core.messages import ToolMessage, AnyMessage
from langchain_core.runnables import RunnableConfig
from langgraph.graph import StateGraph, START
from langgraph.graph.message import add_messages
from langgraph.types import Command
from langsmith import traceable
from typing_extensions import TypedDict

from app.agents.state import AgentState, Citation
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
settings = get_settings()

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
        result: PlannerOutput = res_raw["parsed"]
        rewritten = result.search_query
    except Exception as exc:
        logger.warning("Planner LLM failed, using raw query: %s", exc)
        rewritten = state["original_query"]
        
    return Command(goto="executor", update={"rewritten_queries": [rewritten]})

@traceable(name="rag_executor")
async def executor_node(
    state: AgentState,
    config: RunnableConfig,
) -> Command[Literal["distiller"]]:
    """Executes classroom/PYQ hybrid retrieval and labels confidence."""
    db = config["configurable"]["db"]
    sync_client = config["configurable"]["mongo_client_sync"]
    source = state.get("quiz_topic_source", "course_material")
    document_type = "pyq" if source == "pyqs" else None
    
    query_to_search = state.get("rewritten_queries", [state["original_query"]])[0]
    
    chain = get_retrieval_chain(state["user_id"], state["course_id"], db, sync_client, settings, document_type=document_type)
    result = await chain.ainvoke(query_to_search, config=config)
    
    from app.retrieval.explainability import build_explainability
    from langchain_core.documents import Document

    label = "CLASSROOM_GROUNDED" if result["top_score"] >= settings.grounding_threshold else "CLASSROOM_INSUFFICIENT"
    raw_children = [Document(page_content=d["page_content"], metadata=d["metadata"]) for d in result.get("raw_docs", [])]

    explain_payload = build_explainability(
        query=query_to_search,
        reranked_children=raw_children,
        parent_docs=result["documents"],
        top_score=result["top_score"],
        retrieval_label=label
    )
    
    return Command(goto="distiller", update={
        "context_docs": result["documents"],
        "retrieval_label": label,
        "top_reranker_score": result["top_score"],
        "explainability": explain_payload
    })

@traceable(name="rag_distiller")
async def distiller_node(
    state: AgentState,
) -> Command[Literal["generator"]]:
    """Ranks and token-budgets the context window before generation."""
    docs = state.get("context_docs", [])
    distilled = sorted(docs, key=lambda d: d.get("metadata", {}).get("relevance_score", 0.0), reverse=True)
    from app.utils.token_utils import truncate_context_docs
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
        "Begin your response with <|thought|> to plan the Socratic scaffolding and analogy anchoring."
    )
    if isinstance(prompt[-1].content, str):
        prompt[-1].content += reasoning_trigger
    
    if is_multi:
        from langchain_core.messages import HumanMessage
        content = [
            {"type": "text", "text": prompt[0].content}, 
            {
                "type": "image_url",
                "image_url": {"url": f"data:{state.get('image_mimetype', 'image/png')};base64,{state['image_data']}"}
            }
        ]
        mm_message = HumanMessage(content=content)
        final_prompt = [prompt[0], mm_message]
    else:
        final_prompt = prompt

    res_raw = await llm.ainvoke(final_prompt, config=config)

    if isinstance(res_raw, dict):
        res = res_raw.get("raw", res_raw.get("parsed"))
    else:
        res = res_raw
    
    if not res.tool_calls:
        return Command(goto="generator", update={"messages": [res]})
        
    tc_args = res.tool_calls[0].get("args", {})
    draft = tc_args.get("draft_answer", "")
    
    if not draft:
        logger.warning("Generator tool-call missing draft_answer; using content fallback.")
        draft = res.content

    return Command(
        goto="validator", 
        update={
            "messages": [res, ToolMessage(content="Analyzing draft...", tool_call_id=res.tool_calls[0]["id"])], 
            "tutor_current_draft": draft,
            "tutor_raw_responses": [res.content]
        }
    )

from app.agents.swarm_engine import SwarmLoop


@traceable(name="tutor_validator")
async def validator_node(
    state: AgentState,
    config: RunnableConfig,
) -> Command[Literal["generator", "formatter", "validator"]]:
    """Adversarially fact-checks the draft; loops, approves, or requests revision."""
    revisions = state.get("tutor_revisions", 0)
    if revisions >= 3:
        return Command(goto="formatter")

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
        output = web_search_tool.invoke(tc["args"]) if tc["name"] == "web_search_tool" else python_repl_tool.invoke(tc["args"])
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

    raw_chosen = "\n---\n".join(state.get("tutor_raw_responses", []))
    raw_rejected = state.get("tutor_rejected_draft", "")
    
    dpo_update = SwarmLoop.extract_dpo_pairs(
        agent_name="rag_tutor_generator",
        original_query=state["original_query"],
        chosen_content=raw_chosen,
        rejected_content=raw_rejected,
        revision_count=revisions
    )

    return Command(goto="formatter", update={
        "messages": [res, ToolMessage(content="Verified.", tool_call_id=tc["id"])], 
        "tutor_verified_draft": tc["args"].get("verified_answer", ""),
        "dpo_pairs": dpo_update
    })

@traceable(name="tutor_formatter")
async def formatter_node(state: AgentState, config: RunnableConfig) -> dict:
    """Finalizes response structure and citation objects."""
    draft = state.get("tutor_verified_draft", state.get("tutor_current_draft", ""))
    
    citations = []
    citation_pattern = re.compile(r"\[(?:Doc|Source)[:\s]*(\d+)\]", re.IGNORECASE)
    for ref in set(citation_pattern.findall(draft)):
        idx = int(ref)-1
        if 0 <= idx < len(state["context_docs"]):
            d = state["context_docs"][idx]
            meta = d.get("metadata", {})
            snippet = d.get("snippet") or d.get("content", "")[:150] or "Source material"
            citations.append(Citation(
                source_index=int(ref),
                title=d.get("title", "Source"),
                alternate_link=meta.get("alternate_link", "#"),
                file_url=meta.get("attachment_url") or d.get("file_url"),
                page_number=meta.get("page_number") or d.get("page_number"),
                snippet=snippet,
            ))

    return {"response_text": draft, "citations": citations}

# ── Subgraph Builder ─────────────────────────────────────────────────────────

def build_rag_subgraph() -> StateGraph:
    g = StateGraph(AgentState, input=RAGInputState, output=RAGOutputState)
    g.add_node("planner", planner_node)
    g.add_node("executor", executor_node)
    g.add_node("distiller", distiller_node)
    g.add_node("generator", generator_node)
    g.add_node("validator", validator_node)
    g.add_node("formatter", formatter_node)
    
    g.add_edge(START, "planner")
    return g.compile()
