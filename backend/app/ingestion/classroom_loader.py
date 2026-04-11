from __future__ import annotations

import anyio
from langchain_core.documents import Document
from langchain_google_classroom import GoogleClassroomLoader
from google.oauth2.credentials import Credentials

from app.config import Settings, get_settings
from app.services import get_course
from app.services.groq_vision import build_vision_model


class ClassroomLoadError(Exception):
    pass


def _load_documents_sync(
    user_id: str,
    course_id: str,
    credentials: Credentials,
    settings: Settings,
) -> list[Document]:
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
        )

        documents = list(loader.lazy_load())
    except Exception as exc:
        raise ClassroomLoadError(f"Failed to load Google Classroom content: {exc}") from exc
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
