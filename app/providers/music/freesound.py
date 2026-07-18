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
    "by-nc": "CC BY-NC (ticari kullanım YOK)",
    "by-nc-sa": "CC BY-NC-SA (ticari kullanım YOK)",
    "sampling+": "Sampling+ (ticari kullanım YOK)",
}


class FreesoundMusicProvider(MusicProvider):
    """Search Freesound.org's Creative Commons audio library.

    Unlike Jamendo (independent musicians' song catalog) or ElevenLabs
    (paid on-demand generation), Freesound is a free, community-uploaded
    library of field recordings, atmospheres, and sound design -- most
    of it is genuinely ambient/background material rather than
    song-structured music, closer to what "fon sesi" actually means.

    A duration filter is applied so results skew toward loop-able
    ambient beds rather than the one-shot sound-effect blips (footsteps,
    door creaks, single hits) that also live in Freesound's catalog.
    """

    provider_key = "freesound"
    provider_name = "Freesound (ücretsiz, CC lisanslı atmosfer/fon sesi)"

    API_URL = "https://freesound.org/apiv2/search/text/"
    MIN_DURATION_SECONDS = 60

    def __init__(self) -> None:
        super().__init__()

        if not settings.freesound_api_key:
            raise ValueError(
                "FREESOUND_API_KEY is not configured."
            )

    def get_music(
        self,
        query: str,
        output_dir: Path,
        **options: Any,
    ) -> Path:
        """Search Freesound and download a commercially-clear result."""

        tracks = self.search(query, limit=10)

        if not tracks:
            raise RuntimeError(
                f"No Freesound tracks found for: {query}"
            )

        track = next(
            (t for t in tracks if t["license"]["commercial_ok"] is True),
            tracks[0],
        )

        output_dir.mkdir(parents=True, exist_ok=True)
        destination = output_dir / f"freesound_{track['id']}.mp3"

        MediaDownloader.download(track["download_url"], destination)

        return destination

    def search(
        self,
        query: str,
        limit: int = 12,
    ) -> list[dict[str, Any]]:
        """Search Freesound for candidate ambient/background tracks."""

        search_query = query.strip() or "ambient cinematic atmosphere"

        tracks = self._fetch(
            search_query,
            limit,
            duration_filter=f"duration:[{self.MIN_DURATION_SECONDS} TO *]",
        )

        if not tracks:
            # The duration filter (skewing toward loop-able beds instead
            # of short one-shot SFX) can be too strict for an unusual
            # query -- retry once without it rather than showing nothing.
            tracks = self._fetch(search_query, limit, duration_filter="")

        return tracks

    def _fetch(
        self,
        query: str,
        limit: int,
        duration_filter: str,
    ) -> list[dict[str, Any]]:
        params = {
            "query": query,
            "fields": "id,name,username,duration,license,previews",
            "page_size": limit,
            "sort": "score",
        }

        if duration_filter:
            params["filter"] = duration_filter

        response = requests.get(
            self.API_URL,
            headers={"Authorization": f"Token {settings.freesound_api_key}"},
            params=params,
            timeout=30,
        )

        response.raise_for_status()
        payload = response.json()

        results = payload.get("results", [])

        tracks: list[dict[str, Any]] = []

        for item in results:
            previews = item.get("previews") or {}
            download_url = (
                previews.get("preview-hq-mp3")
                or previews.get("preview_hq_mp3")
                or previews.get("preview-lq-mp3")
                or previews.get("preview_lq_mp3")
            )

            if not download_url:
                continue

            license_info = self._parse_license(
                str(item.get("license") or "")
            )

            # Freesound's catalog is mostly CC0/CC-BY, but CC-BY-NC and
            # Sampling+ (non-commercial) content exists too -- no point
            # listing something that can't legally go on a monetized
            # channel.
            if license_info["commercial_ok"] is False:
                continue

            tracks.append({
                "id": str(item.get("id", "")),
                "name": str(item.get("name") or "Untitled"),
                "artist": str(item.get("username") or ""),
                "duration": int(float(item.get("duration") or 0)),
                "preview_url": str(download_url),
                "download_url": str(download_url),
                "license": license_info,
            })

        return tracks

    def _parse_license(self, url: str) -> dict[str, Any]:
        if not url:
            return {"url": "", "label": "Bilinmiyor", "commercial_ok": None}

        lower = url.lower()

        if "publicdomain" in lower or "/zero/" in lower or lower == "cc0":
            return {
                "url": url,
                "label": "CC0 (kamu malı, ticari kullanıma uygun)",
                "commercial_ok": True,
            }

        match = re.search(r"/licenses/([a-z0-9-]+)/", lower)
        slug = match.group(1) if match else ""

        if not slug and "sampling+" in lower:
            slug = "sampling+"

        if not slug:
            return {"url": url, "label": "Bilinmiyor", "commercial_ok": None}

        commercial_ok = "nc" not in slug.split("-") and slug != "sampling+"
        label = _LICENSE_LABELS.get(slug, slug.upper())

        return {"url": url, "label": label, "commercial_ok": commercial_ok}
