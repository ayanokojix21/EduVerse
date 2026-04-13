"""
POST /chat/stream — Server-Sent Events (SSE) Chat Endpoint
This is the main entry point for the EduVerse AI Tutor frontend.
"""
from __future__ import annotations

import asyncio
import logging
import uuid
from typing import AsyncGenerator

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.encoders import jsonable_encoder
from fastapi.responses import StreamingResponse
from langchain_core.messages import HumanMessage
from pydantic import BaseModel, Field

from app.agents.graph import get_compiled_graph
from app.config import get_settings
from app.db.chat_history import ChatHistoryService
from app.db.mongodb import get_db
from app.db.profile_store import ProfileStore
from app.utils.streaming import sse_event

logger = logging.getLogger(__name__)
settings = get_settings()
router = APIRouter()

# All node names that appear in astream_events; used to filter agent_thought emissions
_AGENT_NODES = frozenset(
    {"supervisor", "query_rewriter", "rag_agent",
     "tutor_a", "tutor_b", "synthesizer", "critic_agent",
     "email_agent", "timetable_agent"}
)


# ── Request / Response schemas ────────────────────────────────────────────────

class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=4000)
    course_id: str = Field(min_length=1)
    session_id: str | None = Field(default=None, description="Provide to resume a previous conversation")


# ── Background task: update weak topics + session count ───────────────────────

async def _post_run_update(
    user_id: str,
    final_state: dict,
    db,
) -> None:
    """
    Fire-and-forget: increments session count and optionally stores weak
    topics extracted by the Critic when severity is ``high``.
    """
    try:
        store = ProfileStore(db=db, settings=settings)
        await store.increment_session(user_id)

        critic = final_state.get("critic_review") or {}
        if critic.get("severity") == "high":
            raw_issues = critic.get("issues") or []
            new_topics = [issue[:40].strip() for issue in raw_issues if issue]
            if new_topics:
                await store.update_weak_topics(user_id, new_topics)
                logger.info(
                    "Weak topics updated for user=%s: %s",
                    user_id[:8],
                    new_topics,
                )
    except Exception as exc:  # noqa: BLE001
        logger.warning("Post-run update failed (non-fatal): %s", exc)


