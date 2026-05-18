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
    def __init__(self, vision_model: Any | None = None, settings: Settings | None = None):
        self.vision_model = vision_model
        self._settings = settings or get_settings()

    def lazy_parse(self, blob: Blob) -> Iterator[Document]:
        import fitz
        import pymupdf4llm
        import logging
        import base64
        import anyio
        logger = logging.getLogger(__name__)
        logger.info(f"--- Parsing Document: {blob.source} ---")
        
        try:
            # We strictly expect PDFs since the loader routes via MIME type
            doc = fitz.open(stream=blob.as_bytes(), filetype="pdf")
            chunks = pymupdf4llm.to_markdown(doc, page_chunks=True)

            img_count = 0
            seen_pages = set()
            
            for chunk in chunks:
                page_idx = chunk.get("metadata", {}).get("page_number", 1) - 1
                page_text = chunk.get("text", "")
                
                if self.vision_model and img_count < self._settings.max_vision_images_per_doc and page_idx not in seen_pages:
                    seen_pages.add(page_idx)
                    page = doc[page_idx]
                    logger.debug(f"Scanning page {page_idx + 1} for qualified images...")
                    
                    image_list = page.get_images()
                    
                    for img_info in image_list:
                        if img_count >= self._settings.max_vision_images_per_doc:
                            break
                            
                        xref = img_info[0]
                        base_image = doc.extract_image(xref)
                        if base_image.get("width", 0) >= 120 and base_image.get("height", 0) >= 120:
                            image_bytes = base_image["image"]
                            
                            import io
                            from PIL import Image
                            try:
                                with Image.open(io.BytesIO(image_bytes)) as img:
                                    if img.mode != "RGB":
                                        img = img.convert("RGB")
                                    img.thumbnail((1024, 1024))
                                    buffer = io.BytesIO()
                                    img.save(buffer, format="JPEG", quality=85)
                                    sanitized_bytes = buffer.getvalue()
                                mime_type = "image/jpeg"
                                b64 = base64.b64encode(sanitized_bytes).decode("utf-8")
                            except Exception as e:
                                logger.warning(f"Image sanitization failed: {e}")
                                continue
                                
                            from langchain_core.messages import HumanMessage
                            try:
                                mm_msg = HumanMessage(content=[
                                    {"type": "text", "text": "Analyze this image/document from " + str(blob.source or "unknown") + " for educational context. Identify key text, diagrams, or events. Be concise."},
                                    {"type": "image_url", "image_url": {"url": f"data:{mime_type};base64,{b64}"}}
                                ])
                                
                                res = self.vision_model.invoke([mm_msg])
                                desc = res.content
                                
                                if isinstance(desc, list):
                                    desc = "\n".join([
                                        part.get("text") or part.get("thinking") or str(part) 
                                        for part in desc if isinstance(part, dict)
                                    ])
                                
                                page_text += f"\n\n> [Visual Analysis]: {desc}\n"
                                img_count += 1
                            except Exception as vision_exc:
                                logger.warning(f"Vision analysis failed for {blob.source or 'unknown'}: {vision_exc}")

                doc_metadata = dict(blob.metadata or {})
                doc_metadata.update({
                    "source": blob.source,
                    "page_number": page_idx + 1
                })
                
                yield Document(page_content=page_text, metadata=doc_metadata)

        except Exception as exc:
            logger.error(f"Failed to parse document from {blob.source or 'unknown'}: {exc}")

class EduVerseClassroomLoader(GoogleClassroomLoader):
    """Custom loader that selectively applies PyMuPDF to PDFs, leaving native routing for other types."""
    def _get_parser_for(self, mime_type: str) -> BaseBlobParser | None:
        normalized_mime = mime_type.split(";")[0].strip().lower()
        if normalized_mime == "application/pdf":
            return MarkdownPyMuPDFParser(vision_model=self.vision_model)
        return super()._get_parser_for(mime_type)


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
        vision_llm = RoundRobinLLM.for_role("vision", temperature=0, vision=True)

        loader = EduVerseClassroomLoader(
            credentials=credentials,
            course_ids=[course_id],
            load_assignments=True,
            load_announcements=True,
            load_materials=True,
            load_attachments=True,
            parse_attachments=True,
            load_images=bool(vision_llm),
            vision_model=vision_llm,
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
    selected_item_ids: list[str] | None = None,
) -> list[Document]:
    resolved_settings = settings or get_settings()
    docs = await anyio.to_thread.run_sync(
        _load_documents_sync,
        user_id,
        course_id,
        credentials,
        resolved_settings,
    )
    if selected_item_ids is not None:
        allowed = set(selected_item_ids)
        docs = [
            d for d in docs
            if d.metadata.get("item_id") in allowed
        ]
    return docs


__all__ = ["ClassroomLoadError", "load_course_documents", "MarkdownPyMuPDFParser"]
