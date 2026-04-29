"""
app/agents/orchestrator.py
───────────────────────────
Orchestrator Node — entry point of the EduVerse MAS.
Classifies the student's intent and routes to the correct swarm.
"""
from __future__ import annotations

import logging
from typing import Literal

from langchain_core.messages import trim_messages
from langchain_core.runnables import RunnableConfig
from langgraph.types import Command
from langsmith import traceable

from app.agents.state import AgentState
from app.utils.llm_pool import RoundRobinLLM
from app.agents.prompts.orchestrator import ORCHESTRATOR_PROMPT
from app.agents.schemas.orchestrator import OrchestratorOutput

logger = logging.getLogger(__name__)


@traceable(name="orchestrator")
async def orchestrator_node(
    state: AgentState,
    config: RunnableConfig,
) -> Command[Literal["rag_swarm", "quiz_swarm", "feedback_swarm"]]:
    """Classifies the student's intent and routes to the correct swarm."""
    llm = RoundRobinLLM.for_role(
        "orchestrator", 
        temperature=0.3, 
        top_p=0.95, 
        top_k=64, 
        schema=OrchestratorOutput
    )
    original = state["original_query"]
    
    history = trim_messages(
        state["messages"],
        strategy="last",
        token_counter=len,
        max_tokens=10000,
        start_on="human",
        include_system=False,
    )

    feedback_list = state.get("critic_feedback", [])
    feedback_text = "\n".join([f"- {f}" for f in feedback_list]) if feedback_list else "No previous issues detected."

    try:
        prompt_value = await ORCHESTRATOR_PROMPT.ainvoke({
            "history": history, 
            "question": original,
            "critic_feedback": feedback_text
        })
        prompt_msgs = prompt_value.to_messages()

        if isinstance(prompt_msgs[-1].content, str):
            prompt_msgs[-1].content += "\n\n### REASONING INSTRUCTION\nBegin with <|thought|> to analyze intent and context before routing."
            
        result_raw = await llm.ainvoke(prompt_msgs, config=config)
        result: OrchestratorOutput = result_raw["parsed"]
        task = result.task
        difficulty = result.difficulty
        topic_source = result.topic_source
    except Exception as exc:
        logger.warning("Orchestrator failed: %s", exc)
        return Command(goto="integrity_guard", update={"task": "safety_fallback"})

    update_state = {
        "task": task,
        "difficulty": difficulty,
        "quiz_topic_source": topic_source,
        "agent_thoughts": [{
            "node": "orchestrator",
            "summary": f"Detected intent: {task}. Routing to {task}_swarm.",
            "data": {"task": task, "difficulty": difficulty}
        }]
    }

    return Command(
        goto=f"{task}_swarm",
        update=update_state
    )
