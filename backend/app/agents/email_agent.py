from __future__ import annotations
import json
from langchain_core.messages import HumanMessage
from langchain_core.runnables import RunnableConfig
from langsmith import traceable
from pydantic import BaseModel, Field
from typing import List
from app.agents.state import AgentState
from app.services.gmail import list_todays_emails
from app.db.oauth_tokens import OAuthTokenService
from app.db.event_store import EventStore
from app.config import get_settings
from app.utils.llm_pool import RoundRobinLLM

settings = get_settings()

class Event(BaseModel):
    event: str = Field(description="Name of the event")
    date: str = Field(description="Date in YYYY-MM-DD format")
    description: str = Field(description="Short description")
    priority: str = Field(description="High, Medium, or Low")

class EmailEventsOutput(BaseModel):
    events: List[Event] = Field(description="List of extracted events", default_factory=list)

@traceable(name="email_agent")
async def email_agent_node(state: AgentState, config: RunnableConfig) -> dict:
    db = config["configurable"]["db"]
    oauth_service = OAuthTokenService(db)
    event_store = EventStore(db)
    
    try:
        creds = await oauth_service.get_user_credentials(state["user_id"])
        emails = list_todays_emails(creds)
    except Exception: emails = []

    if not emails:
        return {"email_events": [], "agent_thoughts": [{"node": "email_agent", "summary": "No new emails today."}]}

    raw_text = "\n\n".join([f"Subject: {e['subject']}\nSnippet: {e['snippet']}" for e in emails])
    llm = RoundRobinLLM.for_role("structured", temperature=0, schema=EmailEventsOutput)
    prompt = f"Extract academic events/deadlines from these emails. Use YYYY-MM-DD for dates:\n\n{raw_text}\n\nReturn JSON list of [{{'event', 'date', 'description', 'priority'}}]"
    
    try:
        response: EmailEventsOutput = await llm.ainvoke([HumanMessage(content=prompt)])
        # convert pydantic models to dicts for the event store
        events = [e.model_dump() for e in response.events]
        if events:
            await event_store.add_events(state["user_id"], events) 
    except Exception as exc: 
        import logging
        logging.getLogger(__name__).warning(f"Email extraction failed: {exc}")
        events = []

    return {"email_events": events, "agent_thoughts": [{"node": "email_agent", "summary": f"Found/stored {len(events)} events."}]}
