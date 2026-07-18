import hashlib
from pathlib import Path
from typing import Any

import requests

from app.core.config import settings
from app.providers.base import MusicProvider


class ElevenLabsMusicProvider(MusicProvider):
    """Generate background music via ElevenLabs' Music API (POST /v1/music).

    Unlike Jamendo/Mubert, this isn't a catalog search -- every call is a
    real, billed generation. Two things follow from that:

    1. A fixed, modest duration (DEFAULT_DURATION_SECONDS) is generated
       for every track rather than the video's full target length --
       DocuForge's render step already loops the music file to cover
       the whole video (ffmpeg `-stream_loop -1`), the same way it
       already handles a short Jamendo track under a long video, so
       there's no need to (expensively) generate minutes of audio.
    2. Results are cached to disk by a hash of (prompt, duration), so
       browsing the same search twice -- or the automatic render-time
       pick reusing what was already generated for a preview -- doesn't
       trigger a second paid generation for identical input.

    The query is deliberately wrapped in an "ambient, no vocals,
    documentary background" framing before being sent as the prompt --
    a bare mood word like "cinematic" tends to generate something
    song-like (verse/chorus structure, a melodic hook) rather than the
    unobtrusive underscore actually wanted behind narration.

    Unverified against a live account in this codebase (no API key
    available in development) -- the request/response shape matches
    ElevenLabs' public documentation, but treat this as a best-effort
    starting point the way the Mubert provider already is, and confirm
    against a real key before depending on it.
    """

    provider_key = "elevenlabs"
    provider_name = "ElevenLabs Music (AI üretimi, ücretli)"

    API_URL = "https://api.elevenlabs.io/v1/music"
    MODEL_ID = "music_v2"
    DEFAULT_DURATION_SECONDS = 90

    CACHE_DIR = Path("music_cache/elevenlabs")

    def __init__(self) -> None:
        super().__init__()

        if not settings.elevenlabs_api_key:
            raise ValueError(
                "ELEVENLABS_API_KEY is not configured."
            )

    def get_music(
        self,
        query: str,
        output_dir: Path,
        **options: Any,
    ) -> Path:
        """Generate (or reuse a cached generation of) a background track
        and copy it into the project's music directory."""

        duration_seconds = int(
            options.get("duration_seconds")
            or self.DEFAULT_DURATION_SECONDS
        )
        # A full documentary's target length isn't a useful duration to
        # actually generate at -- see the class docstring. Cap it the
        # same way search() does so a caller passing the real video
        # length here doesn't trigger an unexpectedly long/expensive
        # generation.
        duration_seconds = min(duration_seconds, self.DEFAULT_DURATION_SECONDS)

        cached_path = self._generate(query, duration_seconds)

        output_dir.mkdir(parents=True, exist_ok=True)
        destination = output_dir / "elevenlabs_track.mp3"
        destination.write_bytes(cached_path.read_bytes())

        return destination

    def search(
        self,
        query: str,
        limit: int = 1,
    ) -> list[dict[str, Any]]:
        """Generate a single track for the listen-and-pick music browser.

        Always returns at most one result -- unlike a catalog search,
        "more results" would just mean "pay for more generations."
        """

        cached_path = self._generate(query, self.DEFAULT_DURATION_SECONDS)
        preview_url = f"/music-cache/elevenlabs/{cached_path.name}"

        return [{
            "id": cached_path.stem,
            "name": "AI Üretilen Arka Plan Müziği",
            "artist": "ElevenLabs Music",
            "duration": self.DEFAULT_DURATION_SECONDS,
            "preview_url": preview_url,
            "download_url": preview_url,
            "license": {
                "url": "",
                "label": "ElevenLabs Music (ticari kullanıma uygun)",
                "commercial_ok": True,
            },
        }]

    def _build_prompt(self, query: str) -> str:
        mood = query.strip() or "cinematic documentary"

        return (
            f"Instrumental ambient background music, {mood}. Subtle and "
            "atmospheric, no vocals, no strong melodic hook or chorus, "
            "unobtrusive underscore meant to sit quietly behind spoken "
            "narration -- not a standalone song."
        )

    def _generate(self, query: str, duration_seconds: int) -> Path:
        prompt = self._build_prompt(query)
        cache_key = hashlib.sha256(
            f"{prompt}|{duration_seconds}".encode("utf-8")
        ).hexdigest()[:24]

        self.CACHE_DIR.mkdir(parents=True, exist_ok=True)
        cached_path = self.CACHE_DIR / f"{cache_key}.mp3"

        if cached_path.exists() and cached_path.stat().st_size > 0:
            return cached_path

        response = requests.post(
            self.API_URL,
            headers={
                "xi-api-key": settings.elevenlabs_api_key,
                "Content-Type": "application/json",
            },
            json={
                "prompt": prompt,
                "music_length_ms": duration_seconds * 1000,
                "model_id": self.MODEL_ID,
            },
            timeout=120,
        )

        response.raise_for_status()

        tmp_path = cached_path.with_suffix(".mp3.tmp")
        tmp_path.write_bytes(response.content)

        if tmp_path.stat().st_size == 0:
            tmp_path.unlink(missing_ok=True)
            raise RuntimeError("ElevenLabs Music returned an empty response.")

        tmp_path.replace(cached_path)

        return cached_path
