"""
Groq Round-Robin LLM Factory with Automatic Fallback

Provides ``get_llm(role)`` — returns a ChatGroq instance that automatically
retries across a priority-ordered pool of models when any single model hits
a 429 or 500.

Model pools are partitioned by role:
  - ``structured``  : agents that use with_structured_output / JSON mode
                      (supervisor, query_rewriter, critic)
  - ``chat``        : streaming chat agents (tutor_a, tutor_b, synthesizer)
  - ``fast``        : lightweight classification where speed > quality

Why round-robin + fallback instead of a single model?
------------------------------------------------------
Groq's free tier enforces per-model TPM/RPM limits.  With 6 LLM calls per
user request running nearly simultaneously the limit is hit almost every turn.
By spreading calls across multiple model IDs, the effective throughput is
multiplied proportionally to the number of models in the pool.

The fallback chain (429 / 500 → next model) means a temporarily saturated
model is transparently replaced mid-chain.

Implementation notes
---------------------
* ``_RoundRobinGroq`` wraps standard ChatGroq and intercepts
  ``invoke`` / ``ainvoke`` to retry on RateLimitError / InternalServerError.
* The pool index is stored at the class level so load is spread across
  requests, not just within a single request.
* Thread-safe for asyncio (asyncio is single-threaded; index increments
  are safe without locks).
"""
from __future__ import annotations

import asyncio
import logging
from itertools import cycle
from typing import Any

from groq import RateLimitError, InternalServerError
from langchain_core.messages import BaseMessage
from langchain_core.runnables import RunnableConfig
from langchain_groq import ChatGroq

from app.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


# ── Model pools ───────────────────────────────────────────────────────────────
# Only models confirmed to work with JSON mode / structured output
# (tested via the Groq /models endpoint with response_format: json_object)

_STRUCTURED_POOL = [
    "llama-3.3-70b-versatile",
    "meta-llama/llama-4-scout-17b-16e-instruct",
    "moonshotai/kimi-k2-instruct",
    "llama-3.1-8b-instant",               # fallback: smaller but capable
]

_CHAT_POOL = [
    "openai/gpt-oss-120b",                 # highest quality — try first
    "llama-3.3-70b-versatile",
    "moonshotai/kimi-k2-instruct",
    "meta-llama/llama-4-scout-17b-16e-instruct",
    "openai/gpt-oss-20b",
    "llama-3.1-8b-instant",               # last resort
]

_FAST_POOL = [
    "llama-3.1-8b-instant",
    "meta-llama/llama-4-scout-17b-16e-instruct",
    "openai/gpt-oss-20b",
]


# ── Core round-robin wrapper ──────────────────────────────────────────────────

