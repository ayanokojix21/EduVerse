from __future__ import annotations

import anyio
from langchain_core.documents import Document
from langchain_core.document_loaders import BaseBlobParser
from langchain_core.documents.base import Blob
from langchain_google_classroom import GoogleClassroomLoader
from google.oauth2.credentials import Credentials
from typing import Iterator, Any

from app.config import Settings, get_settings
from app.services.auth.classroom_service import ClassroomService


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
            doc = fitz.open(stream=blob.as_bytes(), filetype=blob.source.split('.')[-1] if '.' in blob.source else None)
            
            if doc.is_pdf:
                chunks = pymupdf4llm.to_markdown(doc, page_chunks=True)
            else:
                chunks = [{"text": "", "metadata": {"page_number": 1}}]

            img_count = 0
            
            for chunk in chunks:
                page_idx = chunk.get("metadata", {}).get("page_number", 1) - 1
                page_text = chunk.get("text", "")
                
                page_img_count = 0
                if self.vision_model and img_count < 10:
                    page = doc[page_idx]
                    
                    if not doc.is_pdf:
                        image_bytes = blob.as_bytes()
                        is_qualified = True
                    else:
                        image_list = page.get_images()
                        image_bytes = None
                        is_qualified = False
                        
                        if image_list:
                            xref = image_list[0][0]
                            base_image = doc.extract_image(xref)
                            if base_image.get("width", 0) >= 120 and base_image.get("height", 0) >= 120:
                                image_bytes = base_image["image"]
                                is_qualified = True

                    if is_qualified and image_bytes:
                        b64 = base64.b64encode(image_bytes).decode("utf-8")
                        try:
                            desc = anyio.from_thread.run(
                                self.vision_model.describe_image, 
                                b64, 
                                f"Analyze this image/document from {blob.source} for educational context. "
                                "Identify key text, diagrams, or events. Be concise."
                            )
                            page_text += f"\n\n> [Visual Analysis]: {desc}\n"
                            img_count += 1
                        except Exception as vision_exc:
                            logger.warning(f"Vision analysis failed for {blob.source}: {vision_exc}")

                doc_metadata = dict(blob.metadata or {})
                doc_metadata.update({
                    "source": blob.source,
                    "page_number": page_idx + 1
                })
                
                yield Document(page_content=page_text, metadata=doc_metadata)

        except Exception as exc:
            logger.error(f"Failed to parse document from {blob.source}: {exc}")

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
        ClassroomService.get_course(credentials, course_id)

        from app.utils.llm_pool import RoundRobinLLM
        vision_llm = RoundRobinLLM.for_role("vision", temperature=0)

        loader = GoogleClassroomLoader(
            credentials=credentials,
            course_ids=[course_id],
            load_assignments=True,
            load_announcements=True,
            load_materials=True,
            load_attachments=True,
            parse_attachments=True,
            load_images=True,
            file_parser_cls=lambda: MarkdownPyMuPDFParser(vision_model=vision_llm),
        )

        documents = []
        try:
            for doc in loader.lazy_load():
                documents.append(doc)
        except Exception as exc:
            logger.error(f"Partial failure during Google Classroom lazy_load: {exc}")
            
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
