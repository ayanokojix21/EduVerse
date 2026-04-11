from __future__ import annotations
import json
from langchain_core.messages import HumanMessage
from langchain_core.runnables import RunnableConfig
from langchain_groq import ChatGroq
from langsmith import traceable
from app.agents.state import AgentState
from app.services.gmail import list_todays_emails
from app.db.oauth_tokens import OAuthTokenService
from app.db.event_store import EventStore
from app.config import get_settings

settings = get_settings()

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
    llm = ChatGroq(model=settings.groq_timetable_model, api_key=settings.groq_api_key, temperature=0)
    prompt = f"Extract academic events/deadlines from these emails. Use YYYY-MM-DD for dates:\n\n{raw_text}\n\nReturn JSON list of [{{'event', 'date', 'description', 'priority'}}]"
    
    response = await llm.ainvoke([HumanMessage(content=prompt)])
    try:
        content = response.content.split("```json")[-1].split("```")[0].strip()
        events = json.loads(content)
        await event_store.add_events(state["user_id"], events) 
    except: events = []

    return {"email_events": events, "agent_thoughts": [{"node": "email_agent", "summary": f"Found/stored {len(events)} events."}]}