class RoundRobinLLM:
    """
    Wraps a pool of ChatGroq instances and retries across them on rate-limit
    or server errors.  Presents the same ``ainvoke`` interface as ChatGroq.

    Usage::

        llm = RoundRobinLLM.for_role("chat", temperature=0.2, streaming=True)
        result = await llm.ainvoke(messages, config=config)

    Fallback chain::

        model[0] → 429/500 → model[1] → 429/500 → model[2] → ...
    """

    _pool_indices: dict[str, int] = {}   # shared across instances per pool name

    def __init__(
        self,
        pool: list[str],
        pool_name: str,
        temperature: float = 0.1,
        streaming: bool = False,
        api_key: str | None = None,
        max_retries_per_model: int = 1,
    ) -> None:
        self._pool = pool
        self._pool_name = pool_name
        self._temperature = temperature
        self._streaming = streaming
        self._api_key = api_key or settings.groq_api_key
        self._max_retries = max_retries_per_model
        # Start at next round-robin slot
        idx = RoundRobinLLM._pool_indices.get(pool_name, 0)
        RoundRobinLLM._pool_indices[pool_name] = (idx + 1) % len(pool)
        self._start_idx = idx

    def _make_llm(self, model_id: str) -> ChatGroq:
        return ChatGroq(
            model=model_id,
            temperature=self._temperature,
            api_key=self._api_key,
            streaming=self._streaming,
        )

    async def ainvoke(
        self,
        input: list[BaseMessage] | Any,
        config: RunnableConfig | None = None,
        **kwargs: Any,
    ) -> Any:
        """Try each model in round-robin order, falling back on rate-limit/500."""
        errors: list[str] = []
        n = len(self._pool)

        for i in range(n):
            model_id = self._pool[(self._start_idx + i) % n]
            llm = self._make_llm(model_id)
            try:
                logger.debug("RoundRobin[%s] → %s", self._pool_name, model_id)
                result = await llm.ainvoke(input, config=config, **kwargs)
                if i > 0:
                    logger.info(
                        "RoundRobin[%s] succeeded on %s after %d fallback(s)",
                        self._pool_name, model_id, i,
                    )
                return result
            except (RateLimitError, InternalServerError) as exc:
                wait = 1.0 * (i + 1)
                logger.warning(
                    "RoundRobin[%s] %s failed (%s), trying next model in %.1fs",
                    self._pool_name, model_id, type(exc).__name__, wait,
                )
                errors.append(f"{model_id}: {exc}")
                await asyncio.sleep(wait)

        # All pool members exhausted
        raise RuntimeError(
            f"All {n} models in pool '{self._pool_name}' failed:\n"
            + "\n".join(errors)
        )

    def with_structured_output(self, schema: Any, **kwargs: Any) -> "StructuredRoundRobinLLM":
        """Return a structured-output wrapper that round-robins on fallback."""
        return StructuredRoundRobinLLM(
            pool=self._pool,
            pool_name=self._pool_name,
            schema=schema,
            temperature=self._temperature,
            api_key=self._api_key,
            **kwargs,
        )

    @classmethod
    def for_role(
        cls,
        role: str,
        temperature: float = 0.1,
        streaming: bool = False,
    ) -> "RoundRobinLLM":
        """
        Factory.  ``role`` is one of:
          ``"structured"`` — JSON / tool-use agents
          ``"chat"``       — streaming generation agents
          ``"fast"``       — lightweight classification
        """
        pools = {
            "structured": _STRUCTURED_POOL,
            "chat": _CHAT_POOL,
            "fast": _FAST_POOL,
        }
        if role not in pools:
            raise ValueError(f"Unknown role '{role}'. Choose: {list(pools)}")
        return cls(
            pool=pools[role],
            pool_name=role,
            temperature=temperature,
            streaming=streaming,
        )


class StructuredRoundRobinLLM:
    """
    Like RoundRobinLLM but wraps each attempt with ``with_structured_output``.
    Used by supervisor, query_rewriter, and critic.
    """

    def __init__(
        self,
        pool: list[str],
        pool_name: str,
        schema: Any,
        temperature: float = 0.0,
        api_key: str | None = None,
        **schema_kwargs: Any,
    ) -> None:
        self._pool = pool
        self._pool_name = pool_name
        self._schema = schema
        self._schema_kwargs = schema_kwargs
        self._temperature = temperature
        self._api_key = api_key or settings.groq_api_key
        idx = RoundRobinLLM._pool_indices.get(f"{pool_name}_structured", 0)
        RoundRobinLLM._pool_indices[f"{pool_name}_structured"] = (idx + 1) % len(pool)
        self._start_idx = idx

    async def ainvoke(
        self,
        input: Any,
        config: RunnableConfig | None = None,
        **kwargs: Any,
    ) -> Any:
        errors: list[str] = []
        n = len(self._pool)

        for i in range(n):
            model_id = self._pool[(self._start_idx + i) % n]
            llm = ChatGroq(
                model=model_id,
                temperature=self._temperature,
                api_key=self._api_key,
            ).with_structured_output(self._schema, **self._schema_kwargs)
            try:
                logger.debug("StructuredRR[%s] → %s", self._pool_name, model_id)
                result = await llm.ainvoke(input, config=config, **kwargs)
                if i > 0:
                    logger.info(
                        "StructuredRR[%s] succeeded on %s after %d fallback(s)",
                        self._pool_name, model_id, i,
                    )
                return result
            except (RateLimitError, InternalServerError) as exc:
                wait = 1.0 * (i + 1)
                logger.warning(
                    "StructuredRR[%s] %s failed (%s), trying next in %.1fs",
                    self._pool_name, model_id, type(exc).__name__, wait,
                )
                errors.append(f"{model_id}: {exc}")
                await asyncio.sleep(wait)

        raise RuntimeError(
            f"All {n} structured models in pool '{self._pool_name}' failed:\n"
            + "\n".join(errors)
        )
