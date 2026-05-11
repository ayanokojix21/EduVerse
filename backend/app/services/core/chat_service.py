from __future__ import annotations

import asyncio
import logging
import uuid
from typing import AsyncGenerator

from fastapi import BackgroundTasks
from fastapi.encoders import jsonable_encoder
from langchain_core.messages import HumanMessage
from langgraph.types import Command

from app.agents.graph import get_compiled_graph
from app.config import get_settings
from app.db.profile_repository import ProfileRepository
from app.utils.streaming import sse_event

logger = logging.getLogger(__name__)

# Constants for agent telemetry
AGENT_NODES = frozenset(
    {"orchestrator", "rag_swarm", "quiz_swarm", "feedback_swarm",
     "planner", "executor", "hitl", "distiller", "generator", "validator", "formatter",
     "topic_selector", "retriever", "distributor", "drafter_worker", "reviewer",
     "diagnostician", "mentor", "critic_agent", "input_moderator", "integrity_guard", "output_moderator"}
)

class ChatService:
    def __init__(self, db, sync_client, settings=None):
        self.db = db
        self.sync_client = sync_client
        self.settings = settings or get_settings()

    async def run(
        self,
        user_id: str,
        course_id: str,
        message: str,
        background_tasks: BackgroundTasks,
        session_id: str | None = None,
        **kwargs
    ) -> AsyncGenerator[str, None]:
        """
        Drives the LangGraph pipeline and yields SSE frames.
        """
        try:
            profile_store = ProfileRepository(db=self.db, settings=self.settings)
            weak_topics = await profile_store.get_weak_topics(user_id)
        except Exception as exc:
            logger.warning("Failed to load weak topics: %s", exc)
            weak_topics = []

        graph = get_compiled_graph()
        
        if not session_id:
            session_id = f"{user_id}:{course_id}:{uuid.uuid4()}"

        run_config = {
            "configurable": {
                "thread_id": session_id,
                "user_id": user_id,
                "db": self.db,
                "mongo_client_sync": self.sync_client,
            },
            "tags": ["eduverse"],
            "metadata": {
                "user_id": user_id,
                "course_id": course_id,
                "session_id": session_id,
            },
        }

        initial_state = {
            "messages":           [HumanMessage(content=message)],
            "user_id":            user_id,
            "course_id":          course_id,
            "session_id":         session_id,
            "original_query":     message,
            "weak_topics":        weak_topics,         
            "task":               "",
            "rewritten_queries":  [],
            "needs_rewrite":      True,
            "context_docs":       [],
            "retrieval_label":    "",
            "top_reranker_score": 0.0,
            "retrieval_ms":       0,
            "explainability":     {},
            "response_text":      "",
            "citations":          [],
            "critic_review":      {},
            "critic_feedback":    [],       # append-only Annotated reducer — must init
            "agent_thoughts":     [],
            "retry_count":        0,
            # DPO training data
            "dpo_pairs":          [],
            "tutor_raw_responses":   [],
            "quiz_raw_responses":    [],
            "feedback_raw_responses": [],
            # Swarm revision counters
            "tutor_revisions":    0,
            "quiz_revisions":     0,
            "feedback_revisions": 0,
            # Feedback swarm inputs
            "quiz_responses":     kwargs.get("quiz_responses", []),
            # Multimodal
            "trace_url":          "",
            "image_data":         kwargs.get("image_data"),
            "image_mimetype":     kwargs.get("image_mimetype", "image/png"),
            "is_multimodal":      bool(kwargs.get("image_data")),
        }

        yield sse_event("status", {"message": "Processing your question…", "session_id": session_id})

        final_state: dict = {}
        all_thoughts: list[dict] = []
        last_response_text: str = ""

        try:
            async for event in graph.astream_events(initial_state, run_config, version="v2"):
                kind = event.get("event", "")
                name = event.get("name", "")
                tags = event.get("tags") or []

                if kind == "on_chain_start" and name in AGENT_NODES:
                    yield sse_event("node_start", {"node": name, "message": f"{name.replace('_', ' ').title()} is working..."})
                
                if kind == "on_tool_start":
                    yield sse_event("tool_start", {"tool": name, "input": event.get("data", {}).get("input")})
                
                if kind == "on_tool_end":
                    yield sse_event("tool_end", {"tool": name})

                if kind == "on_chain_end" and name in AGENT_NODES:
                    yield sse_event("node_end", {"node": name})
                    output = event["data"].get("output")
                    
                    # LangGraph 2.0+ nodes can return a Command object for routing/updates
                    if isinstance(output, Command):
                        output = output.update or {}
                    elif not isinstance(output, dict):
                        output = {}

                    thoughts = output.get("agent_thoughts") or []
                    for thought in thoughts:
                        all_thoughts.append(thought)
                        yield sse_event("agent_thought", thought)

                    if name == "rag_swarm":
                        yield sse_event("retrieval_label", {
                            "label": output.get("retrieval_label", ""),
                            "top_score": output.get("top_reranker_score", 0.0),
                            "confidence_label": (output.get("explainability") or {}).get("confidence_label", ""),
                            "retrieval_ms": output.get("retrieval_ms", 0),
                        })

                    final_state.update(output)

                elif kind == "on_chat_model_stream":
                    parser_output = event["data"].get("chunk")
                    if isinstance(parser_output, dict):
                        current_text = parser_output.get("response_text", "")
                        if current_text and len(current_text) > len(last_response_text):
                            delta = current_text[len(last_response_text):]
                            yield sse_event("token", {"text": delta})
                            last_response_text = current_text

            try:
                persisted = await graph.aget_state(run_config)
                if persisted and persisted.values:
                    final_state = persisted.values
            except Exception as exc:
                logger.warning("aget_state failed: %s", exc)

            trace_url = self._get_langsmith_url(run_config)

            mermaid_def = "graph TD\n"
            current_node = "START"
            for t in all_thoughts:
                next_node = t.get("node", "step").replace("_", " ")
                mermaid_def += f'  {current_node.replace(" ", "_")}["{current_node}"] --> {next_node.replace(" ", "_")}["{next_node}"]\n'
                current_node = next_node
            mermaid_def += f'  {current_node.replace(" ", "_")} --> END["END"]'

            done_payload = {
                "response":        final_state.get("response_text", ""),
                "citations":       final_state.get("citations", []),
                "tutor_raw_responses": final_state.get("tutor_raw_responses", []),
                "retrieval_label": final_state.get("retrieval_label", ""),
                "explainability":  final_state.get("explainability", {}),
                "critic":          final_state.get("critic_review", {}),
                "agent_thoughts":  all_thoughts,
                "mermaid_graph":   mermaid_def, 
                "retrieval_ms":    final_state.get("retrieval_ms", 0),
                "session_id":      session_id,
                "trace_url":       trace_url,
            }
            yield sse_event("done", jsonable_encoder(done_payload))

            from app.services.training.analytics_service import AnalyticsService
            analytics = AnalyticsService(db=self.db, settings=self.settings)
            background_tasks.add_task(analytics.process_post_run, user_id, session_id, course_id, message, final_state)

        except Exception as exc:
            logger.exception("Pipeline error for user=%s", user_id[:8])
            yield sse_event("error", {"message": str(exc), "code": "PIPELINE_ERROR"})

    async def resume_run(
        self,
        session_id: str,
        decision: str,
        user_id: str,
        background_tasks: BackgroundTasks,
    ) -> AsyncGenerator[str, None]:
        """
        Resumes a LangGraph execution that was paused at a HITL interrupt node.
        
        Uses Command(resume=<decision>) — the 2026 LangGraph pattern for
        deterministic HITL resumption. The graph continues from the exact
        checkpoint where interrupt() was called, with the student's decision
        injected as the return value of interrupt().
        
        Args:
            session_id: The thread_id identifying the paused graph state.
            decision: Student's choice ('search_web' | 'socratic_only').
            user_id: Authenticated user for RBAC and analytics.
            background_tasks: FastAPI background task runner for post-run analytics.
        """
        graph = get_compiled_graph()

        run_config = {
            "configurable": {
                "thread_id": session_id,
                "user_id": user_id,
                "db": self.db,
                "mongo_client_sync": self.sync_client,
            },
            "tags": ["eduverse", "hitl_resume"],
        }

        yield sse_event("status", {
            "message": f"Resuming with your choice: {decision.replace('_', ' ').title()}…",
            "session_id": session_id,
            "hitl_decision": decision,
        })

        final_state: dict = {}
        all_thoughts: list[dict] = []
        last_response_text: str = ""

        try:
            # Command(resume=<value>) is the 2026 LangGraph pattern.
            # It delivers `decision` as the return value of interrupt()
            # inside hitl_node, then continues graph execution.
            async for event in graph.astream_events(
                Command(resume=decision),
                run_config,
                version="v2",
            ):
                kind = event.get("event", "")
                name = event.get("name", "")

                if kind == "on_chain_start" and name in AGENT_NODES:
                    yield sse_event("node_start", {"node": name, "message": f"{name.replace('_', ' ').title()} is working..."})

                if kind == "on_tool_start":
                    yield sse_event("tool_start", {"tool": name, "input": event.get("data", {}).get("input")})

                if kind == "on_tool_end":
                    yield sse_event("tool_end", {"tool": name})

                if kind == "on_chain_end" and name in AGENT_NODES:
                    yield sse_event("node_end", {"node": name})
                    output = event["data"].get("output")
                    if isinstance(output, Command):
                        output = output.update or {}
                    elif not isinstance(output, dict):
                        output = {}

                    thoughts = output.get("agent_thoughts") or []
                    for thought in thoughts:
                        all_thoughts.append(thought)
                        yield sse_event("agent_thought", thought)

                    if name == "rag_swarm":
                        yield sse_event("retrieval_label", {
                            "label": output.get("retrieval_label", ""),
                            "top_score": output.get("top_reranker_score", 0.0),
                            "confidence_label": (output.get("explainability") or {}).get("confidence_label", ""),
                            "retrieval_ms": output.get("retrieval_ms", 0),
                        })

                    final_state.update(output)

                elif kind == "on_chat_model_stream":
                    parser_output = event["data"].get("chunk")
                    if isinstance(parser_output, dict):
                        current_text = parser_output.get("response_text", "")
                        if current_text and len(current_text) > len(last_response_text):
                            delta = current_text[len(last_response_text):]
                            yield sse_event("token", {"text": delta})
                            last_response_text = current_text

            try:
                persisted = await graph.aget_state(run_config)
                if persisted and persisted.values:
                    final_state = persisted.values
            except Exception as exc:
                logger.warning("aget_state failed on resume: %s", exc)

            trace_url = self._get_langsmith_url(run_config)
            done_payload = {
                "response":        final_state.get("response_text", ""),
                "citations":       final_state.get("citations", []),
                "retrieval_label": final_state.get("retrieval_label", ""),
                "explainability":  final_state.get("explainability", {}),
                "critic":          final_state.get("critic_review", {}),
                "agent_thoughts":  all_thoughts,
                "session_id":      session_id,
                "trace_url":       trace_url,
                "hitl_decision":   decision,
            }
            yield sse_event("done", jsonable_encoder(done_payload))

            from app.services.training.analytics_service import AnalyticsService
            analytics = AnalyticsService(db=self.db, settings=self.settings)
            background_tasks.add_task(
                analytics.process_post_run,
                user_id, session_id,
                final_state.get("course_id", ""),
                f"[HITL-{decision}] {final_state.get('original_query', '')}",
                final_state,
            )

        except Exception as exc:
            logger.exception("HITL resume error for session=%s", session_id[:12])
            yield sse_event("error", {"message": str(exc), "code": "HITL_RESUME_ERROR"})

    def _get_langsmith_url(self, config: dict) -> str:
        try:
            import os
            if os.getenv("LANGCHAIN_TRACING_V2", "false").lower() != "true":
                return ""
            thread_id = config.get("configurable", {}).get("thread_id", "")
            project = os.getenv("LANGCHAIN_PROJECT", "default")
            return f"https://smith.langchain.com/o/default/projects/p/{project}?threadId={thread_id}"
        except Exception:
            return ""
