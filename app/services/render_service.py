import json
import subprocess
from pathlib import Path
from typing import Any


class RenderService:
    """Render synchronized scene media and narration using FFmpeg."""

    AUDIO_PADDING_SECONDS = 0.35
    DEFAULT_DURATION_SECONDS = 8.0
    WIDTH = 1280
    HEIGHT = 720
    FPS = 30

    def render(self, project_path: str) -> Path:
        project_dir = Path(project_path)
        media_dir = project_dir / "media"
        audio_dir = project_dir / "audio"
        render_dir = project_dir / "render"
        clips_dir = render_dir / "clips"

        storyboard_path = project_dir / "storyboard.json"
        audio_manifest_path = audio_dir / "manifest.json"

        if not media_dir.exists():
            raise FileNotFoundError(
                f"Media directory not found: {media_dir}"
            )

        if not storyboard_path.exists():
            raise FileNotFoundError(
                f"storyboard.json not found: {storyboard_path}"
            )

        storyboard = self._load_json(storyboard_path)
        storyboard_durations = self._build_storyboard_duration_map(
            storyboard
        )

        audio_manifest: dict[str, Any] | None = None
        audio_scenes: dict[int, dict[str, Any]] = {}

        if audio_manifest_path.exists():
            audio_manifest = self._load_json(audio_manifest_path)
            audio_scenes = self._build_audio_scene_map(
                audio_manifest
            )

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

            storyboard_duration = storyboard_durations.get(
                scene_number,
                self.DEFAULT_DURATION_SECONDS,
            )

            audio_info = audio_scenes.get(scene_number)
            audio_path: Path | None = None
            audio_duration = 0.0

            if audio_info is not None:
                raw_audio_path = audio_info.get("audio_file")
                raw_audio_duration = audio_info.get("audio_duration")

                if isinstance(raw_audio_path, str):
                    candidate = Path(raw_audio_path)

                    if candidate.exists() and candidate.stat().st_size > 0:
                        audio_path = candidate

                try:
                    audio_duration = float(raw_audio_duration or 0)
                except (TypeError, ValueError):
                    audio_duration = 0.0

            if audio_path is not None and audio_duration <= 0:
                audio_duration = self._probe_duration(audio_path)

            if audio_path is not None:
                scene_duration = max(
                    storyboard_duration,
                    audio_duration + self.AUDIO_PADDING_SECONDS,
                )
            else:
                scene_duration = storyboard_duration

            video_files = sorted(scene_dir.glob("*.mp4"))

            image_files = sorted(
                file_path
                for pattern in (
                    "*.jpg",
                    "*.jpeg",
                    "*.png",
                    "*.webp",
                )
                for file_path in scene_dir.glob(pattern)
            )

            clip_path = (
                clips_dir
                / f"clip_{scene_number:03d}.mp4"
            )

            print(
                f"Scene {scene_number:03d}: "
                f"{scene_duration:.2f}s"
                + (
                    f" | audio {audio_duration:.2f}s"
                    if audio_path is not None
                    else " | no audio"
                )
            )

            if video_files:
                self._video_to_clip(
                    source=video_files[0],
                    destination=clip_path,
                    duration=scene_duration,
                    audio_path=audio_path,
                )

            elif image_files:
                self._image_to_clip(
                    source=image_files[0],
                    destination=clip_path,
                    duration=scene_duration,
                    audio_path=audio_path,
                )

            else:
                print(
                    f"  ⚠ No usable media in {scene_dir}; skipped."
                )
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
            "-movflags",
            "+faststart",
            str(output_path),
        ]

        self._run(command)

        if not output_path.exists() or output_path.stat().st_size == 0:
            raise RuntimeError(
                f"Final video was not created: {output_path}"
            )

        return output_path

    def _video_to_clip(
        self,
        source: Path,
        destination: Path,
        duration: float,
        audio_path: Path | None,
    ) -> None:
        command = [
            "ffmpeg",
            "-y",
            "-stream_loop",
            "-1",
            "-i",
            str(source),
        ]

        if audio_path is not None:
            command.extend([
                "-i",
                str(audio_path),
            ])

        command.extend([
            "-t",
            f"{duration:.3f}",
            "-vf",
            (
                f"scale={self.WIDTH}:{self.HEIGHT}:"
                "force_original_aspect_ratio=decrease,"
                f"pad={self.WIDTH}:{self.HEIGHT}:"
                "(ow-iw)/2:(oh-ih)/2,"
                "setsar=1"
            ),
            "-r",
            str(self.FPS),
            "-c:v",
            "libx264",
            "-preset",
            "veryfast",
            "-crf",
            "23",
            "-pix_fmt",
            "yuv420p",
        ])

        if audio_path is not None:
            command.extend([
                "-c:a",
                "aac",
                "-b:a",
                "192k",
                "-ar",
                "48000",
                "-ac",
                "2",
                "-af",
                "apad",
            ])
        else:
            command.extend([
                "-f",
                "lavfi",
                "-i",
                "anullsrc=r=48000:cl=stereo",
                "-c:a",
                "aac",
                "-b:a",
                "192k",
                "-shortest",
            ])

        command.extend([
            "-movflags",
            "+faststart",
            str(destination),
        ])

        self._run(command)

    def _image_to_clip(
        self,
        source: Path,
        destination: Path,
        duration: float,
        audio_path: Path | None,
    ) -> None:
        frame_count = max(
            1,
            int(round(duration * self.FPS)),
        )

        command = [
            "ffmpeg",
            "-y",
            "-loop",
            "1",
            "-i",
            str(source),
        ]

        if audio_path is not None:
            command.extend([
                "-i",
                str(audio_path),
            ])

        command.extend([
            "-t",
            f"{duration:.3f}",
            "-vf",
            (
                f"scale={self.WIDTH}:{self.HEIGHT}:"
                "force_original_aspect_ratio=increase,"
                f"crop={self.WIDTH}:{self.HEIGHT},"
                "zoompan="
                "z='min(zoom+0.0008,1.08)':"
                f"d={frame_count}:"
                f"s={self.WIDTH}x{self.HEIGHT}:"
                f"fps={self.FPS},"
                "setsar=1"
            ),
            "-c:v",
            "libx264",
            "-preset",
            "veryfast",
            "-crf",
            "23",
            "-pix_fmt",
            "yuv420p",
        ])

        if audio_path is not None:
            command.extend([
                "-c:a",
                "aac",
                "-b:a",
                "192k",
                "-ar",
                "48000",
                "-ac",
                "2",
                "-af",
                "apad",
            ])
        else:
            command.extend([
                "-f",
                "lavfi",
                "-i",
                "anullsrc=r=48000:cl=stereo",
                "-c:a",
                "aac",
                "-b:a",
                "192k",
                "-shortest",
            ])

        command.extend([
            "-movflags",
            "+faststart",
            str(destination),
        ])

        self._run(command)

    def _build_storyboard_duration_map(
        self,
        storyboard: dict[str, Any],
    ) -> dict[int, float]:
        scenes = storyboard.get("scenes")

        if not isinstance(scenes, list) or not scenes:
            raise ValueError(
                "Storyboard must contain a non-empty scenes list."
            )

        durations: dict[int, float] = {}

        for index, scene in enumerate(scenes, start=1):
            if not isinstance(scene, dict):
                continue

            try:
                scene_number = int(scene.get("scene", index))
            except (TypeError, ValueError):
                scene_number = index

            try:
                duration = float(
                    scene.get(
                        "duration",
                        self.DEFAULT_DURATION_SECONDS,
                    )
                )
            except (TypeError, ValueError):
                duration = self.DEFAULT_DURATION_SECONDS

            if duration <= 0:
                duration = self.DEFAULT_DURATION_SECONDS

            durations[scene_number] = duration

        return durations

    def _build_audio_scene_map(
        self,
        manifest: dict[str, Any],
    ) -> dict[int, dict[str, Any]]:
        scenes = manifest.get("scenes")

        if not isinstance(scenes, list):
            return {}

        result: dict[int, dict[str, Any]] = {}

        for index, scene in enumerate(scenes, start=1):
            if not isinstance(scene, dict):
                continue

            try:
                scene_number = int(scene.get("scene", index))
            except (TypeError, ValueError):
                continue

            result[scene_number] = scene

        return result

    def _scene_number_from_dir(
        self,
        scene_dir: Path,
        fallback: int,
    ) -> int:
        try:
            return int(
                scene_dir.name.split("_", maxsplit=1)[1]
            )
        except (IndexError, ValueError):
            return fallback

    def _probe_duration(
        self,
        media_path: Path,
    ) -> float:
        command = [
            "ffprobe",
            "-v",
            "error",
            "-show_entries",
            "format=duration",
            "-of",
            "default=noprint_wrappers=1:nokey=1",
            str(media_path),
        ]

        try:
            result = subprocess.run(
                command,
                check=True,
                capture_output=True,
                text=True,
            )
        except FileNotFoundError as error:
            raise RuntimeError(
                "ffprobe is not installed or not available in PATH."
            ) from error
        except subprocess.CalledProcessError as error:
            raise RuntimeError(
                f"ffprobe failed for {media_path}: "
                f"{error.stderr}"
            ) from error

        try:
            duration = float(result.stdout.strip())
        except ValueError as error:
            raise RuntimeError(
                f"Invalid duration for {media_path}: "
                f"{result.stdout}"
            ) from error

        return duration

    def _load_json(
        self,
        path: Path,
    ) -> dict[str, Any]:
        try:
            data = json.loads(
                path.read_text(encoding="utf-8")
            )
        except json.JSONDecodeError as error:
            raise ValueError(
                f"Invalid JSON file {path}: {error}"
            ) from error

        if not isinstance(data, dict):
            raise ValueError(
                f"JSON root must be an object: {path}"
            )

        return data

    def _run(
        self,
        command: list[str],
    ) -> None:
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
