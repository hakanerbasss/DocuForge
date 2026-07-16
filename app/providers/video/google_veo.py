import time
from pathlib import Path
from typing import Any

import requests

from app.core.config import settings
from app.providers.base import VideoProvider


class GoogleVeoProvider(VideoProvider):
    """Generate videos with Google's Veo models via the Gemini API.

    Veo runs as a long-running operation: submit -> poll -> download.
    The completed operation's video reference path
    (response.generateVideoResponse.generatedSamples[0].video.uri) is
    documented, but whether that URI is directly fetchable with just the
    API key header (vs. requiring the Files API) has not been verified
    against live traffic in this codebase. Validate with a real
    GOOGLE_API_KEY before relying on this in production.
    """

    provider_key = "google_veo"
    provider_name = "Google Veo"

    MODEL_NAME = "veo-3.1-generate-preview"
    API_BASE = "https://generativelanguage.googleapis.com/v1beta"
    POLL_INTERVAL_SECONDS = 10
    MAX_WAIT_SECONDS = 600

    def __init__(self) -> None:
        super().__init__()

        if not settings.google_api_key:
            raise ValueError(
                "GOOGLE_API_KEY is not configured."
            )

    def get_videos(
        self,
        query: str,
        output_dir: Path,
        limit: int = 1,
        **options: Any,
    ) -> list[Path]:
        """Generate videos from a text prompt and save them locally."""

        prompt = query.strip()

        if not prompt:
            raise ValueError("Prompt cannot be empty.")

        if limit < 1:
            raise ValueError("limit must be greater than zero.")

        aspect_ratio = self._resolve_aspect_ratio(
            options.get("orientation", "landscape")
        )

        output_dir.mkdir(parents=True, exist_ok=True)
        downloaded: list[Path] = []

        for index in range(1, limit + 1):
            operation_name = self._start_generation(
                prompt,
                aspect_ratio,
            )
            video_uri = self._poll_until_done(operation_name)

            destination = (
                output_dir / f"veo_{abs(hash(prompt))}_{index}.mp4"
            )

            self._download_video(video_uri, destination)
            downloaded.append(destination)

        return downloaded

    def _start_generation(
        self,
        prompt: str,
        aspect_ratio: str,
    ) -> str:
        response = requests.post(
            f"{self.API_BASE}/models/{self.MODEL_NAME}:predictLongRunning",
            headers={
                "x-goog-api-key": settings.google_api_key,
                "Content-Type": "application/json",
            },
            json={
                "instances": [{"prompt": prompt}],
                "parameters": {"aspectRatio": aspect_ratio},
            },
            timeout=60,
        )

        response.raise_for_status()
        payload = response.json()

        operation_name = payload.get("name")

        if not operation_name:
            raise RuntimeError(
                f"Veo did not return an operation name: {payload}"
            )

        return operation_name

    def _poll_until_done(self, operation_name: str) -> str:
        elapsed = 0

        while elapsed < self.MAX_WAIT_SECONDS:
            response = requests.get(
                f"{self.API_BASE}/{operation_name}",
                headers={
                    "x-goog-api-key": settings.google_api_key,
                },
                timeout=30,
            )

            response.raise_for_status()
            payload = response.json()

            if payload.get("done"):
                if "error" in payload:
                    raise RuntimeError(
                        f"Veo generation failed: {payload['error']}"
                    )

                try:
                    samples = payload["response"][
                        "generateVideoResponse"
                    ]["generatedSamples"]
                    return samples[0]["video"]["uri"]
                except (KeyError, IndexError) as error:
                    raise RuntimeError(
                        "Unexpected Veo operation response shape: "
                        f"{payload}"
                    ) from error

            time.sleep(self.POLL_INTERVAL_SECONDS)
            elapsed += self.POLL_INTERVAL_SECONDS

        raise TimeoutError(
            "Veo generation did not complete within "
            f"{self.MAX_WAIT_SECONDS}s."
        )

    def _download_video(
        self,
        video_uri: str,
        destination: Path,
    ) -> None:
        response = requests.get(
            video_uri,
            headers={"x-goog-api-key": settings.google_api_key},
            timeout=120,
        )

        response.raise_for_status()
        destination.write_bytes(response.content)

        if (
            not destination.exists()
            or destination.stat().st_size == 0
        ):
            raise RuntimeError(
                f"Veo output was not created: {destination}"
            )

    def _resolve_aspect_ratio(self, orientation: str) -> str:
        if orientation == "landscape":
            return "16:9"

        if orientation == "portrait":
            return "9:16"

        return "1:1"
