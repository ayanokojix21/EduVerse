from __future__ import annotations

from hashlib import sha1

from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter


def _stable_source_doc_id(doc: Document, user_id: str) -> str:
    metadata = dict(doc.metadata or {})
    base_id = (
        metadata.get("alternate_link")
        or metadata.get("item_id")
        or metadata.get("id")
        or metadata.get("title")
        or doc.page_content[:120]
    )
    course_id = metadata.get("course_id", "")
    raw = f"{user_id}:{course_id}:{base_id}"
    return sha1(raw.encode("utf-8")).hexdigest()


def chunk_documents(
    documents: list[Document],
    user_id: str,
    parent_chunk_size: int,
    child_chunk_size: int,
    chunk_overlap: int,
) -> tuple[list[Document], list[Document]]:
    parent_splitter = RecursiveCharacterTextSplitter(
        chunk_size=parent_chunk_size,
        chunk_overlap=chunk_overlap,
    )
    child_splitter = RecursiveCharacterTextSplitter(
        chunk_size=child_chunk_size,
        chunk_overlap=chunk_overlap,
    )

    parent_chunks: list[Document] = []
    child_chunks: list[Document] = []

    for source_doc in documents:
        source_doc_id = _stable_source_doc_id(source_doc, user_id)
        split_parents = parent_splitter.split_documents([source_doc])

        for parent_idx, parent in enumerate(split_parents):
            parent_raw = f"{source_doc_id}:parent:{parent_idx}:{parent.page_content}"
            parent_id = sha1(parent_raw.encode("utf-8")).hexdigest()

            parent_metadata = dict(parent.metadata or {})
            parent_metadata["source_doc_id"] = source_doc_id
            parent_metadata["parent_id"] = parent_id
            parent.metadata = parent_metadata
            parent_chunks.append(parent)

            split_children = child_splitter.split_documents([parent])
            for child_idx, child in enumerate(split_children):
                child_metadata = dict(child.metadata or {})
                child_metadata["source_doc_id"] = source_doc_id
                child_metadata["parent_id"] = parent_id
                child_metadata["source_id"] = f"{parent_id}:child:{child_idx}"
                child.metadata = child_metadata
                child_chunks.append(child)

    return parent_chunks, child_chunks
