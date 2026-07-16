from pathlib import Path
from typing import Any

import requests

from app.core.config import settings
from app.providers.base import ImageProvider
from app.providers.shared.models import MediaAsset


class PixabayImageProvider(ImageProvider):
    """Search and acquire free stock images from the Pixabay API."""

    provider_key = "pixabay"
    provider_name = "Pixabay Images"

    API_URL = "https://pixabay.com/api/"

    def __init__(self) -> None:
        super().__init__()

        if not settings.pixabay_api_key:
            raise ValueError(
                "PIXABAY_API_KEY is not configured."
            )

    def search(
        self,
        query: str,
        *,
        limit: int = 10,
        orientation: str = "landscape",
    ) -> list[MediaAsset]:
        """Search Pixabay and return normalized image assets."""

        query = query.strip()

        if not query:
            raise ValueError("Search query cannot be empty.")

        if limit < 1:
            raise ValueError("limit must be greater than zero.")

        response = requests.get(
            self.API_URL,
            params={
                "key": settings.pixabay_api_key,
                "q": query,
                "image_type": "photo",
                "orientation": (
                    "horizontal"
                    if orientation == "landscape"
                    else "vertical"
                ),
                "per_page": max(min(limit, 200), 3),
                "safesearch": "true",
            },
            timeout=30,
        )

        response.raise_for_status()
        payload = response.json()

        hits = payload.get("hits", [])
        assets: list[MediaAsset] = []

        for hit in hits:
            download_url = (
                hit.get("largeImageURL")
                or hit.get("webformatURL")
            )

            if not download_url:
                continue

            asset = MediaAsset(
                asset_id=str(hit["id"]),
                provider=self.provider_key,
                media_type="image",
                download_url=download_url,
                width=hit.get("imageWidth"),
                height=hit.get("imageHeight"),
                page_url=hit.get("pageURL"),
                preview_url=hit.get("previewURL"),
                author=hit.get("user"),
                license_name="Pixabay",
                query=query,
                metadata={
                    "tags": hit.get("tags"),
                    "user_id": hit.get("user_id"),
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
                / f"pixabay_{asset.asset_id}_{index}.jpg"
            )

            MediaDownloader.download(
                asset.download_url,
                destination,
            )

            downloaded.append(destination)

        return downloaded
