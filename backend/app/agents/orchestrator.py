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
from app.utils.thinking_utils import build_thought, extract_thinking, normalize_content
from app.agents.prompts.orchestrator import ORCHESTRATOR_PROMPT
from app.agents.schemas.orchestrator import OrchestratorOutput

logger = logging.getLogger(__name__)


@traceable(name="orchestrator")
async def orchestrator_node(
    state: AgentState,
    config: RunnableConfig,
) -> Command[Literal["rag_swarm", "quiz_swarm", "feedback_swarm"]]:
    """Classifies the student's intent and routes to the correct swarm."""
    # Safety check: ensure image_data is not a short placeholder like "string" or empty
    image_data = state.get("image_data")
    is_multi = state.get("is_multimodal", False) and image_data and len(image_data) > 20
    llm = RoundRobinLLM.for_role(
        "orchestrator", 
        temperature=0.3, 
        top_p=0.95, 
        top_k=64, 
        schema=OrchestratorOutput,
        vision=is_multi
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

    logger.info("====== ORCHESTRATOR NODE STARTED ======")
    logger.info(f"Original Query: {state.get('original_query', '')}")
    logger.info(f"Is Multimodal: {is_multi}")
    logger.info(f"Critic Feedback: {feedback_text}")
    
    try:
        prompt_value = await ORCHESTRATOR_PROMPT.ainvoke({
            "history": history, 
            "question": original,
            "critic_feedback": feedback_text
        })
        prompt_msgs = prompt_value.to_messages()
        
        reasoning_trigger = "\n\n### REASONING INSTRUCTION\nThink step-by-step to analyze intent and context before routing."

        if is_multi:
            from langchain_core.messages import HumanMessage
            last_msg = prompt_msgs[-1]
            text_content = (last_msg.content if isinstance(last_msg.content, str) else "") + reasoning_trigger
            
            mm_content = [
                {"type": "text", "text": text_content}, 
                {
                    "type": "image_url",
                    "image_url": {"url": f"data:{state.get('image_mimetype', 'image/png')};base64,{state['image_data']}"}
                }
            ]
            prompt_msgs[-1] = HumanMessage(content=mm_content)
        else:
            if isinstance(prompt_msgs[-1].content, str):
                prompt_msgs[-1].content += reasoning_trigger
            
        logger.info("Invoking Orchestrator LLM...")
        result_raw = await llm.ainvoke(prompt_msgs, config=config)
        logger.info(f"Orchestrator LLM Result: {result_raw}")
        
        # Extract thinking for the "Show Thinking" UI
        raw_content = normalize_content(
            result_raw["raw"].content if isinstance(result_raw, dict) and "raw" in result_raw 
            else str(result_raw)
        )
        thinking_text = extract_thinking(raw_content)
        
        result: OrchestratorOutput = result_raw["parsed"]
        task = result.task
        difficulty = result.difficulty
        topic_source = result.topic_source
        logger.info(f"Parsed Routing Decision -> Task: {task}, Difficulty: {difficulty}, Source: {topic_source}")
    except Exception as exc:
        logger.exception("Orchestrator failed with a critical error: %s", exc)
        task = "rag"
        difficulty = "medium"
        topic_source = "course_material"
        thinking_text = ""
        logger.info(f"Falling back to Default Routing -> Task: {task}")

    update_state = {
        "task": task,
        "difficulty": difficulty,
        "quiz_topic_source": topic_source,
        "agent_thoughts": [build_thought(
            node="orchestrator",
            summary=f"Routing to {task.replace('_', ' ').title()} Pipeline",
            reasoning=thinking_text or f"Detected intent: {task}. Difficulty: {difficulty}. Routing to {task}_swarm.",
            data={"task": task, "difficulty": difficulty},
        )],
    }

    logger.info(f"====== ORCHESTRATOR NODE COMPLETED. GOTO: {task}_swarm ======")

    return Command(
        goto=f"{task}_swarm",
        update=update_state
    )
