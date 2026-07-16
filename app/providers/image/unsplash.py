from pathlib import Path
from typing import Any

import requests

from app.core.config import settings
from app.providers.base import ImageProvider
from app.providers.shared.models import MediaAsset


class UnsplashImageProvider(ImageProvider):
    """Search and acquire free stock images from the Unsplash API."""

    provider_key = "unsplash"
    provider_name = "Unsplash Images"

    API_URL = "https://api.unsplash.com/search/photos"

    def __init__(self) -> None:
        super().__init__()

        if not settings.unsplash_access_key:
            raise ValueError(
                "UNSPLASH_ACCESS_KEY is not configured."
            )

        self.headers = {
            "Authorization": (
                f"Client-ID {settings.unsplash_access_key}"
            ),
        }

    def search(
        self,
        query: str,
        *,
        limit: int = 10,
        orientation: str = "landscape",
    ) -> list[MediaAsset]:
        """Search Unsplash and return normalized image assets."""

        query = query.strip()

        if not query:
            raise ValueError("Search query cannot be empty.")

        if limit < 1:
            raise ValueError("limit must be greater than zero.")

        response = requests.get(
            self.API_URL,
            headers=self.headers,
            params={
                "query": query,
                "per_page": min(limit, 30),
                "orientation": (
                    "landscape"
                    if orientation == "landscape"
                    else "portrait"
                ),
            },
            timeout=30,
        )

        response.raise_for_status()
        payload = response.json()

        results = payload.get("results", [])
        assets: list[MediaAsset] = []

        for photo in results:
            urls = photo.get("urls", {})
            download_url = urls.get("full") or urls.get("regular")

            if not download_url:
                continue

            user = photo.get("user") or {}

            asset = MediaAsset(
                asset_id=str(photo["id"]),
                provider=self.provider_key,
                media_type="image",
                download_url=download_url,
                width=photo.get("width"),
                height=photo.get("height"),
                page_url=(photo.get("links") or {}).get("html"),
                preview_url=urls.get("small"),
                author=user.get("name"),
                license_name="Unsplash",
                query=query,
                metadata={
                    "download_location": (
                        photo.get("links") or {}
                    ).get("download_location"),
                    "user_url": (user.get("links") or {}).get(
                        "html"
                    ),
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
                / f"unsplash_{asset.asset_id}_{index}.jpg"
            )

            MediaDownloader.download(
                asset.download_url,
                destination,
            )

            self._track_download(asset)

            downloaded.append(destination)

        return downloaded

    def _track_download(self, asset: MediaAsset) -> None:
        """Best-effort ping of Unsplash's required download-tracking endpoint."""

        download_location = (asset.metadata or {}).get(
            "download_location"
        )

        if not download_location:
            return

        try:
            requests.get(
                download_location,
                headers=self.headers,
                timeout=10,
            )
        except requests.RequestException:
            pass
