import json
import shutil
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

    AI_DISCLOSURE_SECONDS = 6.0
    AI_DISCLOSURE_TEXT = "Bu videoda yapay zeka destekli görsel/anlatım kullanılmıştır"

    TRANSITION_DURATION_SECONDS = 0.25
    TRANSITION_XFADE_MAP = {
        "crossfade": "fade",
        "fade_black": "fadeblack",
    }

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
        clip_durations: list[float] = []
        subtitle_segments: list[tuple[int, float, str | None]] = []
        placeholder_scene_numbers: list[int] = []

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

            closing_image_path = self._resolve_closing_image(
                project_data,
                is_last_scene=(index == len(scene_dirs)),
            )

            location_map_path = None

            if closing_image_path is None:
                location_map_path = self._resolve_location_map(
                    project_data,
                    project_dir,
                    is_target_scene=(
                        index == 2 and len(scene_dirs) >= 3
                    ),
                )

            if closing_image_path is not None:
                video_files = []
                image_files = [closing_image_path]
                print(
                    "  🎬 Yüklenmiş kapanış görseli kullanılıyor "
                    f"({closing_image_path.name})"
                )
            elif location_map_path is not None:
                video_files = []
                image_files = [location_map_path]
                print(
                    "  🗺️ Konum haritası kullanılıyor "
                    f"({location_map_path.name})"
                )
            else:
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
                    f"  ⚠ No usable media in {scene_dir}; falling back "
                    "to a placeholder background so the narration for "
                    "this scene isn't lost."
                )
                self._placeholder_to_clip(
                    destination=clip_path,
                    duration=scene_duration,
                    audio_path=audio_path,
                )
                placeholder_scene_numbers.append(scene_number)

            clip_files.append(clip_path)
            clip_durations.append(scene_duration)

        if not clip_files:
            raise ValueError("No usable media files found.")

        output_path = render_dir / "final_video.mp4"
        transition = str(
            project_data.get("scene_transition", "crossfade")
        ).strip().lower()

        xfade_name = self.TRANSITION_XFADE_MAP.get(transition)
        start_offsets: list[float] | None = None

        if xfade_name is not None and len(clip_files) > 1:
            try:
                start_offsets = self._concat_with_transitions(
                    clip_files,
                    clip_durations,
                    xfade_name,
                    output_path,
                )
            except Exception as error:
                print(
                    f"  ⚠ Sahne geçişi uygulanamadı ({error}); "
                    "sert kesime düşülüyor."
                )
                self._concat_stream_copy(
                    clip_files, render_dir, output_path
                )

        if start_offsets is None:
            self._concat_stream_copy(clip_files, render_dir, output_path)
            start_offsets = self._naive_offsets(clip_durations)

        if not output_path.exists() or output_path.stat().st_size == 0:
            raise RuntimeError(
                f"Final video was not created: {output_path}"
            )

        subtitle_offset = 0.0
        hook_scene_number = self._find_hook_scene_number(storyboard)

        if hook_scene_number is not None:
            hook_clip_path = (
                clips_dir / f"clip_{hook_scene_number:03d}.mp4"
            )

            if hook_clip_path in clip_files:
                hook_scene_duration = clip_durations[
                    clip_files.index(hook_clip_path)
                ]
                hook_duration = min(3.0, hook_scene_duration)

                if hook_duration >= 1.0:
                    try:
                        teaser_path = render_dir / "hook_teaser.mp4"
                        hooked_path = render_dir / "final_video_hook.mp4"
                        self._build_hook_clip(
                            hook_clip_path, teaser_path, hook_duration
                        )
                        self._concat_stream_copy(
                            [teaser_path, output_path],
                            render_dir,
                            hooked_path,
                        )
                        if (
                            not hooked_path.exists()
                            or hooked_path.stat().st_size == 0
                        ):
                            raise RuntimeError(
                                "Cold open concat produced an empty file."
                            )
                        hooked_path.replace(output_path)
                        subtitle_offset = hook_duration
                        print(
                            "  🎬 Cold open eklendi "
                            f"(sahne {hook_scene_number}, "
                            f"{hook_duration:.1f}s)"
                        )
                    except Exception as error:
                        print(
                            f"  ⚠ Cold open eklenemedi ({error}); "
                            "atlanıyor."
                        )

        if project_data.get("background_music_enabled"):
            try:
                self._apply_background_music(
                    project_dir,
                    output_path,
                    project_data,
                )
            except Exception as error:
                # A music-mixing failure (bad track, ffmpeg filter issue)
                # shouldn't cost the whole render -- the video without
                # music is still a valid, usable result.
                print(
                    f"  ⚠ Arka plan müziği eklenemedi, müziksiz devam "
                    f"ediliyor: {error}"
                )

        if project_data.get("subtitles_enabled"):
            srt_path = render_dir / "subtitles.srt"
            self._write_srt(
                srt_path,
                subtitle_segments,
                start_offsets,
                global_offset=subtitle_offset,
            )
            print(f"  ✅ Subtitles written ({srt_path})")

            txt_path = render_dir / "subtitles.txt"
            self._write_txt(txt_path, subtitle_segments)
            print(f"  ✅ Transcript written ({txt_path})")

            if project_data.get("subtitles_burn_in"):
                self._burn_in_subtitles(output_path, srt_path)

        if project_data.get("ai_disclosure_enabled"):
            try:
                self._burn_ai_disclosure(output_path)
            except Exception as error:
                # Same tolerance as the music mix above -- a disclosure
                # banner failing to burn in shouldn't cost the whole render.
                print(
                    f"  ⚠ Yapay zeka ibaresi eklenemedi, ibaresiz devam "
                    f"ediliyor: {error}"
                )

        warnings_path = render_dir / "media_warnings.json"

        if placeholder_scene_numbers:
            warnings_path.write_text(
                json.dumps(
                    {"placeholder_scenes": placeholder_scene_numbers},
                    ensure_ascii=False,
                    indent=2,
                ),
                encoding="utf-8",
            )
        elif warnings_path.exists():
            # A prior render (before a "Yeniden Üret" on media) may have
            # left a stale warning behind -- clear it so a clean re-render
            # doesn't keep showing an outdated alert.
            warnings_path.unlink()

        return output_path

    def _concat_stream_copy(
        self,
        clip_files: list[Path],
        render_dir: Path,
        output_path: Path,
    ) -> None:
        """Hard-cut concatenation -- pure stream copy, no re-encode.
        The default/fallback path: fastest, and the only option that
        never risks an odd ffmpeg filtergraph edge case.
        """

        concat_file = render_dir / "concat.txt"

        concat_file.write_text(
            "\n".join(
                f"file '{clip.resolve()}'"
                for clip in clip_files
            ),
            encoding="utf-8",
        )

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

    def is_valid_output(self, path: Path) -> bool:
        """Best-effort sanity check that a rendered video file is a
        complete, playable container -- not just a non-empty file.

        Guards against a class of bug where the render process gets
        interrupted mid-write (service restart, OOM kill, disk full)
        and leaves a truncated MP4 (e.g. missing its moov atom) that
        still passes an exists()+size>0 check but won't actually play.
        A resume/skip decision based only on that weaker check would
        wrongly treat the broken file as finished output.
        """

        try:
            return self._probe_duration(path) > 0
        except Exception:
            return False

    def _naive_offsets(
        self,
        clip_durations: list[float],
    ) -> list[float]:
        """Scene start times for a plain hard-cut concat -- each scene
        starts exactly where the previous one ended, no overlap.
        """

        offsets: list[float] = []
        cursor = 0.0

        for duration in clip_durations:
            offsets.append(cursor)
            cursor += duration

        return offsets

    def _concat_with_transitions(
        self,
        clip_files: list[Path],
        clip_durations: list[float],
        xfade_name: str,
        output_path: Path,
    ) -> list[float]:
        """Chain adjacent clips with ffmpeg's xfade filter for video;
        audio is trimmed+concatenated cleanly, NOT crossfaded (see the
        comment at the filter string itself for why -- blending two
        narration waveforms together audibly sounds like the speaker
        repeating/stuttering, not a smooth transition).

        Merges are done ONE PAIR AT A TIME (the running combined clip
        so far + the next scene clip), never all N clips as simultaneous
        inputs to a single ffmpeg filtergraph. A single N-input version
        was tried first and OOM-killed a real render at 23 scenes (one
        ffmpeg process holding ~5.6GB RSS decoding every clip at once) --
        peak memory here stays roughly constant (about two clips' worth)
        regardless of scene count, at the cost of re-encoding the
        growing prefix on every merge instead of touching each clip
        exactly once. Renders with many scenes take noticeably longer
        as a result, but that's a much better trade than crashing the
        whole service.

        The per-pair transition length is clamped to a fraction of both
        adjacent clips' own duration so a couple of very short scenes
        can't produce a negative/degenerate offset.

        Returns each scene's actual start time in the combined output
        (index-aligned with clip_files) -- unlike a hard cut, each
        transition shortens the combined timeline by its own duration,
        so a scene's real start drifts earlier than the naive sum of
        the durations before it. Callers building subtitle timestamps
        need these, not clip_durations' cumulative sum, or captions
        drift out of sync more with every transition.
        """

        tmp_dir = output_path.parent / "transitions_tmp"
        tmp_dir.mkdir(parents=True, exist_ok=True)

        current_path = clip_files[0]
        current_duration = clip_durations[0]
        current_is_temp = False
        start_offsets = [0.0]

        try:
            for i in range(1, len(clip_files)):
                duration = max(
                    0.1,
                    min(
                        self.TRANSITION_DURATION_SECONDS,
                        current_duration * 0.4,
                        clip_durations[i] * 0.4,
                    ),
                )
                offset = max(0.0, current_duration - duration)
                start_offsets.append(offset)

                merged_path = tmp_dir / f"merge_{i:04d}.mp4"

                # Audio deliberately does NOT crossfade (acrossfade
                # blends the two waveforms together over `duration`,
                # which -- unlike blending two video frames -- means
                # briefly playing the tail of one sentence and the
                # start of the next SIMULTANEOUSLY). TRANSITION_DURATION
                # is short enough to fit inside each clip's trailing
                # silence (AUDIO_PADDING_SECONDS), so instead audio just
                # gets that same silent tail trimmed off clip A and
                # cleanly concatenated with clip B's audio -- same
                # shortened duration as the video's xfade output, zero
                # waveform overlap. asetpts resets timestamps after the
                # trim so concat sees a clean, monotonic stream.
                audio_trim_end = max(0.0, current_duration - duration)

                command = [
                    "ffmpeg",
                    "-y",
                    "-i",
                    str(current_path),
                    "-i",
                    str(clip_files[i]),
                    "-filter_complex",
                    (
                        f"[0:v][1:v]xfade=transition={xfade_name}:"
                        f"duration={duration:.3f}:offset={offset:.3f}[v];"
                        f"[0:a]atrim=end={audio_trim_end:.3f},"
                        f"asetpts=PTS-STARTPTS[a0t];"
                        f"[a0t][1:a]concat=n=2:v=0:a=1[a]"
                    ),
                    "-map",
                    "[v]",
                    "-map",
                    "[a]",
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
                    "-c:a",
                    "aac",
                    "-b:a",
                    "192k",
                    "-ar",
                    "48000",
                    "-ac",
                    "2",
                    "-movflags",
                    "+faststart",
                    str(merged_path),
                ]

                self._run(command)

                if not merged_path.exists() or merged_path.stat().st_size == 0:
                    raise RuntimeError(
                        f"Transition merge failed at clip {i + 1}: "
                        f"{merged_path}"
                    )

                if current_is_temp:
                    current_path.unlink(missing_ok=True)

                current_path = merged_path
                current_is_temp = True

                # Re-probe the real, on-disk duration instead of trusting
                # the arithmetic running sum. Each pairwise merge re-encodes
                # audio to AAC, which has its own small encoder delay/
                # rounding on top of libx264 frame-boundary rounding; those
                # sub-frame errors don't cancel out, they accumulate merge
                # after merge. The margin this trim math depends on
                # (AUDIO_PADDING_SECONDS - TRANSITION_DURATION_SECONDS =
                # only ~0.1s of real silence) is easily eaten by that drift
                # over enough scenes, at which point the "silent tail" trim
                # lands inside actual narration instead -- audibly playing
                # two sentences on top of each other at that transition.
                # Grounding every step in the measured duration prevents
                # that error from ever compounding.
                current_duration = self._probe_duration(current_path)

            shutil.move(str(current_path), str(output_path))
        finally:
            shutil.rmtree(tmp_dir, ignore_errors=True)

        return start_offsets

    def _build_hook_clip(
        self,
        source_clip: Path,
        destination: Path,
        duration: float,
    ) -> None:
        """Trim the first `duration` seconds off an already-rendered
        scene clip for use as a cold-open teaser. Video is stream-copied
        (cutting from t=0 needs no keyframe seek, so -c:v copy is safe
        here) and audio is replaced with silence rather than reusing the
        scene's real narration, which will play again moments later once
        the video cuts back to that scene for real.
        """

        command = [
            "ffmpeg",
            "-y",
            "-i",
            str(source_clip),
            "-f",
            "lavfi",
            "-i",
            "anullsrc=r=48000:cl=stereo",
            "-t",
            f"{duration:.3f}",
            "-map",
            "0:v:0",
            "-map",
            "1:a:0",
            "-c:v",
            "copy",
            "-c:a",
            "aac",
            "-b:a",
            "192k",
            "-shortest",
            "-movflags",
            "+faststart",
            str(destination),
        ]

        self._run(command)

        if not destination.exists() or destination.stat().st_size == 0:
            raise RuntimeError(
                f"Hook teaser clip was not created: {destination}"
            )

    def _find_hook_scene_number(
        self,
        storyboard: dict[str, Any],
    ) -> int | None:
        """Which scene (if any) the storyboard agent flagged as the
        most visually striking moment, for use as a cold-open teaser
        shown before the video cuts back to its real start. Never the
        first or last scene -- that would either duplicate the real
        opening or spoil the ending -- and only for videos with enough
        scenes that a teaser+reset actually makes sense.
        """

        scenes = storyboard.get("scenes")

        if not isinstance(scenes, list) or len(scenes) < 3:
            return None

        for position, scene in enumerate(scenes, start=1):
            if not isinstance(scene, dict):
                continue

            if not scene.get("hook_worthy"):
                continue

            if position == 1 or position == len(scenes):
                continue

            try:
                return int(scene.get("scene", position))
            except (TypeError, ValueError):
                return position

        return None

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

        try:
            music_volume = float(
                project_data.get("music_volume", 0.18)
            )
        except (TypeError, ValueError):
            music_volume = 0.18

        music_volume = min(1.0, max(0.0, music_volume))

        volume_stage = self._music_volume_stage(
            music_volume,
            fade_start,
        )

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
                f"[1:a]{volume_stage},"
                f"afade=t=out:st={fade_start:.2f}:d={fade_duration:.2f}"
                f"[music];"
                f"[0:a][music]amix=inputs=2:duration=first:"
                f"dropout_transition=0:normalize=0[aout]"
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

    def _resolve_closing_image(
        self,
        project_data: dict[str, Any],
        is_last_scene: bool,
    ) -> Path | None:
        """A fixed, user-uploaded closing-shot image (configured in
        /settings) for the last scene of a documentary -- an alternative
        to the AI-generated closing shot (storyboard.txt's last-scene
        instruction) for anyone who wants a consistent, hand-designed
        ending across every video instead of a fresh one each time.
        Narration audio for that scene is untouched, only the visual is
        swapped. Requires the separate "closing_image_enabled" switch to
        be on -- having a file uploaded is not by itself enough, so a
        design can sit there unused until someone deliberately flips it
        on. Falls back to the normal scene media on any problem (not
        configured, switch off, file missing) rather than failing the
        render."""

        if not is_last_scene:
            return None

        content_type = str(
            project_data.get("content_type", "")
        ).strip().lower()

        if content_type != "documentary":
            return None

        try:
            from app.core.config import settings

            if not settings.is_configured("closing_image_enabled"):
                return None

            if not settings.is_configured("closing_image"):
                return None

            path = Path(settings.closing_image)

            if path.exists() and path.stat().st_size > 0:
                return path
        except Exception as error:
            print(
                f"  ⚠ Kapanış görseli okunamadı, sahne kendi medyasını "
                f"kullanacak: {error}"
            )

        return None

    def _resolve_location_map(
        self,
        project_data: dict[str, Any],
        project_dir: Path,
        is_target_scene: bool,
    ) -> Path | None:
        """An optional map image, geocoded from the video's SEO-derived
        "location" field, shown for one early scene so the viewer can
        place a documentary's subject on a map. Requires the
        "location_map_enabled" toggle and a usable content_type. Falls
        back to the normal scene media on any problem (toggle off, no
        location, geocoding/rendering failure) rather than failing the
        render -- this is a nice-to-have visual, never worth losing a
        scene's narration over."""

        if not is_target_scene:
            return None

        if not project_data.get("location_map_enabled"):
            return None

        content_type = str(
            project_data.get("content_type", "")
        ).strip().lower()

        if content_type not in {"documentary", "news", "informational"}:
            return None

        cached_path = project_dir / "location_map.png"

        if cached_path.exists() and cached_path.stat().st_size > 0:
            return cached_path

        try:
            seo_data: dict[str, Any] = {}
            seo_path = project_dir / "seo.json"

            if seo_path.exists():
                seo_data = self._load_json(seo_path)

            place_name = str(seo_data.get("location", "")).strip()

            if not place_name:
                return None

            from app.services.map_service import MapService

            map_service = MapService()
            coordinates = map_service.geocode(place_name)

            if coordinates is None:
                return None

            latitude, longitude = coordinates
            map_service.render_map(
                latitude,
                longitude,
                cached_path,
                width=self.WIDTH,
                height=self.HEIGHT,
            )

            if cached_path.exists() and cached_path.stat().st_size > 0:
                return cached_path
        except Exception as error:
            print(
                f"  ⚠ Konum haritası oluşturulamadı, sahne kendi "
                f"medyasını kullanacak: {error}"
            )

        return None

    def _music_volume_stage(
        self,
        music_volume: float,
        fade_start: float,
    ) -> str:
        """Build the ffmpeg `volume` stage for the music track.

        Narration runs almost back-to-back scene to scene (only a ~0.35s
        padding gap between them, see AUDIO_PADDING_SECONDS) -- too short
        for a swell to be audible or feel like anything but a glitch. The
        one genuinely quiet stretch is the tail: by the time the video
        reaches its existing fade-out window, narration has finished. So
        instead of chasing every micro-pause, the music ramps up to a
        fuller "swell" during that tail and holds it until the existing
        afade=out (applied by the caller, right after this stage) carries
        it down to silence -- a swell into the ending rather than an
        abrupt cut. Falls back to a flat volume for very short videos
        where there isn't enough tail room for the ramp to sound smooth
        rather than choppy.
        """

        swell_volume = min(0.55, music_volume * 2.5)
        ramp_duration = min(2.0, fade_start)

        if ramp_duration < 0.5 or swell_volume <= music_volume:
            return f"volume={music_volume:.3f}"

        swell_start = fade_start - ramp_duration

        volume_expr = (
            f"if(lt(t,{swell_start:.2f}),{music_volume:.3f},"
            f"min({swell_volume:.3f},{music_volume:.3f}+"
            f"({swell_volume:.3f}-{music_volume:.3f})*"
            f"(t-{swell_start:.2f})/{ramp_duration:.2f}))"
        )

        return f"volume=eval=frame:volume='{volume_expr}'"

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
        start_offsets: list[float],
        global_offset: float = 0.0,
    ) -> None:
        blocks: list[str] = []
        subtitle_index = 0

        for i, (_scene_number, duration, text) in enumerate(segments):
            scene_start = global_offset + start_offsets[i]
            scene_end = (
                global_offset + start_offsets[i + 1]
                if i + 1 < len(start_offsets)
                else scene_start + duration
            )
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

        # BorderStyle=3 draws an opaque box behind the text instead of
        # just an outline (BorderStyle=1) -- a plain outline wasn't
        # enough to stay readable on some bright/busy scenes. BackColour
        # is ASS's &HAABBGGRR format; alpha 80 (~50% opaque) gives a
        # soft dark backing without going flat black. Outline now sets
        # the box's padding around the text rather than a text stroke.
        force_style = (
            "FontSize=18,PrimaryColour=&H00FFFFFF,"
            "BackColour=&H80000000,BorderStyle=3,"
            "Outline=3,Shadow=0,Alignment=2,MarginV=80"
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

    def _burn_ai_disclosure(self, video_path: Path) -> None:
        """Burn a brief on-screen disclosure banner into the opening
        seconds of the video ("this video uses AI-assisted visuals/
        narration"). YouTube's synthetic-content guidance only requires
        this to appear once near the start, not throughout -- a short
        banner is enough and stays far less intrusive than a persistent
        watermark. Opt-in per project (not every video uses AI-generated
        media), toggled separately from the Studio-side "altered or
        synthetic content" disclosure the creator sets per upload.
        """

        escaped_text = (
            self.AI_DISCLOSURE_TEXT
            .replace("\\", "\\\\")
            .replace(":", "\\:")
            .replace("'", "’")
        )

        burned_path = video_path.with_name(
            "final_video_disclosure.mp4"
        )

        command = [
            "ffmpeg",
            "-y",
            "-i",
            str(video_path),
            "-vf",
            (
                f"drawtext=text='{escaped_text}':"
                "fontsize=22:fontcolor=white:"
                "box=1:boxcolor=black@0.55:boxborderw=10:"
                "x=(w-text_w)/2:y=h-th-40:"
                f"enable='between(t,0,{self.AI_DISCLOSURE_SECONDS:.1f})'"
            ),
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
                f"AI disclosure burn-in failed: {burned_path}"
            )

        burned_path.replace(video_path)

        print("  ✅ AI disclosure banner burned into video")

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
                "force_original_aspect_ratio=increase,"
                f"crop={self.WIDTH}:{self.HEIGHT},"
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

    def _placeholder_to_clip(
        self,
        destination: Path,
        duration: float,
        audio_path: Path | None,
    ) -> None:
        """Fallback clip for a scene whose image/video generation failed.

        Narration audio must never be silently dropped just because the
        visual side of a scene failed -- a plain dark background still
        carries the spoken content, while skipping the scene entirely
        (the previous behavior) cut the narration itself from the final
        video with no warning. This is deliberately the last resort, not
        a normal path -- real media should always be preferred.
        """

        command = [
            "ffmpeg",
            "-y",
            "-f",
            "lavfi",
            "-i",
            f"color=c=0x14203a:s={self.WIDTH}x{self.HEIGHT}:"
            f"d={duration:.3f}:r={self.FPS}",
        ]

        if audio_path is not None:
            command.extend([
                "-i",
                str(audio_path),
            ])

        command.extend([
            "-t",
            f"{duration:.3f}",
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
