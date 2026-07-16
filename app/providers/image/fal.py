from pathlib import Path
from typing import Any

from app.core.config import settings
from app.providers.base import ImageProvider
from app.providers.shared.downloader import MediaDownloader
from app.providers.shared.fal_queue import FalQueueClient


class FalImageProvider(ImageProvider):
    """Generate images via fal.ai's model aggregator (Flux, etc.).

    fal.ai hosts hundreds of models behind one queue API. The model to
    use is a fal.ai endpoint path (e.g. "fal-ai/flux/dev"), configurable
    via the "model" option; DEFAULT_MODEL is used otherwise.
    """

    provider_key = "fal"
    provider_name = "fal.ai (Flux and others)"

    DEFAULT_MODEL = "fal-ai/flux/schnell"

    def __init__(self) -> None:
        super().__init__()

        if not settings.fal_api_key:
            raise ValueError(
                "FAL_KEY is not configured."
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

        model = str(options.get("model", self.DEFAULT_MODEL))
        aspect_ratio = self._resolve_aspect_ratio(
            options.get("orientation", "landscape")
        )

        client = FalQueueClient(settings.fal_api_key)
        result = client.run(
            model,
            {
                "prompt": prompt,
                "num_images": min(max(limit, 1), 4),
                "image_size": aspect_ratio,
            },
        )

        image_urls = self._extract_image_urls(result)

        if not image_urls:
            raise RuntimeError(
                f"Unexpected fal.ai image response shape: {result}"
            )

        output_dir.mkdir(parents=True, exist_ok=True)
        downloaded: list[Path] = []

        for index, url in enumerate(image_urls[:limit], start=1):
            destination = (
                output_dir / f"fal_{abs(hash(prompt))}_{index}.png"
            )

            MediaDownloader.download(url, destination)
            downloaded.append(destination)

        return downloaded

    def _extract_image_urls(
        self,
        result: dict[str, Any],
    ) -> list[str]:
        images = result.get("images")

        if isinstance(images, list):
            return [
                item["url"]
                for item in images
                if isinstance(item, dict) and item.get("url")
            ]

        image = result.get("image")

        if isinstance(image, dict) and image.get("url"):
            return [image["url"]]

        return []

    def _resolve_aspect_ratio(self, orientation: str) -> str:
        if orientation == "landscape":
            return "landscape_16_9"

        if orientation == "portrait":
            return "portrait_16_9"

        return "square_hd"
