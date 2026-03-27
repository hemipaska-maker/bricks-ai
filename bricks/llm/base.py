"""Abstract LLM provider interface."""

from __future__ import annotations

from abc import ABC, abstractmethod


class LLMProvider(ABC):
    """Abstract LLM backend.

    Implement :meth:`complete` to plug any model into Bricks.

    Example::

        class MyProvider(LLMProvider):
            def complete(self, prompt: str, system: str) -> str:
                return my_llm_client.call(system=system, user=prompt)
    """

    @abstractmethod
    def complete(self, prompt: str, system: str) -> str:
        """Send a prompt to the LLM and return the response text.

        Args:
            prompt: The user message to send.
            system: The system prompt that configures model behaviour.

        Returns:
            The model's text response.
        """
