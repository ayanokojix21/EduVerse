"""
Parent chunk fetch — retrieves full parent chunks from MongoDB given a
list of top-reranked child chunk Documents.

Why parent-child?
-----------------
* Child chunks (200 chars) are small → precise vector matches.
* Parent chunks (800 chars) contain full context → LLMs answer well.
* This step bridges the retrieval precision of small chunks with the
  context richness of large ones.
"""
from __future__ import annotations

import logging

from langchain_core.documents import Document
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.config import Settings, get_settings

logger = logging.getLogger(__name__)


async def fetch_parents(
    child_docs: list[Document],
    db: AsyncIOMotorDatabase,
    settings: Settings | None = None,
) -> list[dict]:
    """
    Batch-fetch parent chunks corresponding to *child_docs*.

    Steps
    -----
    1. Collect unique ``parent_id`` values from the reranked children,
       preserving reranker rank order (best first).
    2. Issue a single ``$in`` query against ``course_chunks_parent``.
    3. Return parents in the same order as the deduplicated parent_ids.

    Returns
    -------
    A list of MongoDB-style dicts (not LangChain Documents) with at least::

        {
            "parent_id": str,
            "content":   str,
            "metadata":  dict,
            "user_id":   str,
            "course_id": str,
        }
    """
    resolved = settings or get_settings()

    # Deduplicate while preserving reranker-rank order.
    parent_ids = list(
        dict.fromkeys(
            doc.metadata.get("parent_id", "")
            for doc in child_docs
            if doc.metadata.get("parent_id")
        )
    )

    if not parent_ids:
        logger.warning("fetch_parents called with no valid parent_ids.")
        return []

    collection = db[resolved.mongo_parent_chunks_collection]
    cursor = collection.find({"parent_id": {"$in": parent_ids}})
    raw_parents = await cursor.to_list(length=None)

    # Map for O(1) lookup
    parent_map: dict[str, dict] = {p["parent_id"]: p for p in raw_parents}

    # Return in rank order (best child → its parent first)
    ordered: list[dict] = []
    for pid in parent_ids:
        parent = parent_map.get(pid)
        if parent:
            # Remove MongoDB's internal _id to keep dicts serialisable
            parent.pop("_id", None)
            ordered.append(parent)
        else:
            logger.warning("parent_id=%s not found in collection.", pid)

    return ordered
