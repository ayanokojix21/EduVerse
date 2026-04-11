"""
Web fallback — fires when the top cross-encoder reranker score falls below
the classroom-grounded threshold, indicating the corpus doesn't cover the
student's question well enough.

Fallback strategy
-----------------
1. If ``top_reranker_score >= TAVILY_THRESHOLD`` → **CLASSROOM_GROUNDED**
   (no web search at all).
2. If below threshold and daily Tavily quota not exceeded → call **Tavily**.
3. If Tavily quota exceeded → fall back to **DuckDuckGo** (free, unlimited).
4. ``retrieval_label`` reflects which path was taken.

Tavily quota
------------
A daily counter is stored in a ``tavily_usage`` MongoDB collection
(``{date: "YYYY-MM-DD", count: N}``).  The counter is atomically
incremented before each Tavily call.  If count exceeds
``settings.tavily_daily_limit``, DuckDuckGo is used instead.
"""
from __future__ import annotations

import logging
from datetime import date
from typing import Any

from motor.motor_asyncio import AsyncIOMotorDatabase

from app.config import Settings, get_settings

logger = logging.getLogger(__name__)


def _today() -> str:
    return date.today().isoformat()


async def _increment_tavily_counter(db: AsyncIOMotorDatabase, settings: Settings) -> int:
    """Atomically increment the daily Tavily counter and return the new value."""
    doc = await db[settings.mongo_tavily_usage_collection].find_one_and_update(
        {"date": _today()},
        {"$inc": {"count": 1}},
        upsert=True,
        return_document=True,
    )
    return int(doc["count"])


async def _tavily_search(query: str, settings: Settings) -> list[dict[str, Any]]:
    """Call Tavily API and return normalised result dicts."""
    from tavily import TavilyClient  # type: ignore[import-untyped]

    client = TavilyClient(api_key=settings.tavily_api_key)
    # Tavily's sync API; run in a thread so we don't block the event loop.
    import anyio
    response = await anyio.to_thread.run_sync(
        lambda: client.search(query, max_results=4)
    )
    results = response.get("results", [])
    return [
        {
            "content": r.get("content", ""),
            "title": r.get("title", ""),
            "url": r.get("url", ""),
            "source": "tavily",
        }
        for r in results
    ]


async def _duckduckgo_search(query: str) -> list[dict[str, Any]]:
    """Call DuckDuckGo search (free, no quota)."""
    try:
        from duckduckgo_search import DDGS  # type: ignore[import-untyped]
        import anyio

        results = await anyio.to_thread.run_sync(
            lambda: list(DDGS().text(query, max_results=4))
        )
        return [
            {
                "content": r.get("body", ""),
                "title": r.get("title", ""),
                "url": r.get("href", ""),
                "source": "duckduckgo",
            }
            for r in results
        ]
    except Exception as exc:  # noqa: BLE001
        logger.warning("DuckDuckGo search failed: %s", exc)
        return []


async def apply_web_fallback(
    query: str,
    top_reranker_score: float,
    db: AsyncIOMotorDatabase,
    settings: Settings | None = None,
) -> tuple[list[dict[str, Any]], str]:
    """
    Decide whether to fire a web search and return results + retrieval label.

    Parameters
    ----------
    query:
        The student's original question (not the rewritten retrieval query).
    top_reranker_score:
        The highest reranker logit score from the cross-encoder step.
    db:
        Motor async database handle (used for Tavily quota counter).

    Returns
    -------
    (web_docs, retrieval_label)

    ``retrieval_label`` is one of:

    * ``"CLASSROOM_GROUNDED"`` — corpus score ≥ threshold; no web search.
    * ``"CLASSROOM_PARTIAL_WEB"`` — medium confidence; web supplements
      classroom content.
    * ``"WEB_ONLY"`` — very low classroom score; answer relies on web.
    """
    resolved = settings or get_settings()

    # No web search needed — classroom corpus has a strong match.
    if top_reranker_score >= resolved.tavily_threshold:
        return [], "CLASSROOM_GROUNDED"

    # Determine retrieval label before fetching web results.
    retrieval_label = (
        "WEB_ONLY" if top_reranker_score < 0.10 else "CLASSROOM_PARTIAL_WEB"
    )

    logger.info(
        "Web fallback triggered — top_score=%.3f label=%s",
        top_reranker_score,
        retrieval_label,
    )

    # Try Tavily first (quota-guarded).
    if resolved.tavily_api_key:
        try:
            count = await _increment_tavily_counter(db, resolved)
            if count <= resolved.tavily_daily_limit:
                web_docs = await _tavily_search(query, resolved)
                if web_docs:
                    return web_docs, retrieval_label
        except Exception as exc:  # noqa: BLE001
            logger.warning("Tavily search failed, falling back to DuckDuckGo: %s", exc)

    # Fall back to DuckDuckGo (free, no quota).
    web_docs = await _duckduckgo_search(query)
    return web_docs, retrieval_label
