"""
backend/app/agents/guardrails.py
──────────────────────────────
The Ethical Sentry of EduVerse.
Implements input/output moderation and Academic Integrity (AI) enforcement.
"""
import logging
from typing import Literal

from langgraph.graph import END
from langgraph.types import Command
from app.agents.state import AgentState
from app.utils.llm_pool import RoundRobinLLM

logger = logging.getLogger(__name__)

class Guardrails:
    """Uses Gemma 4 Native Safety Alignment to protect the educational environment."""

    @staticmethod
    async def input_moderator(state: AgentState) -> Command[Literal["integrity_guard", "__end__"]]:
        """
        Gates the entire graph. Detects:
        1. Prompt Injection (Jailbreaking)
        2. Inappropriate Content (NSFW/Violence)
        3. PII Leaks
        """
        last_message = state["messages"][-1].content
        from app.agents.schemas.guardrails import SafetyOutput
        llm = RoundRobinLLM.for_role(
            "critic", 
            temperature=0.2, 
            top_p=0.95, 
            top_k=64,
            schema=SafetyOutput
        ) 
        
        from app.agents.prompts.guardrails import INPUT_MODERATOR_PROMPT, REFUSAL_PROMPT
        
        prompt_msgs = INPUT_MODERATOR_PROMPT.format_messages(query=last_message)
        if isinstance(prompt_msgs[-1].content, str):
            prompt_msgs[-1].content += "\n\n### REASONING INSTRUCTION\nBegin with <|thought|> to analyze query safety."

        res_raw = await llm.ainvoke(prompt_msgs)
        res: SafetyOutput = res_raw["parsed"]
        raw_text = res_raw["raw"].content if hasattr(res_raw["raw"], "content") else str(res_raw["raw"])
        update_state = {"safety_raw_responses": [raw_text]}
        
        if res.decision == "UNSAFE":
            logger.warning(f"Native Safeguard Triggered: {res.reason}")
            refusal_llm = RoundRobinLLM.for_role("tutor", temperature=0.7, top_p=0.95, top_k=50)
            refusal_res = await refusal_llm.ainvoke(REFUSAL_PROMPT.format_messages(query=last_message))
            refusal_msg = refusal_res.content if hasattr(refusal_res, "content") else str(refusal_res)

            return Command(goto=END, update={**update_state, "response_text": refusal_msg})
            
        return Command(goto="integrity_guard", update=update_state)

    @staticmethod
    async def academic_integrity_check(state: AgentState) -> Command[Literal["orchestrator", "__end__"]]:
        """Detects if the student is merely asking for the answer (cheating)."""
        query = state["original_query"]
        from app.agents.schemas.guardrails import IntegrityOutput
        llm = RoundRobinLLM.for_role(
            "critic", 
            temperature=0.2, 
            top_p=0.95, 
            top_k=64,
            schema=IntegrityOutput
        )
        
        from app.agents.prompts.guardrails import ACADEMIC_INTEGRITY_PROMPT
        prompt_msgs = ACADEMIC_INTEGRITY_PROMPT.format_messages(query=query)
        if isinstance(prompt_msgs[-1].content, str):
            prompt_msgs[-1].content += "\n\n### REASONING INSTRUCTION\nBegin with <|thought|> to analyze student intent."

        res_raw = await llm.ainvoke(prompt_msgs)
        res: IntegrityOutput = res_raw["parsed"]
        raw_text = res_raw["raw"].content if hasattr(res_raw["raw"], "content") else str(res_raw["raw"])
        update_state = {"safety_raw_responses": [raw_text]}
        
        if res.decision == "Refusal":
            from app.agents.prompts.guardrails import REFUSAL_PROMPT
            
            refusal_llm = RoundRobinLLM.for_role(
                "tutor", 
                temperature=0.7, 
                top_p=0.95, 
                top_k=50
            )
            refusal_res = await refusal_llm.ainvoke(REFUSAL_PROMPT.format_messages(query=query))
            refusal_msg = refusal_res.content if hasattr(refusal_res, "content") else str(refusal_res)
            
            return Command(goto=END, update={**update_state, "response_text": refusal_msg})
        
        return Command(goto="orchestrator", update=update_state)

    @staticmethod
    async def output_moderator(state: AgentState) -> dict:
        """Verifies the final response is safe, Socratic, and free of PII leaks."""
        response = state.get("response_text", "")
        if not response: 
            return {}

        from app.agents.schemas.guardrails import OutputShieldOutput
        llm = RoundRobinLLM.for_role(
            "critic", 
            temperature=0.2, 
            top_p=0.95, 
            top_k=64,
            schema=OutputShieldOutput
        )
        
        from app.agents.prompts.guardrails import OUTPUT_SHIELD_PROMPT, REFUSAL_PROMPT
        
        prompt_msgs = OUTPUT_SHIELD_PROMPT.format_messages(response=response)
        if isinstance(prompt_msgs[-1].content, str):
            prompt_msgs[-1].content += "\n\n### REASONING INSTRUCTION\nBegin with <|thought|> to verify output quality."

        try:
            res_raw = await llm.ainvoke(prompt_msgs)
            res: OutputShieldOutput = res_raw["parsed"]
            if res.decision == "REDACTED":
                logger.warning(f"Output Shield Triggered: {res.reason}")
                reason = res.reason or "Academic Integrity violation detected."
                
                refusal_llm = RoundRobinLLM.for_role(
                    "tutor", 
                    temperature=0.7, 
                    top_p=0.95, 
                    top_k=50
                )
                refusal_res = await refusal_llm.ainvoke(REFUSAL_PROMPT.format_messages(query=reason))

                return {
                    "response_text": refusal_res.content,
                    "agent_thoughts": [{
                        "node": "output_moderator",
                        "summary": f"Redacted: {reason}"
                    }]
                }
        except Exception as exc:
            logger.error(f"Output moderator failed: {exc}")
        
        return {}
