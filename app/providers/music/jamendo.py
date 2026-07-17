from pathlib import Path
from typing import Any

import requests

from app.core.config import settings
from app.providers.base import MusicProvider
from app.providers.shared.downloader import MediaDownloader


class JamendoMusicProvider(MusicProvider):
    """Search and download royalty-free background music from Jamendo."""

    provider_key = "jamendo"
    provider_name = "Jamendo (royalty-free)"

    API_URL = "https://api.jamendo.com/v3.0/tracks/"

    def __init__(self) -> None:
        super().__init__()

        if not settings.jamendo_client_id:
            raise ValueError(
                "JAMENDO_CLIENT_ID is not configured."
            )

    def get_music(
        self,
        query: str,
        output_dir: Path,
        **options: Any,
    ) -> Path:
        """Search Jamendo for a royalty-free track and download it."""

        tracks = self.search(query, limit=1)

        if not tracks:
            raise RuntimeError(
                f"No Jamendo tracks found for tags: {query}"
            )

        track = tracks[0]

        output_dir.mkdir(parents=True, exist_ok=True)
        destination = output_dir / f"jamendo_{track['id']}.mp3"

        MediaDownloader.download(track["download_url"], destination)

        return destination

    def search(
        self,
        query: str,
        limit: int = 12,
    ) -> list[dict[str, Any]]:
        """Search Jamendo for candidate tracks without downloading --
        used by the /new wizard's listen-and-pick music browser."""

        query = query.strip() or "cinematic background"

        response = requests.get(
            self.API_URL,
            params={
                "client_id": settings.jamendo_client_id,
                "format": "json",
                "tags": query,
                "audioformat": "mp32",
                "limit": limit,
                "include": "musicinfo",
                "order": "popularity_total",
            },
            timeout=30,
        )

        response.raise_for_status()
        payload = response.json()

        results = payload.get("results", [])

        tracks: list[dict[str, Any]] = []

        for track in results:
            download_url = track.get("audiodownload") or track.get("audio")

            if not download_url:
                continue

            tracks.append({
                "id": str(track.get("id", "")),
                "name": str(track.get("name") or "Untitled"),
                "artist": str(track.get("artist_name") or ""),
                "duration": int(track.get("duration") or 0),
                "preview_url": str(track.get("audio") or download_url),
                "download_url": str(download_url),
            })

        return tracks
