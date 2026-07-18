import re
from pathlib import Path
from typing import Any

import requests

from app.core.config import settings
from app.providers.base import MusicProvider
from app.providers.shared.downloader import MediaDownloader

_LICENSE_LABELS = {
    "by": "CC BY (ticari kullanıma uygun)",
    "by-sa": "CC BY-SA (ticari kullanıma uygun)",
    "by-nd": "CC BY-ND (ticari kullanıma uygun)",
    "by-nc": "CC BY-NC (ticari kullanım YOK)",
    "by-nc-sa": "CC BY-NC-SA (ticari kullanım YOK)",
    "by-nc-nd": "CC BY-NC-ND (ticari kullanım YOK)",
}


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
        """Search Jamendo for a royalty-free track and download it.

        Prefers a commercially-clear track (CC BY / BY-SA / BY-ND, no
        "NC" restriction) among the candidates -- these videos usually
        end up on a monetized YouTube channel, and Jamendo's catalog
        mixes commercial and non-commercial-only licenses. Falls back
        to the single best match if none of the candidates are clearly
        commercial-safe, rather than failing the build over it."""

        tracks = self.search(query, limit=10)

        if not tracks:
            raise RuntimeError(
                f"No Jamendo tracks found for tags: {query}"
            )

        track = next(
            (t for t in tracks if t["license"]["commercial_ok"] is True),
            tracks[0],
        )

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
        used by the /new wizard's listen-and-pick music browser.

        Jamendo's `tags` parameter only matches its own fixed, curated
        tag vocabulary -- an AI-suggested mood word or anything typed
        into the free-text search box very often isn't an exact tag in
        that vocabulary, so a strict `tags` search came back empty far
        more often than not. Tries three progressively looser
        strategies and returns the first one that finds anything:
        `fuzzytags` (approximate tag matching), then `search` (full-text
        across track/artist/album names), then no filter at all (just
        the most popular tracks) as a last resort so the browser is
        essentially never empty.
        """

        query = query.strip() or "cinematic background"

        for extra_params in (
            {"fuzzytags": query},
            {"search": query},
            {},
        ):
            tracks = self._fetch(extra_params, limit)

            if tracks:
                return tracks

        return []

    def _fetch(
        self,
        extra_params: dict[str, Any],
        limit: int,
    ) -> list[dict[str, Any]]:
        response = requests.get(
            self.API_URL,
            params={
                "client_id": settings.jamendo_client_id,
                "format": "json",
                "audioformat": "mp32",
                "limit": limit,
                "include": "musicinfo",
                "order": "popularity_total",
                **extra_params,
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

            license_info = self._parse_license(
                str(track.get("license_ccurl") or "")
            )

            # Confirmed non-commercial (CC BY-NC/-SA/-ND) tracks would
            # just be a licensing trap on a monetized channel -- no
            # point listing them at all. commercial_ok is None (license
            # couldn't be determined) still gets shown, since that's
            # "unknown" rather than "confirmed not allowed."
            if license_info["commercial_ok"] is False:
                continue

            tracks.append({
                "id": str(track.get("id", "")),
                "name": str(track.get("name") or "Untitled"),
                "artist": str(track.get("artist_name") or ""),
                "duration": int(track.get("duration") or 0),
                "preview_url": str(track.get("audio") or download_url),
                "download_url": str(download_url),
                "license": license_info,
            })

        return tracks

    def _parse_license(self, url: str) -> dict[str, Any]:
        """Turn Jamendo's license_ccurl into a human-readable label and a
        commercial_ok flag (True/False/None-if-unknown), so the /new and
        project-page music browsers can warn before someone picks a
        non-commercial-only track for a monetized YouTube upload."""

        if not url:
            return {"url": "", "label": "Bilinmiyor", "commercial_ok": None}

        lower = url.lower()

        if "publicdomain" in lower or "/zero/" in lower:
            return {
                "url": url,
                "label": "CC0 (kamu malı, ticari kullanıma uygun)",
                "commercial_ok": True,
            }

        match = re.search(r"/licenses/([a-z0-9-]+)/", lower)
        slug = match.group(1) if match else ""

        if not slug:
            return {"url": url, "label": "Bilinmiyor", "commercial_ok": None}

        commercial_ok = "nc" not in slug.split("-")
        label = _LICENSE_LABELS.get(slug, slug.upper())

        return {"url": url, "label": label, "commercial_ok": commercial_ok}
