from __future__ import annotations

import logging
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

logger = logging.getLogger(__name__)

class ClassroomService:
    @staticmethod
    def get_course(credentials: Credentials, course_id: str) -> dict:
        service = build("classroom", "v1", credentials=credentials, cache_discovery=False)
        return service.courses().get(id=course_id).execute()

    @staticmethod
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

    @staticmethod
    def list_coursework(credentials: Credentials, course_id: str) -> list[dict]:
        service = build("classroom", "v1", credentials=credentials, cache_discovery=False)
        
        def parse_item(item, kind):
            # Extract date if available (format: {"year": YYYY, "month": MM, "day": DD})
            due_date = None
            if "dueDate" in item:
                d = item["dueDate"]
                if "year" in d and "month" in d and "day" in d:
                    due_date = f"{d['year']}-{d['month']:02d}-{d['day']:02d}"
                    
            return {
                "id": item.get("id", ""),
                "title": item.get("title") or "Announcement",
                "description": item.get("description") or item.get("text", ""),
                "state": item.get("state", "PUBLISHED"),
                "due_date": due_date,
                "creation_time": item.get("creationTime", ""),
                "alternate_link": item.get("alternateLink", ""),
                "materials": item.get("materials", []),
                "work_type": kind
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

        return assignments + materials + announcements
