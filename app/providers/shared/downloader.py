from pathlib import Path

import requests


class MediaDownloader:
    """Shared downloader used by all media providers."""

    @staticmethod
    def download(url: str, destination: Path) -> Path:
        destination.parent.mkdir(parents=True, exist_ok=True)

        response = requests.get(url, timeout=60)
        response.raise_for_status()

        destination.write_bytes(response.content)

        return destination
