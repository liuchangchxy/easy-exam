"""Provider boundary for optional AI generation.

The core application depends on this small interface.  The compatibility
provider can be replaced by an Ollama/OpenAI adapter without touching routes
or learning logic.
"""

from typing import Any

from backend.legacy.services.ai_service import AIService, build_tutor_prompt


class AiProvider:
    model: str | None = None

    def chat_complete(self, messages: list[dict[str, str]]) -> str:
        raise NotImplementedError


class CompatibleAiProvider(AiProvider):
    def __init__(self, delegate: Any | None = None):
        self.delegate = delegate or AIService()
        self.model = getattr(self.delegate, "model", None)

    def chat_complete(self, messages: list[dict[str, str]]) -> str:
        return self.delegate.chat_complete(messages)


__all__ = ["AiProvider", "CompatibleAiProvider", "build_tutor_prompt"]
