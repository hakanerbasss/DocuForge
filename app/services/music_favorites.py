import json
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

FAVORITES_PATH = Path("music_favorites.json")

_lock = threading.Lock()


def _load() -> list[dict[str, Any]]:
    if not FAVORITES_PATH.exists():
        return []

    try:
        data = json.loads(FAVORITES_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []

    return data if isinstance(data, list) else []


def _save(favorites: list[dict[str, Any]]) -> None:
    FAVORITES_PATH.write_text(
        json.dumps(favorites, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def list_favorites() -> list[dict[str, Any]]:
    with _lock:
        return _load()


def add_favorite(track: dict[str, Any], provider: str) -> dict[str, Any]:
    """Save a track for reuse without re-searching/re-generating.

    Especially useful for ElevenLabs, where every search is a real,
    billed generation -- favoriting just remembers the already-cached
    file's URL, so picking it again later never re-triggers a charge.
    Idempotent: favoriting the same (provider, id) twice returns the
    existing entry instead of duplicating it.
    """

    with _lock:
        favorites = _load()
        key = f"{provider}:{track.get('id', '')}"

        existing = next(
            (item for item in favorites if item.get("key") == key), None
        )

        if existing is not None:
            return existing

        entry = {
            "key": key,
            "provider": provider,
            "id": str(track.get("id", "")),
            "name": str(track.get("name") or "Untitled"),
            "artist": str(track.get("artist") or ""),
            "duration": int(track.get("duration") or 0),
            "preview_url": str(track.get("preview_url") or ""),
            "download_url": str(track.get("download_url") or ""),
            "license": track.get("license") or {},
            "saved_at": datetime.now(timezone.utc).isoformat(),
        }

        favorites.insert(0, entry)
        _save(favorites)

        return entry


def remove_favorite(provider: str, track_id: str) -> bool:
    with _lock:
        favorites = _load()
        key = f"{provider}:{track_id}"

        remaining = [item for item in favorites if item.get("key") != key]

        if len(remaining) == len(favorites):
            return False

        _save(remaining)

        return True
