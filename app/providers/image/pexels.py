from pathlib import Path
from typing import Any

import requests

from app.core.config import settings
from app.providers.base import ImageProvider
from app.providers.shared.models import MediaAsset


class PexelsImageProvider(ImageProvider):
    """Search and acquire images from the Pexels API."""

    provider_key = "pexels"
    provider_name = "Pexels Images"

    API_URL = "https://api.pexels.com/v1/search"

    def __init__(self) -> None:
        super().__init__()

        if not settings.pexels_api_key:
            raise ValueError(
                "PEXELS_API_KEY is not configured."
            )

        self.headers = {
            "Authorization": settings.pexels_api_key,
        }

    def search(
        self,
        query: str,
        *,
        limit: int = 10,
        orientation: str = "landscape",
    ) -> list[MediaAsset]:
        """Search Pexels and return normalized image assets."""

        if not query.strip():
            raise ValueError("Search query cannot be empty.")

        if limit < 1:
            raise ValueError("limit must be greater than zero.")

        response = requests.get(
            self.API_URL,
            headers=self.headers,
            params={
                "query": query,
                "per_page": min(limit, 80),
                "orientation": orientation,
            },
            timeout=30,
        )

        response.raise_for_status()
        payload = response.json()

        photos = payload.get("photos", [])

        assets: list[MediaAsset] = []

        for photo in photos:
            src = photo.get("src", {})

            download_url = (
                src.get("original")
                or src.get("large2x")
                or src.get("large")
            )

            if not download_url:
                continue

            asset = MediaAsset(
                asset_id=str(photo["id"]),
                provider=self.provider_key,
                media_type="image",
                download_url=download_url,
                width=photo.get("width"),
                height=photo.get("height"),
                page_url=photo.get("url"),
                preview_url=src.get("medium"),
                author=photo.get("photographer"),
                license_name="Pexels",
                query=query,
                metadata={
                    "photographer_url": photo.get(
                        "photographer_url"
                    ),
                    "average_color": photo.get("avg_color"),
                    "alt": photo.get("alt"),
                },
            )

            assets.append(asset)

        return assets

    def get_images(
        self,
        query: str,
        output_dir: Path,
        limit: int = 1,
        **options: Any,
    ) -> list[Path]:
        """Search images and download the selected results."""

        from app.providers.shared.downloader import MediaDownloader

        assets = self.search(
            query,
            limit=limit,
            orientation=options.get(
                "orientation",
                "landscape",
            ),
        )

        downloaded: list[Path] = []

        for index, asset in enumerate(
            assets[:limit],
            start=1,
        ):
            destination = (
                output_dir
                / f"pexels_{asset.asset_id}_{index}.jpg"
            )

            MediaDownloader.download(
                asset.download_url,
                destination,
            )

            downloaded.append(destination)

        return downloaded
