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

    RESOLUTION_MAP = {
        "720p":     (1280, 720),
        "1080p":    (1920, 1080),
        "vertical": (1080, 1920),
        "4k":       (3840, 2160),
    }

    def render(self, project_path: str) -> Path:
        project_dir = Path(project_path)

        # Read resolution and fps from project.json
        project_json = project_dir / "project.json"
        project_data: dict[str, Any] = {}
        if project_json.exists():
            try:
                project_data = json.loads(
                    project_json.read_text(encoding="utf-8")
                )
            except Exception:
                pass

        resolution_key = str(project_data.get("resolution", "720p")).lower()
        w, h = self.RESOLUTION_MAP.get(resolution_key, (1280, 720))
        self.WIDTH = w
        self.HEIGHT = h
        self.FPS = int(project_data.get("fps", self.FPS))

        print(f"  Render: {self.WIDTH}x{self.HEIGHT} @ {self.FPS}fps")

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
        subtitle_segments: list[tuple[int, float, str | None]] = []

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
                    0.5,
                    audio_duration + self.AUDIO_PADDING_SECONDS,
                )
            else:
                scene_duration = storyboard_duration

            subtitle_segments.append((
                scene_number,
                scene_duration,
                self._read_scene_subtitle_text(audio_info),
            ))

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

        if project_data.get("background_music_enabled"):
            self._apply_background_music(
                project_dir,
                output_path,
                project_data,
            )

        if project_data.get("subtitles_enabled"):
            srt_path = render_dir / "subtitles.srt"
            self._write_srt(srt_path, subtitle_segments)
            print(f"  ✅ Subtitles written ({srt_path})")

            txt_path = render_dir / "subtitles.txt"
            self._write_txt(txt_path, subtitle_segments)
            print(f"  ✅ Transcript written ({txt_path})")

            if project_data.get("subtitles_burn_in"):
                self._burn_in_subtitles(output_path, srt_path)

        return output_path

    def _apply_background_music(
        self,
        project_dir: Path,
        video_path: Path,
        project_data: dict[str, Any],
    ) -> None:
        music_path = self._resolve_music_track(
            project_dir,
            project_data,
        )

        if music_path is None:
            print(
                "  ⚠ background_music_enabled=true fakat müzik "
                "dosyası bulunamadı; atlanıyor."
            )
            return

        duration = self._probe_duration(video_path)
        fade_duration = min(3.0, duration)
        fade_start = max(0.0, duration - fade_duration)

        mixed_path = video_path.with_name(
            "final_video_music.mp4"
        )

        command = [
            "ffmpeg",
            "-y",
            "-i",
            str(video_path),
            "-stream_loop",
            "-1",
            "-i",
            str(music_path),
            "-filter_complex",
            (
                f"[1:a]volume=0.18,"
                f"afade=t=out:st={fade_start:.2f}:d={fade_duration:.2f}"
                f"[music];"
                f"[0:a][music]amix=inputs=2:duration=first:"
                f"dropout_transition=0[aout]"
            ),
            "-map",
            "0:v",
            "-map",
            "[aout]",
            "-c:v",
            "copy",
            "-movflags",
            "+faststart",
            str(mixed_path),
        ]

        self._run(command)

        if not mixed_path.exists() or mixed_path.stat().st_size == 0:
            raise RuntimeError(
                f"Background music mix failed: {mixed_path}"
            )

        mixed_path.replace(video_path)

        print(
            f"  ✅ Background music mixed ({music_path.name})"
        )

    def _resolve_music_track(
        self,
        project_dir: Path,
        project_data: dict[str, Any],
    ) -> Path | None:
        explicit = str(
            project_data.get("music_track", "")
        ).strip()

        if explicit.startswith(("http://", "https://")):
            from app.providers.shared.downloader import MediaDownloader

            music_dir = project_dir / "music"
            music_dir.mkdir(parents=True, exist_ok=True)
            destination = music_dir / "selected_track.mp3"

            try:
                return MediaDownloader.download(explicit, destination)
            except Exception as error:
                print(
                    f"  ⚠ Seçilen müzik parçası indirilemedi "
                    f"({explicit}): {error}"
                )
                return None

        if explicit:
            candidate = Path(explicit)

            if not candidate.is_absolute():
                candidate = project_dir / candidate

            if candidate.exists():
                return candidate

            print(
                f"  ⚠ music_track belirtilmiş ama bulunamadı: "
                f"{candidate}"
            )
            return None

        music_dir = project_dir / "music"

        if music_dir.exists():
            for pattern in ("*.mp3", "*.wav", "*.m4a", "*.aac", "*.ogg"):
                matches = sorted(music_dir.glob(pattern))
                if matches:
                    return matches[0]

        music_provider_key = str(
            project_data.get("music_provider", "")
        ).strip().lower()

        if music_provider_key and music_provider_key != "local":
            return self._fetch_music_from_provider(
                music_dir,
                project_data,
                music_provider_key,
            )

        return None

    def _fetch_music_from_provider(
        self,
        music_dir: Path,
        project_data: dict[str, Any],
        provider_key: str,
    ) -> Path | None:
        from app.providers.defaults import register_default_providers
        from app.providers.registry import ProviderRegistry

        register_default_providers()

        try:
            provider = ProviderRegistry.create(
                category="music",
                key=provider_key,
            )
        except Exception as error:
            print(
                f"  ⚠ Müzik sağlayıcı kullanılamadı "
                f"({provider_key}): {error}"
            )
            return None

        query = self._build_music_query(project_data)

        try:
            return provider.get_music(
                query,
                music_dir,
                duration_seconds=180,
            )
        except Exception as error:
            print(
                f"  ⚠ Müzik alınamadı ({provider_key}): {error}"
            )
            return None

    def _build_music_query(
        self,
        project_data: dict[str, Any],
    ) -> str:
        content_type = str(
            project_data.get("content_type", "documentary")
        ).strip().lower()

        moods = {
            "documentary": "cinematic documentary ambient",
            "news": "corporate news background",
            "shorts": "upbeat energetic short",
            "informational": "calm educational background",
        }

        return moods.get(content_type, "cinematic background music")

    def _read_scene_subtitle_text(
        self,
        audio_info: dict[str, Any] | None,
    ) -> str | None:
        if audio_info is None:
            return None

        raw_text_path = audio_info.get("text_file")

        if not isinstance(raw_text_path, str):
            return None

        text_path = Path(raw_text_path)

        if not text_path.exists():
            return None

        text = text_path.read_text(encoding="utf-8").strip()

        return text or None

    def _write_srt(
        self,
        srt_path: Path,
        segments: list[tuple[int, float, str | None]],
    ) -> None:
        blocks: list[str] = []
        cursor = 0.0
        subtitle_index = 0

        for _scene_number, duration, text in segments:
            scene_start = cursor
            scene_end = cursor + duration
            cursor = scene_end
            if not text:
                continue

            words = text.replace("\n", " ").split()
            chunks: list[list[str]] = []
            current: list[str] = []

            for word in words:
                current.append(word)
                joined = " ".join(current)
                if len(current) >= 8 or len(joined) >= 42 or word.endswith((".", "!", "?", ";", ":")):
                    chunks.append(current)
                    current = []

            if current:
                chunks.append(current)

            total_words = sum(len(chunk) for chunk in chunks)
            chunk_cursor = scene_start

            for index, chunk in enumerate(chunks):
                share = len(chunk) / max(total_words, 1)
                chunk_duration = max(1.0, min(3.5, duration * share))
                chunk_start = chunk_cursor
                chunk_end = min(scene_end, chunk_start + chunk_duration)
                if index == len(chunks) - 1:
                    chunk_end = scene_end
                if chunk_end <= chunk_start:
                    continue

                subtitle_index += 1
                blocks.append(
                    f"{subtitle_index}\n"
                    f"{self._format_srt_timestamp(chunk_start)} --> "
                    f"{self._format_srt_timestamp(chunk_end)}\n"
                    f"{' '.join(chunk)}\n"
                )
                chunk_cursor = chunk_end

        srt_path.parent.mkdir(parents=True, exist_ok=True)
        srt_path.write_text("\n".join(blocks), encoding="utf-8")

    def _write_txt(
        self,
        txt_path: Path,
        segments: list[tuple[int, float, str | None]],
    ) -> None:
        """Plain-text transcript -- same narration as the .srt, but as
        readable paragraphs (no timestamps/indices/mid-sentence chunking),
        for copy-paste into a video description or reading offline."""

        paragraphs = [
            text.strip()
            for _scene_number, _duration, text in segments
            if text and text.strip()
        ]

        txt_path.parent.mkdir(parents=True, exist_ok=True)
        txt_path.write_text("\n\n".join(paragraphs), encoding="utf-8")

    def _format_srt_timestamp(
        self,
        seconds: float,
    ) -> str:
        total_ms = max(0, round(seconds * 1000))
        hours, remainder_ms = divmod(total_ms, 3_600_000)
        minutes, remainder_ms = divmod(remainder_ms, 60_000)
        secs, ms = divmod(remainder_ms, 1000)

        return f"{hours:02d}:{minutes:02d}:{secs:02d},{ms:03d}"

    def _burn_in_subtitles(
        self,
        video_path: Path,
        srt_path: Path,
    ) -> None:
        """Re-encode the video with the SRT burned in via ffmpeg's subtitles filter.

        No FontName is forced in force_style -- libass resolves a
        default via fontconfig, which is more robust across servers
        than guessing a font file's internal family name (untested
        against real ffmpeg/libass in this dev environment; verify on
        a real render before relying on it).
        """

        escaped_srt_path = (
            str(srt_path)
            .replace("\\", "\\\\")
            .replace(":", "\\:")
            .replace("'", "’")
        )

        force_style = (
            "FontSize=18,PrimaryColour=&H00FFFFFF,"
            "OutlineColour=&H00000000,BorderStyle=1,"
            "Outline=2,Shadow=0,Alignment=2,MarginV=80"
        )

        burned_path = video_path.with_name(
            "final_video_subtitled.mp4"
        )

        command = [
            "ffmpeg",
            "-y",
            "-i",
            str(video_path),
            "-vf",
            f"subtitles='{escaped_srt_path}':force_style='{force_style}'",
            "-c:a",
            "copy",
            "-movflags",
            "+faststart",
            str(burned_path),
        ]

        self._run(command)

        if (
            not burned_path.exists()
            or burned_path.stat().st_size == 0
        ):
            raise RuntimeError(
                f"Subtitle burn-in failed: {burned_path}"
            )

        burned_path.replace(video_path)

        print("  ✅ Subtitles burned into video")

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
            "-map", "0:v:0",
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
                "-map", "1:a:0",
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
                "-map", "0:v:0",
                "-map", "2:a:0",
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
