import json
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

HISTORY_PATH = Path("topic_history.json")
PROJECTS_ROOT = Path("projects")

MAX_AVOID_TITLES = 80

_lock = threading.Lock()


def _load() -> list[dict[str, Any]]:
    if not HISTORY_PATH.exists():
        return []

    try:
        data = json.loads(HISTORY_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []

    return data if isinstance(data, list) else []


def _save(entries: list[dict[str, Any]]) -> None:
    HISTORY_PATH.write_text(
        json.dumps(entries, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def mark_done(title: str) -> dict[str, Any]:
    """Remember a topic title so future suggestions never repeat it.

    Idempotent: marking the same title (case-insensitively) twice just
    returns the existing entry instead of duplicating it.
    """

    clean_title = title.strip()

    if not clean_title:
        raise ValueError("title is required")

    with _lock:
        entries = _load()

        existing = next(
            (
                item for item in entries
                if str(item.get("title", "")).strip().lower()
                == clean_title.lower()
            ),
            None,
        )

        if existing is not None:
            return existing

        entry = {
            "title": clean_title,
            "marked_at": datetime.now(timezone.utc).isoformat(),
        }

        entries.insert(0, entry)
        _save(entries)

        return entry


def list_done() -> list[dict[str, Any]]:
    with _lock:
        return _load()


def _project_titles() -> list[str]:
    """Titles of already-created projects -- these are obviously already
    covered even if nobody explicitly clicked "bunu yaptım" for them.
    """

    if not PROJECTS_ROOT.exists():
        return []

    titles: list[str] = []

    for project_dir in sorted(
        PROJECTS_ROOT.iterdir(),
        key=lambda p: p.stat().st_mtime if p.exists() else 0,
        reverse=True,
    ):
        if not project_dir.is_dir():
            continue

        project_json = project_dir / "project.json"

        if not project_json.exists():
            continue

        try:
            data = json.loads(project_json.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue

        title = str(data.get("title") or "").strip()

        if title:
            titles.append(title)

    return titles


def get_avoid_titles() -> list[str]:
    """Merge explicitly marked-done titles with existing project titles
    into a single deduplicated avoid-list, most recent first, capped so
    the suggestion prompt doesn't grow unbounded over time.
    """

    with _lock:
        marked = [str(item.get("title", "")).strip() for item in _load()]

    combined = marked + _project_titles()

    seen: set[str] = set()
    deduped: list[str] = []

    for title in combined:
        key = title.lower()

        if not title or key in seen:
            continue

        seen.add(key)
        deduped.append(title)

    return deduped[:MAX_AVOID_TITLES]
