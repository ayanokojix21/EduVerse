"""
Node 1 — Orchestrator (Merge of Supervisor & Query Rewriter)
Classifies the incoming student query AND generates optimized retrieval queries 
in a single LLM round-trip to minimize system latency.
"""
from __future__ import annotations
import logging
from langchain_core.messages import HumanMessage, trim_messages
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.runnables import RunnableConfig
from langsmith import traceable
from pydantic import BaseModel, Field
from app.agents.state import AgentState
from app.config import get_settings
from app.utils.llm_pool import RoundRobinLLM

logger = logging.getLogger(__name__)
settings = get_settings()

class OrchestratorOutput(BaseModel):
    """Combined output for system routing and retrieval strategy."""
    task: str = Field(
        description="One of: qa, explain, quiz, feedback, timetable",
        pattern="^(qa|explain|quiz|feedback|timetable)$",
    )
    difficulty: str = Field(
        description="One of: easy, medium, hard",
        pattern="^(easy|medium|hard)$",
    )
    rewritten_query: str = Field(
        description="1 retrieval-optimised search query string. DO NOT answer the question here.",
    )
    needs_rewrite: bool = Field(
        description="True if the user's query was conversational or vague and required history-based expansion.",
        default=True
    )

_orchestrator_prompt = ChatPromptTemplate.from_messages([
    (
        "system",
        "You are the central Orchestrator for an AI tutoring system.\n"
        "Your goal is to classify the student's intent and optimize their search query for a vector database.\n\n"
        "TASK CLASSIFICATION:\n"
        "- qa: factual question about the material.\n"
        "- explain: student needs a concept explained deeply.\n"
        "- quiz: student wants a practice question.\n"
        "- feedback: student wants their work reviewed.\n"
        "- timetable: student is asking about their schedule or academic emails.\n\n"
        "QUERY OPTIMIZATION RULES:\n"
        "1. Remove conversational filler (can you, please explain, what is, etc.).\n"
        "2. Preserve ALL domain-specific terms and formula names exactly.\n"
        "3. Resolve ALL pronouns (it, that, them) using the provided conversation history.\n"
        "4. Produce exactly 1 standalone search engine query string.\n"
        "5. DO NOT answer the question. You are ONLY planning the search.\n\n"
        "Return ONLY structured JSON matching the required schema."
    ),
    MessagesPlaceholder("history", optional=True),
    ("human", "{question}"),
])

@traceable(name="orchestrator")
async def orchestrator_node(state: AgentState, config: RunnableConfig) -> dict:
    """Classify the student's query and optimize retrieval in one turn."""
    llm = RoundRobinLLM.for_role(
        "structured", 
        temperature=0.1, 
        schema=OrchestratorOutput
    )
    original = state["original_query"]
    
    # Trim to last 6 messages for context
    history = trim_messages(
        state["messages"],
        strategy="last",
        token_counter=len,
        max_tokens=6,
        start_on="human",
        include_system=False,
    )

    try:
        prompt_value = await _orchestrator_prompt.ainvoke({
            "history": history,
            "question": original,
        })
        result: OrchestratorOutput = await llm.ainvoke(
            prompt_value.to_messages(), 
            config=config
        )
        task = result.task
        difficulty = result.difficulty
        rewrites = [result.rewritten_query]
        needs_rewrite = result.needs_rewrite
    except Exception as exc:
        logger.warning("Orchestrator LLM failed, using defaults: %s", exc)
        task, difficulty, rewrites, needs_rewrite = "qa", "medium", [original], True

    logger.info(
        "Orchestrator â†’ task=%s rewrites=%d needs_rewrite=%s",
        task, len(rewrites), needs_rewrite
    )

    return {
        "task": task,
        "difficulty": difficulty,
        "rewritten_queries": rewrites,
        "needs_rewrite": needs_rewrite,
        "tutor_drafts": None,
        "agent_thoughts": [
            {
                "node": "orchestrator",
                "summary": f"Task: {task} · Strategy: Optimized ({len(rewrites)} queries)",
                "data": {
                    "task": task,
                    "difficulty": difficulty,
                    "rewritten_queries": rewrites,
                    "needs_rewrite": needs_rewrite
                },
            }
        ],
    }
