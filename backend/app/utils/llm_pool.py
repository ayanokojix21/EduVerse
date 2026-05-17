"""
app/utils/llm_pool.py
─────────────────────
Resilient LLM Orchestrator — Cloud Gemma 4 Edition.

Live Path: Gemma 4 via Google AI Studio (cloud)
Background Path: Gemini 2.5 Pro for DPO distillation
"""
import logging
from typing import Optional, Type, TypeVar, Any

from langchain_core.language_models import BaseChatModel
from langchain_core.runnables import Runnable
from pydantic import BaseModel

from app.config import get_settings

logger = logging.getLogger(__name__)

T = TypeVar("T", bound=BaseModel)


class LLMFactory:
    """Singleton factory that returns provider-agnostic, role-specific LLM chains."""
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(LLMFactory, cls).__new__(cls)
        return cls._instance

    @classmethod
    def for_role(
        cls,
        role: str,
        temperature: float = 0.1,
        top_p: float = 0.9,
        top_k: int = 40,
        streaming: bool = False,
        schema: Type[T] | None = None,
        vision: bool = False,
    ) -> Runnable:
        """Returns a Cloud Gemma 4 chain for the live chat path."""
        factory = cls()
        return factory._build_cloud_chain(role, temperature, top_p, top_k, streaming, schema, vision)

    def _build_teacher_chain(
        self,
        role: str,
        temperature: float,
        schema: Optional[Type[T]] = None,
    ) -> Runnable:
        """
        Cloud Teacher Model for DPO distillation.
        Uses Gemini 2.5 Pro for grading student-model outputs.
        """
        from langchain_google_genai import ChatGoogleGenerativeAI
        settings = get_settings()

        llm = ChatGoogleGenerativeAI(
            model=settings.eval_judge_model,
            google_api_key=settings.google_api_key,
            temperature=temperature,
        )
        return llm.with_structured_output(schema, include_raw=True) if schema else llm

    def _build_cloud_chain(
        self,
        role: str,
        temperature: float,
        top_p: float = 0.9,
        top_k: int = 40,
        streaming: bool = False,
        schema: Optional[Type[T]] = None,
        vision: bool = False,
    ) -> Runnable:
        """Builds a Cloud Gemma 4 chain via Google AI Studio.
        
        Dynamically routes to the optimal Gemma 4 variant based on the agent's role
        to balance latency and deep reasoning capabilities.
        """
        from langchain_google_genai import ChatGoogleGenerativeAI
        settings = get_settings()

        if vision:
            model_name = settings.gemma_fast_reasoning_model
            logger.info("Multimodal request: Routing to fast reasoning model %s", model_name)
        elif role in ["orchestrator", "guardrails"]:
            model_name = settings.gemma_routing_model
        elif role in ["quiz", "critic"]:
            model_name = settings.gemma_fast_reasoning_model
        else:
            model_name = settings.gemma_heavy_reasoning_model

        primary_llm = ChatGoogleGenerativeAI(
            model=model_name,
            google_api_key=settings.google_api_key,
            temperature=temperature,
            top_p=top_p,
            top_k=top_k,
            streaming=streaming,
        )

        # ── Fallback to stable Gemini models if Gemma 500s ────────────────────
        fallback_model = "gemini-1.5-flash" if role not in ["orchestrator", "guardrails", "quiz", "critic"] or vision else "gemini-flash-latest"
        fallback_llm = ChatGoogleGenerativeAI(
            model=fallback_model,
            google_api_key=settings.google_api_key,
            temperature=temperature,
            top_p=top_p,
            top_k=top_k,
            streaming=streaming,
        )

        if schema:
            primary_chain = primary_llm.with_structured_output(schema, include_raw=True)
            fallback_chain = fallback_llm.with_structured_output(schema, include_raw=True)
            return primary_chain.with_fallbacks([fallback_chain])
        
        return primary_llm.with_fallbacks([fallback_llm])


# Backward compatibility alias
RoundRobinLLM = LLMFactory

