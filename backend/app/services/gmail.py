from __future__ import annotations
import logging
from datetime import datetime
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

logger = logging.getLogger(__name__)

def list_todays_emails(credentials: Credentials) -> list[dict]:
    """Fetch all emails received since the start of the current day."""
    try:
        service = build("gmail", "v1", credentials=credentials, cache_discovery=False)
        today_date = datetime.now().strftime('%Y/%m/%d')
        query = f"after:{today_date}"
        
        all_messages = []
        page_token = None
        while True:
            results = service.users().messages().list(userId="me", q=query, pageToken=page_token).execute()
            all_messages.extend(results.get("messages", []))
            page_token = results.get("nextPageToken")
            if not page_token: break
        
        email_data = []
        for msg in all_messages:
            txt = service.users().messages().get(userId="me", id=msg["id"], format="full").execute()
            headers = txt.get("payload", {}).get("headers", [])
            subject = next((h["value"] for h in headers if h["name"] == "Subject"), "No Subject")
            from_email = next((h["value"] for h in headers if h["name"] == "From"), "Unknown")
            email_data.append({"id": msg["id"], "from": from_email, "subject": subject, "snippet": txt.get("snippet", "")})
        return email_data
    except Exception as e:
        logger.error(f"Gmail API error: {e}")
        return []
