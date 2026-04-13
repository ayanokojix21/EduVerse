from __future__ import annotations

import logging

from langchain_core.messages import AIMessage, HumanMessage
from langchain_core.runnables import RunnableConfig
from langchain_core.prompts import ChatPromptTemplate
from langsmith import traceable
from pydantic import BaseModel, Field

from app.agents.state import AgentState, Citation
from app.config import get_settings
from app.utils.llm_pool import RoundRobinLLM
from app.utils.prompt_helpers import build_context_text
from app.utils.token_utils import truncate_context_docs

logger = logging.getLogger(__name__)
settings = get_settings()


# ── Structured output schema ─────────────────────────────────────────────────

class SynthesizerOutput(BaseModel):
    """Schema for the final synthesized tutoring response."""
    response_text: str = Field(description="The final educational response text")
    citations: list[Citation] = Field(description="Merged and deduplicated course citations")
    consensus_reasoning: str = Field(description="One-sentence synthetic reasoning")


# ── Node ─────────────────────────────────────────────────────────────────────

@traceable(name="synthesizer")
async def synthesizer_node(state: AgentState, config: RunnableConfig) -> dict:
    """
    Merge or refine the tutors' outputs into a single grounded answer.
    """
    # Lazy init to prevent import-time hangs
    llm = RoundRobinLLM.for_role(
        "chat", 
        temperature=0.15, 
        streaming=True,
        schema=SynthesizerOutput
    )
    synthesizer_chain = llm
    
    critic_feedback: list[str] = state.get("critic_feedback") or []
    is_retry = len(critic_feedback) > 0
    
    # ── Token-Aware Context Pruning ──────────────────────────────────────────
    raw_context = state.get("context_docs", [])
    context_docs = truncate_context_docs(raw_context, max_tokens=5800)
    context_text = build_context_text(context_docs)
    
    system_template = (
        "You are an expert AI Synthesizer. You must combine multiple tutor drafts into a single, cohesive, grounded response.\n"
    )

    if is_retry:
        # ── Mode B: targeted critic-guided rewrite ────────────────────────
        review = state.get("critic_review") or {}
        required_facts = review.get("required_facts") or []
        
        issues_text = "\n".join(f"  • {issue}" for issue in critic_feedback)
        facts_text = "\n".join(f"  • {fact}" for fact in required_facts)
        
        user_template = """The previous tutoring response requires targeted corrections based on the course materials.
 
 Specific issues identified:
 {issues_text}
 
 GROUND TRUTH FACTS (MUST BE INCLUDED):
 {facts_text}
 
 Course Content (Ground Truth Documents):
 {context_text}
 
 Previous answer (Fix only the errors where the facts above were violated):
 {response_text}
 
 Instructions:
 1. Fix the accuracy using the GROUND TRUTH FACTS provided above.
 2. Ensure the response remains educational and helpful.
 3. Output your answer in JSON format."""
        input_data = {
            "issues_text": issues_text,
            "facts_text": facts_text,
            "context_text": context_text,
            "response_text": state.get("response_text", "")
        }

    else:
        # ── Mode A: first-pass merge of both tutor drafts ─────────────────
        drafts = state.get("tutor_drafts") or []
        draft_a = next((d for d in drafts if getattr(d, "agent_id", None) == "tutor_a"), None)
        draft_b = next((d for d in drafts if getattr(d, "agent_id", None) == "tutor_b"), None)

        a_text = draft_a.response_text if draft_a else "(Tutor A draft not available)"
        b_text = draft_b.response_text if draft_b else "(Tutor B draft not available)"
        a_reasoning = draft_a.reasoning if draft_a else ""
        b_reasoning = draft_b.reasoning if draft_b else ""

        user_template = """Two specialist tutors answered the same student question in different styles.
Your task: synthesise their answers into a single, superior response.

RULES:
- Combine the best of both drafts into one clear, helpful answer.
- You MUST maintain all inline citation references [1], [2], etc.
- DO NOT write "SOURCE_1" or "SOURCE_2" in your text. Instead, integrate the reference smoothly (e.g., "according to the notes [1]") or just use the brackets.
- ONLY include citations in your final CITATIONS list if they are EXPLICITLY referenced with a number (e.g. [1]) in your synthesized text. Discard any unused sources.
- You MUST merge and deduplicate the final citations based exactly on the source documents provided.
- For every citation, extract the `page_number` from the SOURCE_i header if available and include it in the JSON.
- Ensure every index [i] in the final response maps exactly to source [i] in the final CITATIONS list.

Tutor A (concise/formula-first) — reasoning: {a_reasoning}
{a_text}

---
Tutor B (explanatory/analogy-rich) — reasoning: {b_reasoning}
{b_text}"""

        input_data = {
            "context_text": context_text,
            "a_reasoning": a_reasoning,
            "a_text": a_text,
            "b_reasoning": b_reasoning,
            "b_text": b_text
        }

    invoke_config = {
        **config,
        "tags": [*(config.get("tags") or []), "synthesizer"],
    }

    prompt = ChatPromptTemplate.from_messages([
        ("system", system_template),
        ("human", user_template)
    ])
    
    full_chain = prompt | synthesizer_chain

    # Invoke with all dynamic content
    result = await full_chain.ainvoke(input_data, config=invoke_config)
    
    response_text = result.response_text
    raw_citations = result.citations
    consensus_reasoning = result.consensus_reasoning

    # Post-process: Enforce Ground Truth Metadata on Citations
    citations: list[Citation] = []
    for cit in raw_citations:
        idx = cit.source_index - 1
        if 0 <= idx < len(context_docs):
            # Map directly from retrieved documents, overriding potential LLM hallucinations
            doc = context_docs[idx]
            meta = getattr(doc, "metadata", doc.get("metadata", {}))
            cit.title = meta.get("title") or cit.title
            # Cover both snake_case and camelCase (LangChain Google Classroom loader uses varying schemes)
            cit.alternate_link = meta.get("alternate_link") or meta.get("alternateLink") or cit.alternate_link
            cit.file_url = meta.get("attachment_url") or meta.get("attachmentUrl") or meta.get("file_url") or cit.file_url
            
            # Allow LLM to extract page number if the metadata doesn't have it explicitly bound,
            # but prefer metadata
            if meta.get("page_number"):
                cit.page_number = int(meta["page_number"])
                
            citations.append(cit)
        else:
            # Invalid source_index hallucinated by LLM
            continue

    action = "Targeted critic-guided rewrite" if is_retry else "Merged A+B drafts"
    logger.info(
        "Synthesizer → %s · %d chars · %d citations · consensus=%r",
        action,
        len(response_text),
        len(citations),
        consensus_reasoning[:60] if consensus_reasoning else "",
    )

    return {
        "response_text": response_text,
        "citations": citations,
        "consensus_reasoning": consensus_reasoning,
        "messages": [AIMessage(content=response_text)],
        "critic_feedback": [],
        "agent_thoughts": [
            {
                "node": "synthesizer",
                "summary": f"{action} · {len(citations)} citations",
                "data": {
                    "is_retry": is_retry,
                    "citation_count": len(citations),
                    "char_count": len(response_text),
                    "consensus_reasoning": consensus_reasoning,
                },
            }
        ],
    }
