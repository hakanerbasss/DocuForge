from pathlib import Path
from typing import Any

import requests

from app.core.config import settings
from app.providers.base import MusicProvider
from app.providers.shared.downloader import MediaDownloader


class MubertMusicProvider(MusicProvider):
    """Generate AI royalty-free background music via the Mubert API.

    Mubert's API 3.0 uses a two-step auth: create a "customer" from a
    company-id + license-token, get back a customer-id + access-token,
    then use those to request a generated track. The exact request/
    response body for track generation (genre/mood/duration parameter
    names, and which field in the response holds the final audio URL)
    is not fully documented in public examples and has not been
    exercised against a live account in this codebase -- treat this as
    a best-effort starting point, not a verified integration. Confirm
    the actual request/response shape against Mubert's current docs
    (or support) before relying on it in production.
    """

    provider_key = "mubert"
    provider_name = "Mubert (AI music)"

    API_BASE = "https://music-api.mubert.com/api/v3"

    def __init__(self) -> None:
        super().__init__()

        if not settings.mubert_company_id:
            raise ValueError(
                "MUBERT_COMPANY_ID is not configured."
            )

        if not settings.mubert_license_token:
            raise ValueError(
                "MUBERT_LICENSE_TOKEN is not configured."
            )

    def get_music(
        self,
        query: str,
        output_dir: Path,
        **options: Any,
    ) -> Path:
        """Generate a background music track and download it."""

        customer_id, access_token = self._get_customer_credentials()

        duration_seconds = int(options.get("duration_seconds", 60))

        response = requests.post(
            f"{self.API_BASE}/public/tracks",
            headers={
                "customer-id": customer_id,
                "access-token": access_token,
                "Content-Type": "application/json",
            },
            json={
                "prompt": query.strip() or "cinematic background music",
                "duration": duration_seconds,
            },
            timeout=60,
        )

        response.raise_for_status()
        payload = response.json()

        download_url = (
            payload.get("audio_url")
            or payload.get("url")
            or payload.get("download_url")
        )

        if not download_url:
            raise RuntimeError(
                f"Unexpected Mubert track response shape: {payload}"
            )

        output_dir.mkdir(parents=True, exist_ok=True)
        destination = output_dir / "mubert_track.mp3"

        MediaDownloader.download(download_url, destination)

        return destination

    def _get_customer_credentials(self) -> tuple[str, str]:
        response = requests.post(
            f"{self.API_BASE}/customers",
            headers={
                "company-id": settings.mubert_company_id,
                "license-token": settings.mubert_license_token,
                "Content-Type": "application/json",
            },
            json={},
            timeout=30,
        )

        response.raise_for_status()
        payload = response.json()

        customer_id = payload.get("customer_id") or payload.get("id")
        access_token = payload.get("access_token") or payload.get("token")

        if not customer_id or not access_token:
            raise RuntimeError(
                f"Unexpected Mubert customer response shape: {payload}"
            )

        return customer_id, access_token
