import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from dotenv import load_dotenv


load_dotenv()

SECRETS_PATH = Path("secrets.json")

# env var name -> secrets.json key, for every secret the /settings page manages.
SECRET_FIELDS: dict[str, str] = {
    "DEEPSEEK_API_KEY": "deepseek_api_key",
    "PEXELS_API_KEY": "pexels_api_key",
    "PIXABAY_API_KEY": "pixabay_api_key",
    "UNSPLASH_ACCESS_KEY": "unsplash_access_key",
    "OPENAI_API_KEY": "openai_api_key",
    "GOOGLE_API_KEY": "google_api_key",
    "FAL_KEY": "fal_api_key",
    "XTTS_REFERENCE_AUDIO": "xtts_reference_audio",
    "CLOSING_IMAGE": "closing_image",
    "CLOSING_IMAGE_ENABLED": "closing_image_enabled",
    "CHANNEL_LOGO": "channel_logo",
    "CHANNEL_LOGO_ENABLED": "channel_logo_enabled",
    "JAMENDO_CLIENT_ID": "jamendo_client_id",
    "MUBERT_COMPANY_ID": "mubert_company_id",
    "MUBERT_LICENSE_TOKEN": "mubert_license_token",
    "ELEVENLABS_API_KEY": "elevenlabs_api_key",
    "FREESOUND_API_KEY": "freesound_api_key",
}


def _load_secrets() -> dict[str, Any]:
    if not SECRETS_PATH.exists():
        return {}

    try:
        data = json.loads(SECRETS_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}

    return data if isinstance(data, dict) else {}


def _resolve_secret(env_name: str, secrets_key: str, secrets: dict[str, Any]) -> str:
    """An explicit env var always wins; otherwise fall back to secrets.json."""

    return os.getenv(env_name) or str(secrets.get(secrets_key, "") or "")


_secrets = _load_secrets()


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

    deepseek_api_key: str = _resolve_secret(
        "DEEPSEEK_API_KEY", "deepseek_api_key", _secrets
    )

    pexels_api_key: str = _resolve_secret(
        "PEXELS_API_KEY", "pexels_api_key", _secrets
    )

    pixabay_api_key: str = _resolve_secret(
        "PIXABAY_API_KEY", "pixabay_api_key", _secrets
    )

    unsplash_access_key: str = _resolve_secret(
        "UNSPLASH_ACCESS_KEY", "unsplash_access_key", _secrets
    )

    openai_api_key: str = _resolve_secret(
        "OPENAI_API_KEY", "openai_api_key", _secrets
    )

    google_api_key: str = _resolve_secret(
        "GOOGLE_API_KEY", "google_api_key", _secrets
    )

    fal_api_key: str = _resolve_secret(
        "FAL_KEY", "fal_api_key", _secrets
    )

    xtts_reference_audio: str = _resolve_secret(
        "XTTS_REFERENCE_AUDIO", "xtts_reference_audio", _secrets
    )

    closing_image: str = _resolve_secret(
        "CLOSING_IMAGE", "closing_image", _secrets
    )

    closing_image_enabled: str = _resolve_secret(
        "CLOSING_IMAGE_ENABLED", "closing_image_enabled", _secrets
    )

    channel_logo: str = _resolve_secret(
        "CHANNEL_LOGO", "channel_logo", _secrets
    )

    channel_logo_enabled: str = _resolve_secret(
        "CHANNEL_LOGO_ENABLED", "channel_logo_enabled", _secrets
    )

    jamendo_client_id: str = _resolve_secret(
        "JAMENDO_CLIENT_ID", "jamendo_client_id", _secrets
    )

    mubert_company_id: str = _resolve_secret(
        "MUBERT_COMPANY_ID", "mubert_company_id", _secrets
    )

    mubert_license_token: str = _resolve_secret(
        "MUBERT_LICENSE_TOKEN", "mubert_license_token", _secrets
    )

    elevenlabs_api_key: str = _resolve_secret(
        "ELEVENLABS_API_KEY", "elevenlabs_api_key", _secrets
    )

    freesound_api_key: str = _resolve_secret(
        "FREESOUND_API_KEY", "freesound_api_key", _secrets
    )

    def save_secret(self, secrets_key: str, value: str) -> None:
        """Persist a secret to secrets.json and update the live instance.

        Takes effect immediately for the running process -- no restart
        needed -- and survives one, since the next process start reads
        secrets.json again (unless an env var overrides it).
        """

        if secrets_key not in SECRET_FIELDS.values():
            raise ValueError(f"Unknown secret field: {secrets_key}")

        secrets = _load_secrets()
        secrets[secrets_key] = value

        SECRETS_PATH.write_text(
            json.dumps(secrets, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

        setattr(self, secrets_key, value)

    def is_configured(self, secrets_key: str) -> bool:
        return bool(getattr(self, secrets_key, ""))


settings = Settings()
