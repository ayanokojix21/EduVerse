"""
app/services/eval_engine.py
──────────────────────────
Quality Gate — Teacher-as-a-Judge Evaluation.

Uses Gemini 2.5 Pro (or local Gemma 4 fallback) to audit fine-tuned model
performance on golden benchmarks. Runs ONLY in background training pipeline.
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Tuple

from langchain_core.messages import HumanMessage, SystemMessage

from app.utils.llm_pool import LLMFactory
from app.config import get_settings

logger = logging.getLogger(__name__)


from app.agents.schemas.judge import JudgeOutput

class EvalService:
    """
    Automated benchmark scorer.
    Implements the 'Golden Set' quality gate for autonomous model promotion.
    """

    def __init__(self):
        self.settings = get_settings()
        self.judge = LLMFactory()._build_teacher_chain("critic", temperature=0.0, schema=JudgeOutput)

    async def score_responses(
        self,
        prompts: List[str],
        responses_base: List[str],
        responses_new: List[str],
        role: str,
    ) -> Dict[str, Any]:
        """
        Performs pairwise side-by-side evaluation (Judge-as-a-Teacher).
        Returns aggregated win rates and safety scores.
        """
        results = []
        wins_new = 0
        total_score_base = 0.0
        total_score_new = 0.0

        for prompt, res_base, res_new in zip(prompts, responses_base, responses_new):
            score_base, score_new, critique = await self._judge_pair(prompt, res_base, res_new, role)

            results.append({
                "prompt": prompt,
                "score_base": score_base,
                "score_new": score_new,
                "critique": critique,
            })

            total_score_base += score_base
            total_score_new += score_new
            if score_new > score_base:
                wins_new += 1

        n = len(prompts) if prompts else 1
        avg_base = total_score_base / n
        avg_new = total_score_new / n

        return {
            "avg_base": avg_base,
            "avg_new": avg_new,
            "win_rate_new": wins_new / n,
            "improvement_pct": (avg_new - avg_base) / avg_base if avg_base > 0 else 0,
            "passed_gate": avg_new >= avg_base * (1 + self.settings.improvement_threshold),
            "detailed_results": results,
        }

    async def _judge_pair(
        self,
        prompt: str,
        res_a: str,
        res_b: str,
        role: str,
    ) -> Tuple[float, float, str]:
        """Uses the Teacher model to compare two responses based on pedagogical rubric."""

        system_prompt = f"""
        You are an expert Instructional Coach evaluating a {role} AI agent.
        Evaluate the following two responses (A and B) to a student query.

        RUBRIC for {role}:
        1. Factual Grounding (1-10): Is it grounded in pedagogical standards?
        2. Clarity (1-10): Is it easy for a student to understand?
        3. Tone (1-10): Does it use a growth-mindset, patient tone?
        4. No Hallucinations: Zero tolerance for made-up facts.
        """

        user_content = f"STUDENT PROMPT: {prompt}\n\nRESPONSE A:\n{res_a}\n\nRESPONSE B:\n{res_b}"

        try:
            res_raw = await self.judge.ainvoke([
                SystemMessage(content=system_prompt),
                HumanMessage(content=user_content),
            ])
            
            if isinstance(res_raw, dict) and "parsed" in res_raw:
                data: JudgeOutput = res_raw["parsed"]
            elif hasattr(res_raw, "parsed"):
                data = res_raw.parsed
            else:
                logger.warning("Judge returned non-structured output, skipping.")
                return (0.0, 0.0, "Judging failed: Non-structured output")

            return (
                float(data.score_a),
                float(data.score_b),
                data.reasoning,
            )
        except Exception as e:
            logger.error("Judging failed: %s", e)
            return (0.0, 0.0, f"Judge Error: {e}")
