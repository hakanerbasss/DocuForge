from pathlib import Path
from typing import Any

import requests

from app.core.config import settings
from app.providers.base import VideoProvider
from app.providers.shared.downloader import MediaDownloader
from app.providers.shared.models import MediaAsset


class PixabayVideoProvider(VideoProvider):
    """Search and download free stock videos from the Pixabay API."""

    provider_key = "pixabay"
    provider_name = "Pixabay Videos"

    API_URL = "https://pixabay.com/api/videos/"

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
        min_width: int = 1280,
    ) -> list[MediaAsset]:
        """Search Pixabay and return normalized video assets."""

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
            video_file = self._select_video_file(
                hit.get("videos", {}),
                min_width=min_width,
                orientation=orientation,
            )

            if video_file is None:
                continue

            asset = MediaAsset(
                asset_id=str(hit["id"]),
                provider=self.provider_key,
                media_type="video",
                download_url=video_file["url"],
                width=video_file.get("width"),
                height=video_file.get("height"),
                duration=float(hit["duration"])
                if hit.get("duration")
                else None,
                page_url=hit.get("pageURL"),
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

    def get_videos(
        self,
        query: str,
        output_dir: Path,
        limit: int = 1,
        **options: Any,
    ) -> list[Path]:
        """Search videos and download selected results."""

        assets = self.search(
            query,
            limit=limit,
            orientation=options.get(
                "orientation",
                "landscape",
            ),
            min_width=options.get(
                "min_width",
                1280,
            ),
        )

        downloaded: list[Path] = []

        for index, asset in enumerate(
            assets[:limit],
            start=1,
        ):
            destination = (
                output_dir
                / f"pixabay_{asset.asset_id}_{index}.mp4"
            )

            MediaDownloader.download(
                asset.download_url,
                destination,
            )

            downloaded.append(destination)

        return downloaded

    def _select_video_file(
        self,
        videos: dict[str, Any],
        *,
        min_width: int,
        orientation: str,
    ) -> dict[str, Any] | None:
        """Choose the largest suitable rendition Pixabay offers."""

        candidates = [
            {**rendition, "quality": quality}
            for quality, rendition in videos.items()
            if isinstance(rendition, dict) and rendition.get("url")
        ]

        if not candidates:
            return None

        landscape_matches = [
            item
            for item in candidates
            if orientation != "landscape"
            or (
                isinstance(item.get("width"), int)
                and isinstance(item.get("height"), int)
                and item["width"] >= item["height"]
            )
        ]

        pool = landscape_matches or candidates

        wide_enough = [
            item
            for item in pool
            if isinstance(item.get("width"), int)
            and item["width"] >= min_width
        ]

        pool = wide_enough or pool

        return max(
            pool,
            key=lambda item: (
                item.get("width") or 0,
                item.get("height") or 0,
            ),
        )
