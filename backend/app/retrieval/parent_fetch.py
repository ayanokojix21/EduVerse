"""
Parent chunk fetch — retrieves full parent chunks from MongoDB given a
list of top-reranked child chunk Documents.

Why parent-child?
-----------------
* Child chunks (300 chars) are small → precise vector matches.
* Parent chunks (2000 chars) contain full context → LLMs answer well.
* This step bridges the retrieval precision of small chunks with the
  context richness of large ones.

Sibling expansion
-----------------
After fetching the directly-matched parents, we also pull all OTHER
parent chunks that share the same ``source_doc_id`` (i.e. from the same
PDF / attachment).  This ensures the LLM sees the full document, not
just the single paragraph that happened to match the vector search.

Matched parents appear first (in reranker-rank order), followed by
sibling parents (in their original document order).
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
    Batch-fetch parent chunks corresponding to *child_docs*, then expand
    to include sibling parents from the same source documents.

    Steps
    -----
    1. Collect unique ``parent_id`` values from the reranked children,
       preserving reranker rank order (best first).
    2. Issue a single ``$in`` query against ``course_chunks_parent``.
    3. Identify unique ``source_doc_id`` values from the matched parents.
    4. Fetch ALL sibling parents sharing those ``source_doc_id`` values.
    5. Return matched parents first (rank-ordered), then siblings
       (document-ordered), with no duplicates.

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

    # ── Step 1: Fetch directly-matched parents ────────────────────────────
    cursor = collection.find({"parent_id": {"$in": parent_ids}})
    raw_parents = await cursor.to_list(length=None)

    # Map for O(1) lookup
    parent_map: dict[str, dict] = {p["parent_id"]: p for p in raw_parents}

    # Build the matched list in rank order (best child → its parent first)
    matched_parents: list[dict] = []
    matched_parent_ids: set[str] = set()
    for pid in parent_ids:
        parent = parent_map.get(pid)
        if parent:
            parent.pop("_id", None)
            matched_parents.append(parent)
            matched_parent_ids.add(pid)
        else:
            logger.warning("parent_id=%s not found in collection.", pid)

    # ── Step 2: Sibling expansion — fetch other parents from the same docs ─
    # Collect unique source_doc_ids from matched parents
    source_doc_ids = list(
        dict.fromkeys(
            p.get("metadata", {}).get("source_doc_id", "")
            for p in matched_parents
            if p.get("metadata", {}).get("source_doc_id")
        )
    )

    sibling_parents: list[dict] = []
    if source_doc_ids:
        sibling_cursor = collection.find({
            "metadata.source_doc_id": {"$in": source_doc_ids},
            "parent_id": {"$nin": list(matched_parent_ids)},  # exclude already-matched
        })
        raw_siblings = await sibling_cursor.to_list(length=None)

        for sib in raw_siblings:
            sib.pop("_id", None)
            sibling_parents.append(sib)

        logger.info(
            "Sibling expansion → %d extra parents from %d source docs",
            len(sibling_parents),
            len(source_doc_ids),
        )

    # Matched parents first (ranked), then siblings (document order)
    all_parents = matched_parents + sibling_parents

    logger.info(
        "fetch_parents → %d matched + %d siblings = %d total parents",
        len(matched_parents),
        len(sibling_parents),
        len(all_parents),
    )

    return all_parents
