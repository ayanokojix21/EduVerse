from __future__ import annotations

from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build


def get_course(credentials: Credentials, course_id: str) -> dict:
    service = build("classroom", "v1", credentials=credentials, cache_discovery=False)
    return service.courses().get(id=course_id).execute()


def list_courses(credentials: Credentials) -> list[dict[str, str]]:
    service = build("classroom", "v1", credentials=credentials, cache_discovery=False)
    response = service.courses().list(courseStates=["ACTIVE"]).execute()

    courses = response.get("courses", [])
    return [
        {
            "id": str(course.get("id", "")),
            "name": str(course.get("name", "")),
            "section": str(course.get("section", "")),
        }
        for course in courses
    ]
