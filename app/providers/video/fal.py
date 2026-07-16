from pathlib import Path
from typing import Any

from app.core.config import settings
from app.providers.base import VideoProvider
from app.providers.shared.downloader import MediaDownloader
from app.providers.shared.fal_queue import FalQueueClient


class FalVideoProvider(VideoProvider):
    """Generate videos via fal.ai's model aggregator (Kling, and others).

    fal.ai hosts hundreds of models behind one queue API. The model to
    use is a fal.ai endpoint path (e.g. "fal-ai/kling-video/v1.6/standard/
    text-to-video"), configurable via the "model" option; DEFAULT_MODEL
    is used otherwise. Request/response field names are not fully
    standardized across fal's model catalog -- this targets the
    text-to-video convention (prompt, aspect_ratio, duration in) most
    models share, and reads video.url or video_url from the result.
    """

    provider_key = "fal"
    provider_name = "fal.ai (Kling and others)"

    DEFAULT_MODEL = "fal-ai/kling-video/v1.6/standard/text-to-video"

    def __init__(self) -> None:
        super().__init__()

        if not settings.fal_api_key:
            raise ValueError(
                "FAL_KEY is not configured."
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

        model = str(options.get("model", self.DEFAULT_MODEL))
        aspect_ratio = self._resolve_aspect_ratio(
            options.get("orientation", "landscape")
        )
        duration = str(options.get("duration", "5"))

        client = FalQueueClient(settings.fal_api_key)

        output_dir.mkdir(parents=True, exist_ok=True)
        downloaded: list[Path] = []

        for index in range(1, limit + 1):
            result = client.run(
                model,
                {
                    "prompt": prompt,
                    "aspect_ratio": aspect_ratio,
                    "duration": duration,
                },
            )

            video_url = self._extract_video_url(result)

            if not video_url:
                raise RuntimeError(
                    f"Unexpected fal.ai video response shape: {result}"
                )

            destination = (
                output_dir / f"fal_{abs(hash(prompt))}_{index}.mp4"
            )

            MediaDownloader.download(video_url, destination)
            downloaded.append(destination)

        return downloaded

    def _extract_video_url(
        self,
        result: dict[str, Any],
    ) -> str | None:
        video = result.get("video")

        if isinstance(video, dict) and video.get("url"):
            return video["url"]

        video_url = result.get("video_url")

        if isinstance(video_url, str) and video_url:
            return video_url

        return None

    def _resolve_aspect_ratio(self, orientation: str) -> str:
        if orientation == "landscape":
            return "16:9"

        if orientation == "portrait":
            return "9:16"

        return "1:1"
