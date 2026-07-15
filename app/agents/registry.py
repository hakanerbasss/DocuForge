from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from app.agents.base import BaseAgent


@dataclass(frozen=True)
class AgentDefinition:
    """Metadata and factory for a registered DocuForge agent."""

    key: str
    name: str
    icon: str
    output_file: str
    factory: Callable[[], BaseAgent]


class AgentRegistry:
    """Central registry for all DocuForge agents."""

    _agents: dict[str, AgentDefinition] = {}

    @classmethod
    def register(
        cls,
        *,
        key: str,
        name: str,
        icon: str,
        output_file: str,
        factory: Callable[[], BaseAgent],
    ) -> None:
        normalized_key = key.strip().lower()

        if not normalized_key:
            raise ValueError("Agent key cannot be empty.")

        if normalized_key in cls._agents:
            raise ValueError(
                f"Agent already registered: {normalized_key}"
            )

        cls._agents[normalized_key] = AgentDefinition(
            key=normalized_key,
            name=name,
            icon=icon,
            output_file=output_file,
            factory=factory,
        )

    @classmethod
    def get(cls, key: str) -> AgentDefinition:
        normalized_key = key.strip().lower()

        try:
            return cls._agents[normalized_key]
        except KeyError as error:
            raise KeyError(
                f"Agent is not registered: {normalized_key}"
            ) from error

    @classmethod
    def all(cls) -> list[AgentDefinition]:
        return list(cls._agents.values())

    @classmethod
    def create(cls, key: str) -> BaseAgent:
        definition = cls.get(key)
        return definition.factory()

    @classmethod
    def clear(cls) -> None:
        """Clear registry, mainly useful for tests."""

        cls._agents.clear()
