import json
import subprocess
from pathlib import Path
from typing import Any


class ThumbnailService:
    """Generate a YouTube-style thumbnail from project media via FFmpeg."""

    WIDTH = 1280
    HEIGHT = 720
    VERTICAL_WIDTH = 1080
    VERTICAL_HEIGHT = 1920

    FONT_CANDIDATES = (
        Path("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"),
        Path("/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf"),
        Path("/usr/share/fonts/truetype/noto/NotoSans-Bold.ttf"),
        Path("/usr/share/fonts/truetype/freefont/FreeSansBold.ttf"),
    )

    def generate(self, project_path: str) -> Path:
        project_dir = Path(project_path)
        project_data = self._load_json(
            project_dir / "project.json"
        )

        title = str(
            project_data.get("title", "")
        ).strip() or "DocuForge"

        source_image = self._extract_source_frame(project_dir)

        output_path = project_dir / "thumbnail.jpg"
        self._render_thumbnail(
            source_image,
            title,
            output_path,
            self.WIDTH,
            self.HEIGHT,
        )

        resolution = str(
            project_data.get("resolution", "")
        ).strip().lower()

        content_type = str(
            project_data.get("content_type", "")
        ).strip().lower()

        if resolution == "vertical" or content_type == "shorts":
            self._render_thumbnail(
                source_image,
                title,
                project_dir / "thumbnail_vertical.jpg",
                self.VERTICAL_WIDTH,
                self.VERTICAL_HEIGHT,
            )

        return output_path

    def _extract_source_frame(self, project_dir: Path) -> Path:
        media_dir = project_dir / "media"

        scene_dirs = sorted(
            path
            for path in media_dir.iterdir()
            if path.is_dir() and path.name.startswith("scene_")
        ) if media_dir.exists() else []

        for scene_dir in scene_dirs:
            images = sorted(
                file_path
                for pattern in ("*.jpg", "*.jpeg", "*.png", "*.webp")
                for file_path in scene_dir.glob(pattern)
            )
            if images:
                return images[0]

        for scene_dir in scene_dirs:
            videos = sorted(scene_dir.glob("*.mp4"))

            if not videos:
                continue

            frame_path = project_dir / "thumbnail_source.jpg"

            self._run([
                "ffmpeg",
                "-y",
                "-ss",
                "0.5",
                "-i",
                str(videos[0]),
                "-frames:v",
                "1",
                "-q:v",
                "2",
                str(frame_path),
            ])

            if frame_path.exists() and frame_path.stat().st_size > 0:
                return frame_path

        raise FileNotFoundError(
            "No scene image or video found to build a thumbnail from."
        )

    def _render_thumbnail(
        self,
        source: Path,
        title: str,
        output_path: Path,
        width: int,
        height: int,
    ) -> Path:
        font_path = self._find_font()

        vf_parts = [
            f"scale={width}:{height}:"
            "force_original_aspect_ratio=increase",
            f"crop={width}:{height}",
        ]

        if font_path is not None:
            wrapped_title = self._wrap_text(title, max_chars=28)
            escaped_text = self._escape_drawtext(wrapped_title)
            box_height = int(height * 0.22)

            vf_parts.append(
                f"drawbox=x=0:y={height - box_height}:"
                f"w={width}:h={box_height}:color=black@0.55:t=fill"
            )
            vf_parts.append(
                "drawtext="
                f"fontfile='{font_path}':"
                f"text='{escaped_text}':"
                "fontcolor=white:"
                f"fontsize={int(height * 0.055)}:"
                "x=(w-text_w)/2:"
                f"y=h-{box_height}+({box_height}-text_h)/2:"
                "line_spacing=6"
            )

        command = [
            "ffmpeg",
            "-y",
            "-i",
            str(source),
            "-vf",
            ",".join(vf_parts),
            "-frames:v",
            "1",
            "-q:v",
            "2",
            str(output_path),
        ]

        self._run(command)

        if not output_path.exists() or output_path.stat().st_size == 0:
            raise RuntimeError(
                f"Thumbnail was not created: {output_path}"
            )

        return output_path

    def _find_font(self) -> Path | None:
        for candidate in self.FONT_CANDIDATES:
            if candidate.exists():
                return candidate

        return None

    def _wrap_text(self, text: str, max_chars: int) -> str:
        words = text.split()
        lines: list[str] = []
        current = ""

        for word in words:
            candidate = f"{current} {word}".strip()

            if len(candidate) > max_chars and current:
                lines.append(current)
                current = word
            else:
                current = candidate

        if current:
            lines.append(current)

        return "\n".join(lines[:3])

    def _escape_drawtext(self, text: str) -> str:
        text = text.replace("\\", "\\\\")
        # Sidestep single-quote escaping inside a single-quoted
        # drawtext value entirely instead of the fragile '\'' dance.
        text = text.replace("'", "’")
        text = text.replace(":", "\\:")
        text = text.replace("%", "\\%")

        return text

    def _load_json(self, path: Path) -> dict[str, Any]:
        if not path.exists():
            return {}

        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return {}

        return data if isinstance(data, dict) else {}

    def _run(self, command: list[str]) -> None:
        try:
            subprocess.run(
                command,
                check=True,
                capture_output=True,
                text=True,
            )
        except FileNotFoundError as error:
            raise RuntimeError(
                "FFmpeg is not installed or not available in PATH."
            ) from error
        except subprocess.CalledProcessError as error:
            raise RuntimeError(
                f"FFmpeg failed:\n{error.stderr}"
            ) from error
