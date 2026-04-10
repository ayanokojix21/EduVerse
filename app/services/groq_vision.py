from __future__ import annotations

from typing import Any

from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_groq import ChatGroq

from app.config import Settings, get_settings


class GroqVisionWrapper:
    """Thin adapter around ChatGroq for vision calls used by classroom parsers."""

    def __init__(
        self,
        *,
        api_key: str,
        model_name: str,
        temperature: float,
        max_tokens: int,
        chat_model: Any | None = None,
    ) -> None:
        self.model_name = model_name
        self._chat_model = chat_model or ChatGroq(
            model=model_name,
            api_key=api_key,
            temperature=temperature,
            max_tokens=max_tokens,
            max_retries=2,
        )

    def invoke(self, messages: Any, **kwargs: Any) -> Any:
        return self._chat_model.invoke(messages, **kwargs)

    async def ainvoke(self, messages: Any, **kwargs: Any) -> Any:
        return await self._chat_model.ainvoke(messages, **kwargs)

    def __getattr__(self, name: str) -> Any:
        return getattr(self._chat_model, name)


def build_vision_model(settings: Settings | None = None) -> Any | None:
    resolved_settings = settings or get_settings()

    if resolved_settings.groq_vision_enabled and resolved_settings.groq_api_key:
        return GroqVisionWrapper(
            api_key=resolved_settings.groq_api_key,
            model_name=resolved_settings.groq_vision_model,
            temperature=resolved_settings.groq_vision_temperature,
            max_tokens=resolved_settings.groq_vision_max_tokens,
        )

    if resolved_settings.google_api_key:
        return ChatGoogleGenerativeAI(
            model="gemini-2.0-flash",
            google_api_key=resolved_settings.google_api_key,
        )

    return None


__all__ = ["GroqVisionWrapper", "build_vision_model"]
