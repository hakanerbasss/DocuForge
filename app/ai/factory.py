from app.core.config import settings
from app.providers.base import TextProvider
from app.providers.defaults import register_default_providers
from app.providers.registry import ProviderRegistry


def get_ai() -> TextProvider:
    """Return the configured text provider."""

    register_default_providers()

    provider = ProviderRegistry.create(
        category="text",
        key=settings.text_provider,
    )

    if not isinstance(provider, TextProvider):
        raise TypeError(
            "Configured provider is not a text provider: "
            f"{settings.text_provider}"
        )

    return provider
