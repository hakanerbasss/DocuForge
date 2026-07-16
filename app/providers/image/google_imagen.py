import base64
from pathlib import Path
from typing import Any

import requests

from app.core.config import settings
from app.providers.base import ImageProvider


class GoogleImagenProvider(ImageProvider):
    """Generate images with Google's Imagen models via the Gemini API."""

    provider_key = "google_imagen"
    provider_name = "Google Imagen"

    MODEL_NAME = "imagen-4.0-generate-001"
    API_BASE = "https://generativelanguage.googleapis.com/v1beta"

    def __init__(self) -> None:
        super().__init__()

        if not settings.google_api_key:
            raise ValueError(
                "GOOGLE_API_KEY is not configured."
            )

    def get_images(
        self,
        query: str,
        output_dir: Path,
        limit: int = 1,
        **options: Any,
    ) -> list[Path]:
        """Generate images from a text prompt and save them locally."""

        prompt = query.strip()

        if not prompt:
            raise ValueError("Prompt cannot be empty.")

        if limit < 1:
            raise ValueError("limit must be greater than zero.")

        aspect_ratio = self._resolve_aspect_ratio(
            options.get("orientation", "landscape")
        )

        response = requests.post(
            f"{self.API_BASE}/models/{self.MODEL_NAME}:predict",
            headers={
                "x-goog-api-key": settings.google_api_key,
                "Content-Type": "application/json",
            },
            json={
                "instances": [{"prompt": prompt}],
                "parameters": {
                    "sampleCount": min(max(limit, 1), 4),
                    "aspectRatio": aspect_ratio,
                },
            },
            timeout=120,
        )

        response.raise_for_status()
        payload = response.json()

        predictions = payload.get("predictions", [])

        if not predictions:
            raise RuntimeError(
                f"Imagen returned no predictions: {payload}"
            )

        output_dir.mkdir(parents=True, exist_ok=True)
        downloaded: list[Path] = []

        for index, prediction in enumerate(
            predictions[:limit],
            start=1,
        ):
            image_b64 = prediction.get("bytesBase64Encoded")

            if not image_b64:
                continue

            destination = (
                output_dir / f"imagen_{abs(hash(prompt))}_{index}.png"
            )

            destination.write_bytes(
                base64.b64decode(image_b64)
            )

            downloaded.append(destination)

        if not downloaded:
            raise RuntimeError(
                "Imagen did not return any usable image data."
            )

        return downloaded

    def _resolve_aspect_ratio(self, orientation: str) -> str:
        if orientation == "landscape":
            return "16:9"

        if orientation == "portrait":
            return "9:16"

        return "1:1"
