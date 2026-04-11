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


def list_coursework(credentials: Credentials, course_id: str) -> dict:
    service = build("classroom", "v1", credentials=credentials, cache_discovery=False)
    
    def parse_item(item, kind):
        return {
            "id": item.get("id", ""),
            "title": item.get("title") or "Announcement",
            "description": item.get("description") or item.get("text", ""),
            "state": item.get("state", "PUBLISHED"),
            "dueDate": item.get("dueDate", None),
            "creationTime": item.get("creationTime", ""),
            "alternateLink": item.get("alternateLink", ""),
            "materials": item.get("materials", []),
            "type": kind
        }

    # 1. Fetch CourseWork (Assignments)
    cw_res = service.courses().courseWork().list(courseId=course_id).execute()
    assignments = [parse_item(i, "assignment") for i in cw_res.get("courseWork", [])]
    
    # 2. Fetch CourseWorkMaterials
    cwm_res = service.courses().courseWorkMaterials().list(courseId=course_id).execute()
    materials = [parse_item(i, "material") for i in cwm_res.get("courseWorkMaterial", [])]
    
    # 3. Fetch Announcements
    ann_res = service.courses().announcements().list(courseId=course_id).execute()
    announcements = [parse_item(i, "announcement") for i in ann_res.get("announcements", [])]

    return {
        "assignments": assignments,
        "materials": materials,
        "announcements": announcements
    }