async def _persist_chat_messages(
    session_id: str,
    user_id: str,
    course_id: str,
    user_message: str,
    ai_response: str,
    citations: list[dict],
    db,
) -> None:
    """
    Fire-and-forget: persist the user message and AI response
    to the chat_sessions collection for history/resume.
    """
    try:
        history = ChatHistoryService(db=db)
        # Save user message
        await history.save_message(
            session_id=session_id,
            user_id=user_id,
            course_id=course_id,
            role="user",
            content=user_message,
        )
        # Save AI response
        await history.save_message(
            session_id=session_id,
            user_id=user_id,
            course_id=course_id,
            role="assistant",
            content=ai_response,
            citations=citations,
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning("Chat history save failed (non-fatal): %s", exc)

def _get_langsmith_url(config: dict) -> str:
    """
    Build the LangSmith run URL for surfacing in the UI.
    Returns empty string if LangSmith tracing is disabled or URL unavailable.
    """
    try:
        import os
        if os.getenv("LANGCHAIN_TRACING_V2", "false").lower() != "true":
            return ""
        thread_id = config.get("configurable", {}).get("thread_id", "")
        project = os.getenv("LANGCHAIN_PROJECT", "default")
        return f"https://smith.langchain.com/o/default/projects/p/{project}?threadId={thread_id}"
    except Exception:  # noqa: BLE001
        return ""


# ── SSE generator ─────────────────────────────────────────────────────────────

async def _run_pipeline(
    user_id: str,
    course_id: str,
    message: str,
    db,
    session_id: str | None = None,
) -> AsyncGenerator[str, None]:
    try:
        _profile_store = ProfileStore(db=db, settings=settings)
        weak_topics: list[str] = await _profile_store.get_weak_topics(user_id)
    except Exception as exc:  # noqa: BLE001
        logger.warning("Failed to load weak topics (non-fatal): %s", exc)
        weak_topics = []
    """
    Core SSE generator.  Drives the LangGraph pipeline and yields SSE frames.
    """
    graph = get_compiled_graph()
    
    # Use provided session_id to resume checkpoint memory, or create a new session
    if not session_id:
        session_id = f"{user_id}:{course_id}:{uuid.uuid4()}"

    # Build LangGraph run config
    # ─ thread_id   → unique per session, enabling checkpointed memory
    # ─ db          → passed to rag_agent_node via config["configurable"]
    # ─ tags        → propagate to child runs (filtering in astream_events)
    run_config: dict = {
        "configurable": {
            "thread_id": session_id,
            "user_id": user_id,          # available to nodes via config["configurable"]
            "db": db,
        },
        "tags": ["eduverse"],
        "metadata": {
            "user_id": user_id,
            "course_id": course_id,
            "session_id": session_id,
        },
    }

    # Initial state — fields that must be set before graph runs
    initial_state = {
        "messages":           [HumanMessage(content=message)],
        "user_id":            user_id,
        "course_id":          course_id,
        "session_id":         session_id,
        "original_query":     message,
        "weak_topics":        weak_topics,         # loaded above from MongoDB
        "task":               "timetable" if session_id.startswith("timetable:") else "",
        "rewritten_queries":  [],
        "context_docs":       [],
        "retrieval_label":    "",
        "top_reranker_score": 0.0,
        "retrieval_ms":       0,
        "explainability":     {},
        "response_text":      "",
        "citations":          [],
        "retry_count":        0,
        "critic_review":      {},
        "critic_feedback":    [],
        "agent_thoughts":     [],
        "trace_url":          "",
    }

    # ── Stream start ──────────────────────────────────────────────────────────
    yield sse_event("status", {"message": "Processing your question…", "session_id": session_id})

    final_state: dict = {}
    all_thoughts: list[dict] = []
    last_response_text: str = ""

    try:
        # astream_events v2 yields granular events from every node and LLM call
        async for event in graph.astream_events(initial_state, run_config, version="v2"):
            kind: str = event.get("event", "")
            name: str = event.get("name", "")
            tags: list[str] = event.get("tags") or []

            # ── Agent thought: fired when any named node completes ─────────
            if kind == "on_chain_end" and name in _AGENT_NODES:
                output = event["data"].get("output") or {}
                thoughts: list[dict] = output.get("agent_thoughts") or []
                for thought in thoughts:
                    all_thoughts.append(thought)
                    yield sse_event("agent_thought", thought)

                # Extra: emit retrieval_label + explainability when rag_agent ends
                if name == "rag_agent":
                    yield sse_event(
                        "retrieval_label",
                        {
                            "label":            output.get("retrieval_label", ""),
                            "top_score":        output.get("top_reranker_score", 0.0),
                            "confidence_label": (output.get("explainability") or {}).get(
                                "confidence_label", ""
                            ),
                            "retrieval_ms":     output.get("retrieval_ms", 0),
                        },
                    )

                # Extra: emit tutor_draft as each parallel tutor finishes
                if name in ("tutor_a", "tutor_b"):
                    drafts: list[dict] = output.get("tutor_drafts") or []
                    for draft in drafts:
                        yield sse_event("tutor_draft", draft)

                # Track final state from the last node (critic or synthesizer on pass)
                final_state.update(output)

            # ── High-Fidelity Streaming (on_parser_stream) ────────────────
            elif kind == "on_parser_stream" and "synthesizer" in tags:
                parser_output = event["data"].get("chunk")
                if isinstance(parser_output, dict):
                    current_text = parser_output.get("response_text", "")
                    if current_text and len(current_text) > len(last_response_text):
                        delta = current_text[len(last_response_text):]
                        yield sse_event("token", {"text": delta})
                        last_response_text = current_text

        # ── Fetch final persisted state from checkpointer ─────────────────
        try:
            persisted = await graph.aget_state(run_config)
            if persisted and persisted.values:
                final_state = persisted.values
        except Exception as exc:  # noqa: BLE001
            logger.warning("aget_state failed (using in-memory final_state): %s", exc)

        trace_url = _get_langsmith_url(run_config)

        done_payload = {
            "response":        final_state.get("response_text", ""),
            "citations":       final_state.get("citations", []),
            "tutor_drafts":    final_state.get("tutor_drafts", []),
            "retrieval_label": final_state.get("retrieval_label", ""),
            "explainability":  final_state.get("explainability", {}),
            "critic":          final_state.get("critic_review", {}),
            "agent_thoughts":  all_thoughts,
            "retrieval_ms":    final_state.get("retrieval_ms", 0),
            "session_id":      session_id,
            "trace_url":       trace_url,
        }
        yield sse_event("done", jsonable_encoder(done_payload))

        # Background task: update weak topics + session count (non-blocking)
        asyncio.create_task(
            _post_run_update(user_id, final_state, db)
        )

        # Background task: persist chat messages to chat_sessions collection
        asyncio.create_task(
            _persist_chat_messages(
                session_id=session_id,
                user_id=user_id,
                course_id=course_id,
                user_message=message,
                ai_response=final_state.get("response_text", ""),
                citations=final_state.get("citations", []),
                db=db,
            )
        )

    except Exception as exc:  # noqa: BLE001
        logger.exception("Pipeline error for user=%s course=%s", user_id[:8], course_id)
        yield sse_event("error", {"message": str(exc), "code": "PIPELINE_ERROR"})


# ── FastAPI endpoint ──────────────────────────────────────────────────────────

@router.post(
    "/chat/stream",
    summary="Stream an AI tutoring response via SSE",
    response_description="text/event-stream with 7 event types",
)
async def chat_stream(
    payload: ChatRequest,
    request: Request,
    db=Depends(get_db),
) -> StreamingResponse:
    """
    Main chat endpoint.  Returns a ``StreamingResponse`` carrying a
    ``text/event-stream`` body.

    The ``Authorization: Bearer <jwt>`` header is verified by
    ``JWTAuthMiddleware`` before this handler is reached; ``user_id``
    is already set on ``request.state``.
    """
    user_id: str = getattr(request.state, "user_id", None)
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
        )

    return StreamingResponse(
        _run_pipeline(
            user_id=user_id,
            course_id=payload.course_id,
            message=payload.message,
            db=db,
            session_id=payload.session_id,
        ),
        media_type="text/event-stream",
        headers={
            "Cache-Control":      "no-cache",
            "X-Accel-Buffering":  "no",   # disable Nginx proxy buffering
            "Connection":         "keep-alive",
        },
    )
