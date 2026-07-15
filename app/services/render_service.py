import json
import subprocess
from pathlib import Path
from typing import Any


class RenderService:
    """Render project media into a single MP4 file using FFmpeg."""

    def render(self, project_path: str) -> Path:
        project_dir = Path(project_path)
        media_dir = project_dir / "media"
        render_dir = project_dir / "render"
        clips_dir = render_dir / "clips"
        storyboard_path = project_dir / "storyboard.json"

        if not media_dir.exists():
            raise FileNotFoundError(
                f"Media directory not found: {media_dir}"
            )

        if not storyboard_path.exists():
            raise FileNotFoundError(
                f"storyboard.json not found: {storyboard_path}"
            )

        storyboard = self._load_storyboard(storyboard_path)
        durations = self._build_duration_map(storyboard)

        render_dir.mkdir(parents=True, exist_ok=True)
        clips_dir.mkdir(parents=True, exist_ok=True)

        scene_dirs = sorted(
            path
            for path in media_dir.iterdir()
            if path.is_dir() and path.name.startswith("scene_")
        )

        if not scene_dirs:
            raise ValueError("No scene directories found.")

        clip_files: list[Path] = []

        for index, scene_dir in enumerate(scene_dirs, start=1):
            scene_number = self._scene_number_from_dir(
                scene_dir,
                fallback=index,
            )

            duration = durations.get(scene_number, 8.0)

            video_files = sorted(scene_dir.glob("*.mp4"))
            image_files = sorted(
                file_path
                for pattern in ("*.jpg", "*.jpeg", "*.png", "*.webp")
                for file_path in scene_dir.glob(pattern)
            )

            clip_path = clips_dir / f"clip_{scene_number:03d}.mp4"

            if video_files:
                self._video_to_clip(
                    source=video_files[0],
                    destination=clip_path,
                    duration=duration,
                )

            elif image_files:
                self._image_to_clip(
                    source=image_files[0],
                    destination=clip_path,
                    duration=duration,
                )

            else:
                continue

            clip_files.append(clip_path)

        if not clip_files:
            raise ValueError("No usable media files found.")

        concat_file = render_dir / "concat.txt"

        concat_file.write_text(
            "\n".join(
                f"file '{clip.resolve()}'"
                for clip in clip_files
            ),
            encoding="utf-8",
        )

        output_path = render_dir / "final_video.mp4"

        command = [
            "ffmpeg",
            "-y",
            "-f",
            "concat",
            "-safe",
            "0",
            "-i",
            str(concat_file),
            "-c",
            "copy",
            str(output_path),
        ]

        self._run(command)

        return output_path

    def _load_storyboard(
        self,
        storyboard_path: Path,
    ) -> dict[str, Any]:
        try:
            data = json.loads(
                storyboard_path.read_text(encoding="utf-8")
            )
        except json.JSONDecodeError as error:
            raise ValueError(
                f"storyboard.json is invalid: {error}"
            ) from error

        if not isinstance(data, dict):
            raise ValueError(
                "Storyboard root must be a JSON object."
            )

        scenes = data.get("scenes")

        if not isinstance(scenes, list) or not scenes:
            raise ValueError(
                "Storyboard must contain a non-empty scenes list."
            )

        return data

    def _build_duration_map(
        self,
        storyboard: dict[str, Any],
    ) -> dict[int, float]:
        durations: dict[int, float] = {}

        for index, scene in enumerate(
            storyboard["scenes"],
            start=1,
        ):
            if not isinstance(scene, dict):
                continue

            scene_number = scene.get("scene", index)
            duration = scene.get("duration", 8)

            try:
                scene_number = int(scene_number)
                duration = float(duration)
            except (TypeError, ValueError):
                continue

            if duration <= 0:
                duration = 8.0

            durations[scene_number] = duration

        return durations

    def _scene_number_from_dir(
        self,
        scene_dir: Path,
        fallback: int,
    ) -> int:
        try:
            return int(scene_dir.name.split("_", maxsplit=1)[1])
        except (IndexError, ValueError):
            return fallback

    def _video_to_clip(
        self,
        source: Path,
        destination: Path,
        duration: float,
    ) -> None:
        command = [
            "ffmpeg",
            "-y",
            "-stream_loop",
            "-1",
            "-i",
            str(source),
            "-t",
            str(duration),
            "-vf",
            (
                "scale=1280:720:force_original_aspect_ratio=decrease,"
                "pad=1280:720:(ow-iw)/2:(oh-ih)/2"
            ),
            "-r",
            "30",
            "-c:v",
            "libx264",
            "-preset",
            "veryfast",
            "-crf",
            "23",
            "-pix_fmt",
            "yuv420p",
            "-an",
            str(destination),
        ]

        self._run(command)

    def _image_to_clip(
        self,
        source: Path,
        destination: Path,
        duration: float,
    ) -> None:
        frame_count = max(1, int(round(duration * 30)))

        command = [
            "ffmpeg",
            "-y",
            "-loop",
            "1",
            "-i",
            str(source),
            "-t",
            str(duration),
            "-vf",
            (
                "scale=1280:720:force_original_aspect_ratio=increase,"
                "crop=1280:720,"
                "zoompan="
                "z='min(zoom+0.0008,1.08)':"
                f"d={frame_count}:"
                "s=1280x720:"
                "fps=30"
            ),
            "-c:v",
            "libx264",
            "-preset",
            "veryfast",
            "-crf",
            "23",
            "-pix_fmt",
            "yuv420p",
            "-an",
            str(destination),
        ]

        self._run(command)

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
