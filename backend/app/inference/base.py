from abc import ABC, abstractmethod
from typing import Any, Protocol, runtime_checkable


@runtime_checkable
class InferenceProtocol(Protocol):
    """Structural interface Study-logic can depend on."""

    name: str

    def embed(self, texts: list[str]) -> list[list[float]]: ...

    def complete(self, messages: list[dict[str, Any]], **kwargs: Any) -> str: ...


class InferenceAdapter(ABC):
    """One interface for embeddings + chat. Policy code must not hardcode a vendor."""

    name: str

    @abstractmethod
    def embed(self, texts: list[str]) -> list[list[float]]:
        """Return one embedding vector per input text."""

    @abstractmethod
    def complete(self, messages: list[dict[str, Any]], **kwargs: Any) -> str:
        """Return assistant text for a chat-style message list."""
