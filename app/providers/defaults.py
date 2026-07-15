from app.ai.deepseek import DeepSeekProvider
from app.providers.registry import ProviderRegistry


def register_default_providers() -> None:
    """Register DocuForge's built-in providers."""

    existing_text_providers = ProviderRegistry.all("text")

    if existing_text_providers:
        return

    ProviderRegistry.register(
        category="text",
        key="deepseek",
        name="DeepSeek",
        factory=DeepSeekProvider,
    )
