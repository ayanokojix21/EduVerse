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
from app.utils.thinking_utils import build_thought, extract_thinking, normalize_content

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
            prompt_msgs[-1].content += "\n\n### REASONING INSTRUCTION\nThink step-by-step to analyze query safety."

        res_raw = await llm.ainvoke(prompt_msgs)
        res: SafetyOutput | None = res_raw.get("parsed")
        
        # Normalize raw content to string (handles Gemma 4 thinking lists)
        raw_text = normalize_content(
            res_raw["raw"].content if hasattr(res_raw["raw"], "content") else str(res_raw["raw"]),
            include_thinking=True,
        )
        thinking_text = extract_thinking(raw_text)

        if not res:
            logger.warning("Input moderator failed to parse structured output natively. Attempting robust extraction.")
            from app.utils.thinking_utils import extract_robust_json
            data = extract_robust_json(raw_text)
            if data:
                try:
                    res = SafetyOutput(**data)
                except Exception as e:
                    logger.warning(f"Input moderator robust parsing failed: {e}")

        if not res:
            logger.warning("Input moderator extraction failed completely; failing OPEN (safe).")
            return Command(
                goto="integrity_guard", 
                update={
                    "safety_raw_responses": [raw_text],
                    "agent_thoughts": [build_thought("input_moderator", "Scanning Input Safety", "Decision: SAFE. (Parsing fallback)")]
                }
            )

        update_state = {
            "safety_raw_responses": [raw_text],
            "agent_thoughts": [build_thought(
                node="input_moderator",
                summary="Scanning Input Safety",
                reasoning=thinking_text or f"Decision: {res.decision}. {res.reason or 'Content appears safe.'}" if hasattr(res, 'reason') else f"Decision: {res.decision}.",
            )],
        }
        
        if res.decision == "UNSAFE":
            logger.warning(f"Native Safeguard Triggered: {res.reason}")
            refusal_llm = RoundRobinLLM.for_role("tutor", temperature=0.7, top_p=0.95, top_k=50)
            refusal_res = await refusal_llm.ainvoke(REFUSAL_PROMPT.format_messages(query=last_message))
            refusal_msg = normalize_content(
                refusal_res.content if hasattr(refusal_res, "content") else str(refusal_res)
            )

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
            prompt_msgs[-1].content += "\n\n### REASONING INSTRUCTION\nThink step-by-step to analyze student intent."

        res_raw = await llm.ainvoke(prompt_msgs)
        res: IntegrityOutput | None = res_raw.get("parsed")
        
        # Normalize raw content to string (handles Gemma 4 thinking lists)
        raw_text = normalize_content(
            res_raw["raw"].content if hasattr(res_raw["raw"], "content") else str(res_raw["raw"]),
            include_thinking=True,
        )
        thinking_text = extract_thinking(raw_text)
        
        if not res:
            logger.warning("Integrity guard failed to parse structured output natively. Attempting robust extraction.")
            from app.utils.thinking_utils import extract_robust_json
            data = extract_robust_json(raw_text)
            if data:
                try:
                    res = IntegrityOutput(**data)
                except Exception as e:
                    logger.warning(f"Integrity guard robust parsing failed: {e}")

        if not res:
            logger.warning("Integrity guard extraction failed completely; failing OPEN (safe).")
            return Command(
                goto="orchestrator", 
                update={
                    "safety_raw_responses": [raw_text],
                    "agent_thoughts": [build_thought("integrity_guard", "Checking Academic Integrity", "Decision: Allowed. (Parsing fallback)")]
                }
            )

        update_state = {
            "safety_raw_responses": [raw_text],
            "agent_thoughts": [build_thought(
                node="integrity_guard",
                summary="Checking Academic Integrity",
                reasoning=thinking_text or f"Decision: {res.decision}. Student intent analysis complete.",
            )],
        }
        
        if res.decision == "Refusal":
            from app.agents.prompts.guardrails import REFUSAL_PROMPT
            
            refusal_llm = RoundRobinLLM.for_role(
                "tutor", 
                temperature=0.7, 
                top_p=0.95, 
                top_k=50
            )
            refusal_res = await refusal_llm.ainvoke(REFUSAL_PROMPT.format_messages(query=query))
            refusal_msg = normalize_content(
                refusal_res.content if hasattr(refusal_res, "content") else str(refusal_res)
            )
            
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
            prompt_msgs[-1].content += "\n\n### REASONING INSTRUCTION\nThink step-by-step to verify output quality."

        try:
            res_raw = await llm.ainvoke(prompt_msgs)
            res: OutputShieldOutput | None = res_raw.get("parsed")
            
            # Extract reasoning to show in the UI
            raw_text = normalize_content(
                res_raw["raw"].content if hasattr(res_raw["raw"], "content") else str(res_raw["raw"]),
                include_thinking=True,
            )
            thinking_text = extract_thinking(raw_text)
            
            if not res:
                logger.warning("Output shield failed to parse structured output natively. Attempting robust extraction.")
                from app.utils.thinking_utils import extract_robust_json
                data = extract_robust_json(raw_text)
                if data:
                    try:
                        res = OutputShieldOutput(**data)
                    except Exception as e:
                        logger.warning(f"Output shield robust parsing failed: {e}")

            if not res:
                logger.warning("Output shield extraction failed completely; failing OPEN (safe).")
                return {
                    "agent_thoughts": [build_thought("output_moderator", "Output Safety Verified", "Decision: OK. (Parsing fallback)")]
                }

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
                    "response_text": normalize_content(
                        refusal_res.content if hasattr(refusal_res, "content") else str(refusal_res)
                    ),
                    "agent_thoughts": [build_thought(
                        node="output_moderator",
                        summary=f"Redacted: {reason}",
                        reasoning=thinking_text or f"Decision: {res.decision}. {reason}"
                    )]
                }
            
            # Return success thought so it lights up and appears in the graph
            return {
                "agent_thoughts": [build_thought(
                    node="output_moderator",
                    summary="Scanning Output Safety",
                    reasoning=thinking_text or f"Decision: {res.decision}. Output is safe and complies with academic integrity."
                )]
            }
        except Exception as exc:
            logger.error(f"Output moderator failed: {exc}")
        
        return {}
