from app.ai.deepseek import DeepSeekProvider
from app.providers.image.pexels import PexelsImageProvider
from app.providers.registry import ProviderRegistry
from app.providers.video.pexels import PexelsVideoProvider
from app.providers.voice.espeak import EspeakVoiceProvider

def register_default_providers() -> None:
    """Register DocuForge's built-in providers."""

    if not ProviderRegistry.all("text"):
        ProviderRegistry.register(
            category="text",
            key="deepseek",
            name="DeepSeek",
            factory=DeepSeekProvider,
        )

    if not ProviderRegistry.all("video"):
        ProviderRegistry.register(
            category="video",
            key="pexels",
            name="Pexels Videos",
            factory=PexelsVideoProvider,
        )

    if not ProviderRegistry.all("image"):
        ProviderRegistry.register(
            category="image",
            key="pexels",
            name="Pexels Images",
            factory=PexelsImageProvider,
        )
    if not ProviderRegistry.all("voice"):
        ProviderRegistry.register(
            category="voice",
            key="espeak",
            name="eSpeak NG",
            factory=EspeakVoiceProvider,
        )
