from __future__ import annotations
import json
from datetime import datetime
from langchain_core.messages import HumanMessage
from langchain_core.runnables import RunnableConfig
from langchain_groq import ChatGroq
from langsmith import traceable
from app.agents.state import AgentState
from app.db.event_store import EventStore
from app.config import get_settings

settings = get_settings()

@traceable(name="timetable_agent")
async def timetable_agent_node(state: AgentState, config: RunnableConfig) -> dict:
    db = config["configurable"]["db"]
    event_store = EventStore(db)
    
    # 1. Identify Target Date (Default to today in YYYY-MM-DD)
    target_date = datetime.now().strftime("%Y-%m-%d") 
    
    # 2. Fetch Stored Memory for that date
    stored_events = await event_store.get_events_for_date(state["user_id"], target_date)
    
    # 3. Generate Timetable
    llm = ChatGroq(model=settings.groq_timetable_model, api_key=settings.groq_api_key)
    prompt = (
        f"Date: {target_date}\nMemory (Stored Events): {json.dumps(stored_events)}\n"
        f"New Events: {json.dumps(state['email_events'])}\nUser Request: {state['original_query']}\n"
        "Generate a complete today's timetable as a JSON object."
    )
    
    response = await llm.ainvoke([HumanMessage(content=prompt)])
    return {
        "response_text": f"Schedule for {target_date} updated! \n\n{response.content}",
        "timetable": response.content,
        "agent_thoughts": [{"node": "timetable_agent", "summary": "Timetable compiled with long-term memory."}]
    }
