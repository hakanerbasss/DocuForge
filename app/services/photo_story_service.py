import json
import threading
from pathlib import Path
from typing import Any

import requests

from app.core.config import settings
from app.services.render_service import RenderService


class PhotoStoryService:
    """Render a comic-strip / photo-story video from user-uploaded panels."""

    FREESOUND_API_URL = "https://freesound.org/apiv2/search/text/"
    DEFAULT_PANEL_DURATION = 5.0
    PHOTO_STORIES_ROOT = Path("photo_stories")

    # ------------------------------------------------------------------ #
    # SFX search + download                                                #
    # ------------------------------------------------------------------ #

    def search_sfx(self, keyword: str, output_path: Path) -> dict[str, Any] | None:
        """Search Freesound for a short sound effect and download it.

        Unlike FreesoundMusicProvider (which targets 60s+ ambient beds),
        this targets SHORT clips (0.5–30s) for comic-panel beat accents.
        Returns metadata dict on success, None on any failure.
        """

        if not settings.freesound_api_key:
            return None

        query = keyword.strip() or "whoosh transition"

        for attempt_filter in (
            "duration:[0.5 TO 30]",  # prefer short SFX
            "",                        # fallback: no duration restriction
        ):
            try:
                params: dict[str, Any] = {
                    "query": query,
                    "fields": "id,name,username,duration,license,previews",
                    "page_size": 15,
                    "sort": "score",
                }

                if attempt_filter:
                    params["filter"] = attempt_filter

                resp = requests.get(
                    self.FREESOUND_API_URL,
                    headers={
                        "Authorization": f"Token {settings.freesound_api_key}"
                    },
                    params=params,
                    timeout=20,
                )
                resp.raise_for_status()
                results = resp.json().get("results", [])

                for item in results:
                    lic = str(item.get("license", "")).lower()
                    if "nc" in lic or "sampling+" in lic:
                        continue

                    previews = item.get("previews") or {}
                    url = (
                        previews.get("preview-hq-mp3")
                        or previews.get("preview-lq-mp3")
                    )

                    if not url:
                        continue

                    r = requests.get(url, timeout=30)
                    r.raise_for_status()

                    output_path.parent.mkdir(parents=True, exist_ok=True)
                    output_path.write_bytes(r.content)

                    return {
                        "id": str(item.get("id", "")),
                        "name": str(item.get("name") or ""),
                        "artist": str(item.get("username") or ""),
                        "duration": float(item.get("duration") or 0),
                    }

                if not results:
                    # Nothing came back for this filter level; try the next.
                    continue

            except Exception as exc:
                print(
                    f"  ⚠ Freesound SFX araması başarısız "
                    f"({query!r}): {exc}"
                )
                break

        return None

    # ------------------------------------------------------------------ #
    # Render                                                               #
    # ------------------------------------------------------------------ #

    def render(self, project_dir: Path) -> Path:
        """Render all slots in order into a single video file."""

        config_path = project_dir / "photo_story.json"
        config: dict[str, Any] = json.loads(
            config_path.read_text(encoding="utf-8")
        )

        slots_raw: dict[str, Any] = config.get("slots") or {}
        slot_nums = sorted(int(k) for k in slots_raw)

        if not slot_nums:
            raise ValueError("Hiç panel yüklenmemiş.")

        rs = RenderService()
        rs.WIDTH = 1280
        rs.HEIGHT = 720
        rs.FPS = 30

        render_dir = project_dir / "render"
        clips_dir = render_dir / "clips"
        clips_dir.mkdir(parents=True, exist_ok=True)

        clip_files: list[Path] = []
        clip_durations: list[float] = []

        default_dur = float(
            config.get("panel_duration") or self.DEFAULT_PANEL_DURATION
        )
        default_trans = str(config.get("transition") or "crossfade")

        for num in slot_nums:
            slot = slots_raw[str(num)]
            panel_rel = slot.get("panel_file")
            sfx_rel = slot.get("sfx_file")
            duration = float(slot.get("duration") or default_dur)

            panel_path = (project_dir / panel_rel) if panel_rel else None
            sfx_path = (project_dir / sfx_rel) if sfx_rel else None

            if panel_path and not panel_path.exists():
                panel_path = None

            if sfx_path and not sfx_path.exists():
                sfx_path = None

            clip_path = clips_dir / f"clip_{num:03d}.mp4"
            print(
                f"  Panel {num:03d}: {duration:.1f}s"
                + (f" | SFX {sfx_path.name}" if sfx_path else " | no SFX")
            )

            if panel_path:
                rs._image_to_clip(
                    source=panel_path,
                    destination=clip_path,
                    duration=duration,
                    audio_path=sfx_path,
                    zoom=False,
                )
            else:
                rs._placeholder_to_clip(
                    destination=clip_path,
                    duration=duration,
                    audio_path=sfx_path,
                )

            clip_files.append(clip_path)
            clip_durations.append(duration)

        output_path = render_dir / "photo_story.mp4"
        xfade_name = RenderService.TRANSITION_XFADE_MAP.get(default_trans)

        if xfade_name and len(clip_files) > 1:
            try:
                rs._concat_with_transitions(
                    clip_files, clip_durations, xfade_name, output_path
                )
            except Exception as exc:
                print(
                    f"  ⚠ Geçiş efekti başarısız ({exc}); "
                    "sert kesime geçiliyor."
                )
                rs._concat_stream_copy(clip_files, render_dir, output_path)
        else:
            rs._concat_stream_copy(clip_files, render_dir, output_path)

        if not output_path.exists() or output_path.stat().st_size == 0:
            raise RuntimeError("Video oluşturulamadı (çıktı dosyası boş).")

        print(f"  ✅ Photo story video hazır: {output_path}")
        return output_path
