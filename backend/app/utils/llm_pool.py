"""
app/utils/llm_pool.py
─────────────────────
Resilient LLM Orchestrator — Gemma 4 Local-First Edition.

Live Path: 100% Local via Ollama (Gemma 4 E4B)
Background Path: Cloud Teacher (Gemini 2.5 Pro) for DPO distillation only
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
        """Returns a 100% Local Gemma 4 chain for the live chat path."""
        factory = cls()

        if vision:
            return factory._build_local_vision_chain(role, temperature, top_p, top_k, streaming, schema)

        return factory._build_local_chain(role, temperature, top_p, top_k, streaming, schema)

    def _build_teacher_chain(
        self,
        role: str,
        temperature: float,
        schema: Optional[Type[T]] = None,
    ) -> Runnable:
        """
        INTERNAL USE ONLY — Cloud Teacher Model for DPO distillation.
        Uses Gemini 2.5 Pro if API key present, falls back to local Gemma 4.
        Never called on the live student-facing path.
        """
        settings = get_settings()

        if settings.has_google_api:
            try:
                from langchain_google_genai import ChatGoogleGenerativeAI

                llm = ChatGoogleGenerativeAI(
                    model=settings.eval_judge_model,
                    google_api_key=settings.google_api_key,
                    temperature=temperature,
                )
                return llm.with_structured_output(schema, include_raw=True) if schema else llm
            except Exception as exc:
                logger.warning("Cloud Teacher init failed, falling back to local: %s", exc)

        return self._build_local_chain("critic", temperature=temperature, streaming=False, schema=schema)

    def _build_local_vision_chain(
        self,
        role: str,
        temperature: float,
        top_p: float,
        top_k: int,
        streaming: bool,
        schema: Optional[Type[T]],
    ) -> Runnable:
        """Builds a local Ollama vision chain using Gemma 4 E4B native multimodality."""
        from langchain_ollama import ChatOllama

        settings = get_settings()
        model_id = settings.local_vision_model

        llm = ChatOllama(
            model=model_id,
            temperature=temperature,
            top_p=top_p,
            top_k=top_k,
            streaming=streaming,
            base_url=settings.ollama_base_url,
            num_thread=settings.local_num_threads,
            num_ctx=settings.local_context_window, 
        )
        return llm.with_structured_output(schema, include_raw=True) if schema else llm

    async def _resolve_model_id(self, role: str) -> str:
        """Dynamically determines the best model ID from Registry or Settings."""
        from app.db.mongodb import get_motor_client
        from app.db.model_registry_repository import ModelRegistryRepository
        
        settings = get_settings()
        client = get_motor_client()
        try:
            db = client[settings.mongo_db_name]
            repo = ModelRegistryRepository(db, settings)
            return await repo.get_current_model(role)
        except Exception as exc:
            logger.warning("Dynamic registry lookup failed, using settings: %s", exc)
            model_map = {
                "orchestrator": settings.local_orchestrator_model,
                "tutor": settings.local_tutor_model,
                "quiz": settings.local_quiz_model,
                "feedback": settings.local_feedback_model,
                "critic": settings.local_critic_model,
            }
            return model_map.get(role, settings.local_tutor_model)

    def _build_local_chain(
        self,
        role: str,
        temperature: float,
        top_p: float,
        top_k: int,
        streaming: bool,
        schema: Optional[Type[T]],
    ) -> Runnable:
        """Builds a JIT local Ollama chain for Gemma 4 inference."""
        from langchain_core.runnables import RunnableLambda
        from langchain_ollama import ChatOllama
        settings = get_settings()

        def _instantiate_llm(input_data: Any) -> Runnable:
            import asyncio
            model_id = asyncio.run(self._resolve_model_id(role))
            
            llm = ChatOllama(
                model=model_id,
                temperature=temperature,
                top_p=top_p,
                top_k=top_k,
                streaming=streaming,
                base_url=settings.ollama_base_url,
                num_thread=settings.local_num_threads,
                num_ctx=settings.local_context_window,
            )
            return llm.with_structured_output(schema, include_raw=True) if schema else llm

        return RunnableLambda(_instantiate_llm)


# Backward compatibility alias
RoundRobinLLM = LLMFactory
