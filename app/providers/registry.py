from dataclasses import dataclass
from typing import Callable, TypeVar

from app.providers.base import BaseProvider


ProviderType = TypeVar("ProviderType", bound=BaseProvider)


@dataclass(frozen=True)
class ProviderDefinition:
    """Metadata and factory for a registered provider."""

    category: str
    key: str
    name: str
    factory: Callable[[], BaseProvider]


class ProviderRegistry:
    """Central registry for all DocuForge providers."""

    _providers: dict[str, dict[str, ProviderDefinition]] = {}

    @classmethod
    def register(
        cls,
        *,
        category: str,
        key: str,
        name: str,
        factory: Callable[[], BaseProvider],
    ) -> None:
        normalized_category = category.strip().lower()
        normalized_key = key.strip().lower()

        if not normalized_category:
            raise ValueError("Provider category cannot be empty.")

        if not normalized_key:
            raise ValueError("Provider key cannot be empty.")

        category_providers = cls._providers.setdefault(
            normalized_category,
            {},
        )

        if normalized_key in category_providers:
            raise ValueError(
                f"Provider already registered: "
                f"{normalized_category}/{normalized_key}"
            )

        category_providers[normalized_key] = ProviderDefinition(
            category=normalized_category,
            key=normalized_key,
            name=name,
            factory=factory,
        )

    @classmethod
    def get(
        cls,
        category: str,
        key: str,
    ) -> ProviderDefinition:
        normalized_category = category.strip().lower()
        normalized_key = key.strip().lower()

        try:
            return cls._providers[normalized_category][normalized_key]
        except KeyError as error:
            raise KeyError(
                f"Provider is not registered: "
                f"{normalized_category}/{normalized_key}"
            ) from error

    @classmethod
    def create(
        cls,
        category: str,
        key: str,
    ) -> BaseProvider:
        definition = cls.get(category, key)
        return definition.factory()

    @classmethod
    def all(
        cls,
        category: str | None = None,
    ) -> list[ProviderDefinition]:
        if category is None:
            return [
                definition
                for providers in cls._providers.values()
                for definition in providers.values()
            ]

        normalized_category = category.strip().lower()

        return list(
            cls._providers.get(normalized_category, {}).values()
        )

    @classmethod
    def categories(cls) -> list[str]:
        return sorted(cls._providers.keys())

    @classmethod
    def clear(cls) -> None:
        """Clear the registry, mainly for tests."""

        cls._providers.clear()
