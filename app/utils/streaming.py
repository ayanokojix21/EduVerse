"""
Server-Sent Events (SSE) helpers.

Usage::

    yield sse_event("status", {"message": "Processing..."})
    yield sse_event("token",  {"text": chunk.content})
    yield sse_event("done",   {"response": final_text, ...})
"""
from __future__ import annotations

import json
from typing import Any


def sse_event(event_type: str, data: Any) -> str:
    """
    Format a single SSE frame.

    Returns a string of the form::

        event: <event_type>\\n
        data: <json>\\n
        \\n

    Compatible with the ``text/event-stream`` protocol and the
    ``@microsoft/fetch-event-source`` client library.
    """
    payload = json.dumps(data, default=str, ensure_ascii=False)
    return f"event: {event_type}\ndata: {payload}\n\n"
