from app.providers.voice.supertonic import (
    SupertonicVoiceProvider,
)
from app.ai.deepseek import DeepSeekProvider
from app.providers.voice.piper import PiperVoiceProvider
from app.providers.voice.xtts import XTTSVoiceProvider
from app.providers.image.pexels import PexelsImageProvider
from app.providers.image.pixabay import PixabayImageProvider
from app.providers.image.unsplash import UnsplashImageProvider
from app.providers.image.dalle import DalleImageProvider
from app.providers.image.google_imagen import GoogleImagenProvider
from app.providers.image.fal import FalImageProvider
from app.providers.registry import ProviderRegistry
from app.providers.video.pexels import PexelsVideoProvider
from app.providers.video.pixabay import PixabayVideoProvider
from app.providers.video.google_veo import GoogleVeoProvider
from app.providers.video.fal import FalVideoProvider
from app.providers.voice.espeak import EspeakVoiceProvider
from app.providers.music.jamendo import JamendoMusicProvider
from app.providers.music.mubert import MubertMusicProvider


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

    if ("image", "pixabay") not in registered:
        ProviderRegistry.register(
            category="image",
            key="pixabay",
            name="Pixabay Images",
            factory=PixabayImageProvider,
        )

    if ("video", "pixabay") not in registered:
        ProviderRegistry.register(
            category="video",
            key="pixabay",
            name="Pixabay Videos",
            factory=PixabayVideoProvider,
        )

    if ("image", "unsplash") not in registered:
        ProviderRegistry.register(
            category="image",
            key="unsplash",
            name="Unsplash Images",
            factory=UnsplashImageProvider,
        )

    if ("image", "dalle") not in registered:
        ProviderRegistry.register(
            category="image",
            key="dalle",
            name="DALL-E (OpenAI Images)",
            factory=DalleImageProvider,
        )

    if ("image", "google_imagen") not in registered:
        ProviderRegistry.register(
            category="image",
            key="google_imagen",
            name="Google Imagen",
            factory=GoogleImagenProvider,
        )

    if ("video", "google_veo") not in registered:
        ProviderRegistry.register(
            category="video",
            key="google_veo",
            name="Google Veo",
            factory=GoogleVeoProvider,
        )

    if ("image", "fal") not in registered:
        ProviderRegistry.register(
            category="image",
            key="fal",
            name="fal.ai (Flux and others)",
            factory=FalImageProvider,
        )

    if ("video", "fal") not in registered:
        ProviderRegistry.register(
            category="video",
            key="fal",
            name="fal.ai (Kling and others)",
            factory=FalVideoProvider,
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

    if ("music", "jamendo") not in registered:
        ProviderRegistry.register(
            category="music",
            key="jamendo",
            name="Jamendo (royalty-free)",
            factory=JamendoMusicProvider,
        )

    if ("music", "mubert") not in registered:
        ProviderRegistry.register(
            category="music",
            key="mubert",
            name="Mubert (AI music)",
            factory=MubertMusicProvider,
        )
