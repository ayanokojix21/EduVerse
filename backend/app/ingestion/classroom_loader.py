from __future__ import annotations

import anyio
from langchain_core.documents import Document
from langchain_google_classroom import GoogleClassroomLoader
from google.oauth2.credentials import Credentials

from app.config import Settings, get_settings
from app.services import get_course
from app.services.groq_vision import build_vision_model

from langchain_core.documents import Document
from langchain_core.document_loaders import BaseBlobParser
from langchain_core.documents.base import Blob
from typing import Iterator, Any


class MarkdownPyMuPDFParser(BaseBlobParser):
    def __init__(self, vision_model: Any | None = None):
        self.vision_model = vision_model

    def lazy_parse(self, blob: Blob) -> Iterator[Document]:
        import fitz
        import pymupdf4llm
        import logging
        import base64
        import anyio
        logger = logging.getLogger(__name__)
        
        try:
            doc = fitz.open(stream=blob.as_bytes(), filetype="pdf")
            
            # 1. Extract content page-by-page
            chunks = pymupdf4llm.to_markdown(doc, page_chunks=True)
            
            img_count = 0
            
            for chunk in chunks:
                # 'chunk' is a dict: {'text': '...', 'metadata': {'page_number': N, ...}}
                page_idx = chunk.get("metadata", {}).get("page_number", 1) - 1
                page_text = chunk.get("text", "")
                
                # 2. Vision Enrichment for THIS page
                page_img_count = 0
                if self.vision_model and img_count < 10:
                    page = doc[page_idx]
                    image_list = page.get_images()
                    
                    for img in image_list:
                        if img_count >= 10 or page_img_count >= 2:
                            break
                        
                        xref = img[0]
                        base_image = doc.extract_image(xref)
                        
                        # SMART FILTER: Skip icons/logos (smaller than 120x120)
                        if base_image.get("width", 0) < 120 or base_image.get("height", 0) < 120:
                            continue
                            
                        image_bytes = base_image["image"]
                        b64 = base64.b64encode(image_bytes).decode("utf-8")
                        
                        try:
                            desc = anyio.from_thread.run(
                                self.vision_model.describe_image, 
                                b64, 
                                f"Analyze this figure/newspaper clipping from page {page_idx + 1} for educational context. "
                                "Identify key headlines, text labels, or historical events shown. Be concise but specific."
                            )
                            page_text += f"\n\n> [Visual Context (Page {page_idx + 1})]: {desc}\n"
                            img_count += 1
                            page_img_count += 1
                        except Exception as vision_exc:
                            logger.warning(f"Vision failed on page {page_idx+1}: {vision_exc}")

                # 3. Yield as a standalone Document for this page
                # We carefully propagate ALL blob metadata (URL, title, etc) 
                doc_metadata = dict(blob.metadata or {})
                doc_metadata.update({
                    "source": blob.source,
                    "page_number": page_idx + 1  # 1-indexed for citation
                })
                
                yield Document(
                    page_content=page_text, 
                    metadata=doc_metadata
                )

        except Exception as exc:
            logger.error(f"Failed to parse PDF from {blob.source}: {exc}")
            # Yield nothing for this blob instead of crashing

class ClassroomLoadError(Exception):
    pass


def _load_documents_sync(
    user_id: str,
    course_id: str,
    credentials: Credentials,
    settings: Settings,
) -> list[Document]:
    import logging
    logger = logging.getLogger(__name__)
    
    try:
        # Fail fast when the user cannot access the requested course.
        get_course(credentials, course_id)

        vision_model = build_vision_model(settings)

        loader = GoogleClassroomLoader(
            credentials=credentials,
            course_ids=[course_id],
            load_assignments=True,
            load_announcements=True,
            load_materials=True,
            load_attachments=True,
            parse_attachments=True,
            load_images=bool(vision_model),
            vision_model=vision_model,
            file_parser_cls=lambda: MarkdownPyMuPDFParser(vision_model=vision_model),
        )

        documents = []
        # Robust iteration: If the loader's generator fails for one item, 
        try:
            for doc in loader.lazy_load():
                documents.append(doc)
        except Exception as exc:
            logger.error(f"Partial failure during Google Classroom lazy_load: {exc}")
            # We continue with whatever documents we managed to load
            
    except Exception as exc:
        if isinstance(exc, ClassroomLoadError):
            raise
        raise ClassroomLoadError(f"Failed to initialize Google Classroom loader: {exc}") from exc
    
    for doc in documents:
        metadata = dict(doc.metadata or {})
        metadata.setdefault("source", "google_classroom")
        metadata["user_id"] = user_id
        metadata["course_id"] = course_id
        doc.metadata = metadata

    return documents


async def load_course_documents(
    user_id: str,
    course_id: str,
    credentials: Credentials,
    settings: Settings | None = None,
) -> list[Document]:
    resolved_settings = settings or get_settings()
    return await anyio.to_thread.run_sync(
        _load_documents_sync,
        user_id,
        course_id,
        credentials,
        resolved_settings,
    )


__all__ = ["ClassroomLoadError", "load_course_documents"]
