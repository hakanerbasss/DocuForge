import subprocess
from pathlib import Path


class RenderService:
    """Render project media into a single MP4 file using FFmpeg."""

    def render(self, project_path: str) -> Path:
        project_dir = Path(project_path)
        media_dir = project_dir / "media"
        render_dir = project_dir / "render"
        clips_dir = render_dir / "clips"

        if not media_dir.exists():
            raise FileNotFoundError(
                f"Media directory not found: {media_dir}"
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
            video_files = sorted(scene_dir.glob("*.mp4"))
            image_files = sorted(
                file_path
                for pattern in ("*.jpg", "*.jpeg", "*.png", "*.webp")
                for file_path in scene_dir.glob(pattern)
            )

            clip_path = clips_dir / f"clip_{index:03d}.mp4"

            if video_files:
                self._video_to_clip(
                    source=video_files[0],
                    destination=clip_path,
                )

            elif image_files:
                self._image_to_clip(
                    source=image_files[0],
                    destination=clip_path,
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

    def _video_to_clip(
        self,
        source: Path,
        destination: Path,
    ) -> None:
        command = [
            "ffmpeg",
            "-y",
            "-i",
            str(source),
            "-t",
            "8",
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
            "-an",
            str(destination),
        ]

        self._run(command)

    def _image_to_clip(
        self,
        source: Path,
        destination: Path,
    ) -> None:
        command = [
            "ffmpeg",
            "-y",
            "-loop",
            "1",
            "-i",
            str(source),
            "-t",
            "8",
            "-vf",
            (
                "scale=1280:720:force_original_aspect_ratio=increase,"
                "crop=1280:720,"
                "zoompan=z='min(zoom+0.0008,1.08)':"
                "d=240:s=1280x720:fps=30"
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
