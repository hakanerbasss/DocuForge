from abc import ABC, abstractmethod
from typing import Any

from app.ai.factory import get_ai


class BaseAgent(ABC):
    """Common base class for all DocuForge AI agents."""

    MAX_ATTEMPTS = 3

    def __init__(self) -> None:
        self.ai = get_ai()

    def generate_with_retry(self, prompt: str) -> str:
        """Generate an AI response with automatic retry support."""

        last_error: Exception | None = None

        for attempt in range(1, self.MAX_ATTEMPTS + 1):
            try:
                response = self.ai.generate(prompt)

                if not isinstance(response, str):
                    raise TypeError(
                        "AI provider response must be a string."
                    )

                response = response.strip()

                if not response:
                    raise ValueError(
                        "AI provider returned an empty response."
                    )

                return response

            except Exception as error:
                last_error = error

                if attempt == self.MAX_ATTEMPTS:
                    break

        raise RuntimeError(
            f"{self.__class__.__name__} failed after "
            f"{self.MAX_ATTEMPTS} attempts. "
            f"Last error: {last_error}"
        ) from last_error

    def validate_text(self, content: str) -> str:
        """Validate and normalize plain-text AI output."""

        if not isinstance(content, str):
            raise TypeError("Agent output must be a string.")

        content = content.strip()

        if not content:
            raise ValueError("Agent output cannot be empty.")

        return content

    @abstractmethod
    def run(self, *args: Any, **kwargs: Any) -> str:
        """Run the agent and return its generated output."""
        raise NotImplementedError
