import os
from dataclasses import dataclass

from dotenv import load_dotenv


load_dotenv()


@dataclass
class Settings:
    project_name: str = "DocuForge"
    version: str = "0.5.0"
    environment: str = os.getenv(
        "ENVIRONMENT",
        "development",
    )

    text_provider: str = os.getenv(
        "TEXT_PROVIDER",
        os.getenv("AI_PROVIDER", "deepseek"),
    )

    image_provider: str = os.getenv(
        "IMAGE_PROVIDER",
        "pexels",
    )

    video_provider: str = os.getenv(
        "VIDEO_PROVIDER",
        "pexels",
    )

    voice_provider: str = os.getenv(
        "VOICE_PROVIDER",
        "local_tts",
    )

    render_provider: str = os.getenv(
        "RENDER_PROVIDER",
        "supertonic",
    )

    model: str = os.getenv(
        "MODEL",
        "deepseek-chat",
    )

    deepseek_api_key: str = os.getenv(
        "DEEPSEEK_API_KEY",
        "",
    )

    pexels_api_key: str = os.getenv(
        "PEXELS_API_KEY",
        "",
    )


settings = Settings()
