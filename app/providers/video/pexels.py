from pathlib import Path
from typing import Any

import requests

from app.core.config import settings
from app.providers.base import VideoProvider
from app.providers.shared.downloader import MediaDownloader
from app.providers.shared.models import MediaAsset


class PexelsVideoProvider(VideoProvider):
    """Search and download videos from the Pexels API."""

    provider_key = "pexels"
    provider_name = "Pexels Videos"

    API_URL = "https://api.pexels.com/videos/search"

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
        min_width: int = 1280,
    ) -> list[MediaAsset]:
        """Search Pexels and return normalized video assets."""

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
                "per_page": min(limit, 80),
                "orientation": orientation,
            },
            timeout=30,
        )

        response.raise_for_status()
        payload = response.json()

        videos = payload.get("videos", [])
        assets: list[MediaAsset] = []

        for video in videos:
            video_file = self._select_video_file(
                video.get("video_files", []),
                min_width=min_width,
            )

            if video_file is None:
                continue

            user = video.get("user") or {}
            video_pictures = video.get("video_pictures") or []

            preview_url = None

            if video_pictures:
                preview_url = video_pictures[0].get("picture")

            asset = MediaAsset(
                asset_id=str(video["id"]),
                provider=self.provider_key,
                media_type="video",
                download_url=video_file["link"],
                width=video_file.get("width"),
                height=video_file.get("height"),
                duration=float(video["duration"])
                if video.get("duration")
                else None,
                page_url=video.get("url"),
                preview_url=preview_url,
                author=user.get("name"),
                license_name="Pexels",
                query=query,
                metadata={
                    "video_file_id": video_file.get("id"),
                    "quality": video_file.get("quality"),
                    "file_type": video_file.get("file_type"),
                    "user_url": user.get("url"),
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
                / f"pexels_{asset.asset_id}_{index}.mp4"
            )

            MediaDownloader.download(
                asset.download_url,
                destination,
            )

            downloaded.append(destination)

        return downloaded

    def _select_video_file(
        self,
        video_files: list[dict[str, Any]],
        *,
        min_width: int,
    ) -> dict[str, Any] | None:
        """Choose a suitable landscape MP4 file."""

        candidates = [
            video_file
            for video_file in video_files
            if video_file.get("file_type") == "video/mp4"
            and isinstance(video_file.get("width"), int)
            and isinstance(video_file.get("height"), int)
            and video_file["width"] >= min_width
            and video_file["width"] > video_file["height"]
            and video_file.get("link")
        ]

        if not candidates:
            candidates = [
                video_file
                for video_file in video_files
                if video_file.get("file_type") == "video/mp4"
                and video_file.get("link")
            ]

        if not candidates:
            return None

        return max(
            candidates,
            key=lambda item: (
                item.get("width") or 0,
                item.get("height") or 0,
            ),
        )
