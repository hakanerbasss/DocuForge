import base64
from pathlib import Path
from typing import Any

from app.core.config import settings
from app.providers.base import ImageProvider


class DalleImageProvider(ImageProvider):
    """Generate images with OpenAI's Images API (gpt-image-1)."""

    provider_key = "dalle"
    provider_name = "DALL-E (OpenAI Images)"

    MODEL_NAME = "gpt-image-1"

    _client = None

    def __init__(self) -> None:
        super().__init__()

        if not settings.openai_api_key:
            raise ValueError(
                "OPENAI_API_KEY is not configured."
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

        size = self._resolve_size(
            options.get("orientation", "landscape")
        )
        quality = str(options.get("quality", "medium"))

        client = self._get_client()
        output_dir.mkdir(parents=True, exist_ok=True)

        downloaded: list[Path] = []

        # gpt-image-1 only returns one image per call; loop for more.
        for index in range(1, limit + 1):
            response = client.images.generate(
                model=self.MODEL_NAME,
                prompt=prompt,
                size=size,
                quality=quality,
                n=1,
            )

            image_b64 = response.data[0].b64_json

            if not image_b64:
                raise RuntimeError(
                    "OpenAI Images API returned no image data."
                )

            destination = (
                output_dir / f"dalle_{abs(hash(prompt))}_{index}.png"
            )

            destination.write_bytes(
                base64.b64decode(image_b64)
            )

            if (
                not destination.exists()
                or destination.stat().st_size == 0
            ):
                raise RuntimeError(
                    f"DALL-E output was not created: {destination}"
                )

            downloaded.append(destination)

        return downloaded

    def _resolve_size(self, orientation: str) -> str:
        if orientation == "landscape":
            return "1536x1024"

        if orientation == "portrait":
            return "1024x1536"

        return "1024x1024"

    @classmethod
    def _get_client(cls):
        if cls._client is None:
            from openai import OpenAI

            cls._client = OpenAI(api_key=settings.openai_api_key)

        return cls._client
