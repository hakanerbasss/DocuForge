from app.providers.voice.supertonic import (
    SupertonicVoiceProvider,
)
from app.ai.deepseek import DeepSeekProvider
from app.providers.voice.piper import PiperVoiceProvider
from app.providers.voice.xtts import XTTSVoiceProvider
from app.providers.image.pexels import PexelsImageProvider
from app.providers.registry import ProviderRegistry
from app.providers.video.pexels import PexelsVideoProvider
from app.providers.voice.espeak import EspeakVoiceProvider


def register_default_providers() -> None:
    """Register DocuForge built-in providers."""

    registered = {
        (provider.category, provider.key)
        for provider in ProviderRegistry.all()
    }

    if ("text", "deepseek") not in registered:
        ProviderRegistry.register(
            category="text",
            key="deepseek",
            name="DeepSeek",
            factory=DeepSeekProvider,
        )

    if ("image", "pexels") not in registered:
        ProviderRegistry.register(
            category="image",
            key="pexels",
            name="Pexels Images",
            factory=PexelsImageProvider,
        )

    if ("video", "pexels") not in registered:
        ProviderRegistry.register(
            category="video",
            key="pexels",
            name="Pexels Videos",
            factory=PexelsVideoProvider,
        )

    if ("voice", "espeak") not in registered:
        ProviderRegistry.register(
            category="voice",
            key="espeak",
            name="eSpeak NG",
            factory=EspeakVoiceProvider,
        )

    # Generic local TTS alias.
    if ("voice", "local_tts") not in registered:
        ProviderRegistry.register(
            category="voice",
            key="local_tts",
            name="Local TTS (eSpeak NG)",
            factory=EspeakVoiceProvider,
        )

    if ("voice", "piper") not in registered:
        ProviderRegistry.register(
            category="voice",
            key="piper",
            name="Piper TTS",
            factory=PiperVoiceProvider,
        )

    if ("voice", "supertonic") not in registered:
        ProviderRegistry.register(
            category="voice",
            key="supertonic",
            name="Supertonic",
            factory=SupertonicVoiceProvider,
        )

    if ("voice", "xtts") not in registered:
        ProviderRegistry.register(
            category="voice",
            key="xtts",
            name="XTTS Voice Clone",
            factory=XTTSVoiceProvider,
        )
