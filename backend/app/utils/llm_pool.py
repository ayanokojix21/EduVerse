import logging
from typing import Any, Type, TypeVar

from langchain_core.language_models import BaseChatModel
from langchain_core.runnables import Runnable
from langchain_groq import ChatGroq
from pydantic import BaseModel

from app.config import get_settings

logger = logging.getLogger(__name__)

T = TypeVar("T", bound=BaseModel)

# ── Text-only fallback pools (ordered: best quality → fastest) ────────────────

# For structured output: supervisor, critic — must support JSON mode reliably
_STRUCTURED_POOL = [
    "llama-3.3-70b-versatile",   # Primary: production 70B, rock-solid JSON
    "openai/gpt-oss-20b",        # Fallback 1: OpenAI-grade quality, 20B
    "qwen/qwen3-32b",            # Fallback 2: strong reasoning, 32B
    "llama-3.1-8b-instant",      # Fallback 3: ultra-fast safety net
]

# For heavy synthesis: tutor, synthesizer — needs max quality
_CHAT_POOL = [
    "openai/gpt-oss-120b",       # Primary: most capable on Groq
    "llama-3.3-70b-versatile",   # Fallback 1: production 70B
    "openai/gpt-oss-20b",        # Fallback 2: balanced quality
    "qwen/qwen3-32b",            # Fallback 3: preview reasoning
    "llama-3.1-8b-instant",      # Fallback 4: last resort fast
]

# For fast tasks: rewriter, supervisor — minimize TTFT
_FAST_POOL = [
    "llama-3.1-8b-instant",      # Primary: fastest production model
    "openai/gpt-oss-20b",        # Fallback 1: lightweight quality
    "llama-3.3-70b-versatile",   # Fallback 2: reliable last resort
]


class RoundRobinLLM:
    """
    Factory class that returns a native LangChain RunnableWithFallbacks.
    Spreads load across high-quality Groq endpoints to maximize throughput.
    """
    _pool_indices: dict[str, int] = {}
    _cache: dict[str, Runnable] = {}

    @classmethod
    def for_role(
        cls,
        role: str,
        temperature: float = 0.1,
        streaming: bool = False,
        schema: Type[T] | None = None
    ) -> Runnable:
        """
        Build a resilient LLM runnable for a specific agent role.
        """
        # Create a unique cache key based on params
        cache_key = f"{role}_{temperature}_{streaming}_{schema.__name__ if schema else 'none'}"
        if cache_key in cls._cache:
            return cls._cache[cache_key]

        pools = {
            "structured": _STRUCTURED_POOL,
            "chat": _CHAT_POOL,
            "fast": _FAST_POOL,
        }
        if role not in pools:
            raise ValueError(f"Unknown role '{role}'. Choose from: {list(pools.keys())}")

        pool = pools[role]
        settings = get_settings()

        # 1. Rotate the array to spread load
        idx = cls._pool_indices.get(role, 0)
        cls._pool_indices[role] = (idx + 1) % len(pool)
        reordered_pool = pool[idx:] + pool[:idx]

        def _build_model(model_id: str) -> BaseChatModel:
            llm = ChatGroq(
                model=model_id,
                temperature=temperature,
                streaming=streaming,
                api_key=settings.groq_api_key
            )
            if schema:
                return llm.with_structured_output(schema)
            return llm

        # 2. Construct Primary and Native Fallbacks
        primary_llm = _build_model(reordered_pool[0])
        fallbacks = [_build_model(m) for m in reordered_pool[1:]]

        runnable = primary_llm.with_fallbacks(fallbacks)
        cls._cache[cache_key] = runnable
        return runnable

    @classmethod
    async def warm_up(cls):
        """
        Prime the connection pools by dry-running the most critical LLM roles.
        Eliminates the 'first message hang' (initial SDK initialization).
        """
        logger.info("Warming up LLM pools...")
        
        # 1. Warm up the chat pool (main response engine)
        chat_llm = cls.for_role("chat", streaming=True)
        # Small background task to establish HTTPS
        try:
            await chat_llm.ainvoke("ping") 
        except Exception as e:
            logger.warning("LLM Warm-up heartbeat skipped: %s", e)

        # 2. Warm up the structured pool
        class WarmupSchema(BaseModel): 
            status: str
        
        try:
            struct_llm = cls.for_role("structured", schema=WarmupSchema)
        except Exception:
            pass

        logger.info("LLM pools primed.")
