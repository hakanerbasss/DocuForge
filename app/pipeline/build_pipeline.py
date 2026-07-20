import json
import threading
import time
from collections.abc import Callable
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from rich.console import Console

from app.agents.registry import AgentRegistry
from app.models.project import DocumentaryProject
from app.pipeline.definitions import (
    get_agent_definition,
    get_default_pipeline_steps,
)
from app.pipeline.exceptions import PipelineAwaitingUpload
from app.services.media_builder import MediaBuilder
from app.services.narration_builder import NarrationBuilder
from app.services.project_service import ProjectService, load_project
from app.services.render_service import RenderService
from app.services.thumbnail_service import ThumbnailService
from app.services.voice_service import VoiceService


console = Console()

# Which project.json fields may be changed when regenerating a given step.
# Keeps "regenerate with different settings" from silently accepting an
# override that a step's action doesn't actually read.
STEP_ALLOWED_OVERRIDES: dict[str, set[str]] = {
    "research": {
        "language",
        "content_type",
        "target_duration_seconds",
        "source_material",
    },
    "voice": {"voice_provider", "voice_name", "voice_speed"},
    "media": {"image_provider", "video_provider", "media_mode"},
    "render": {
        "resolution",
        "fps",
        "scene_transition",
        "background_music_enabled",
        "music_provider",
        "music_track",
        "music_volume",
        "subtitles_enabled",
        "subtitles_burn_in",
        "ai_disclosure_enabled",
        "location_map_enabled",
    },
    "thumbnail": {"thumbnail_source", "thumbnail_hook_override"},
    "seo": {"source_citation"},
}


class PipelineCancelled(Exception):
    """Raised between steps when the caller has requested cancellation.

    Cancellation is cooperative, checked only between steps -- an
    in-flight AI call or ffmpeg render can't be interrupted mid-call
    without much more invasive work, so cancelling stops the pipeline
    before the *next* step starts, not instantly.
    """


class BuildPipeline:
    """Run and resume the complete DocuForge production pipeline."""

    STATE_FILE = "pipeline_state.json"

    def run(
        self,
        topic: str,
        source_material: str = "",
        source_citation: str = "",
        language: str = "tr",
        content_type: str = "documentary",
        target_duration_seconds: int = 600,
        media_mode: str = "mixed",
        text_provider: str = "deepseek",
        image_provider: str = "pexels",
        video_provider: str = "pexels",
        voice_provider: str = "supertonic",
        voice_name: str = "M1",
        voice_speed: float = 1.0,
        resolution: str = "720p",
        fps: int = 30,
        scene_transition: str = "crossfade",
        background_music_enabled: bool = False,
        music_provider: str = "local",
        music_track: str = "",
        music_volume: float = 0.18,
        subtitles_enabled: bool = False,
        subtitles_burn_in: bool = False,
        ai_disclosure_enabled: bool = False,
        location_map_enabled: bool = False,
        thumbnail_enabled: bool = False,
        thumbnail_source: str = "auto",
        template: str | None = None,
        cancel_event: threading.Event | None = None,
    ) -> Path:
        """Create a configured project and run all pipeline stages."""

        console.print("[bold]📂 Creating project...[/bold]")

        resolved_content_type = content_type.strip().lower()

        # Backward compatibility for older callers using template=...
        if (
            template
            and resolved_content_type == "documentary"
        ):
            resolved_content_type = template.strip().lower()

        project = DocumentaryProject(
            title=topic,
            source_material=source_material,
            source_citation=source_citation,
            language=language,
            content_type=resolved_content_type,
            target_duration_seconds=target_duration_seconds,
            media_mode=media_mode,
            text_provider=text_provider,
            image_provider=image_provider,
            video_provider=video_provider,
            voice_provider=voice_provider,
            voice_name=voice_name,
            voice_speed=voice_speed,
            resolution=resolution,
            fps=fps,
            scene_transition=scene_transition,
            background_music_enabled=background_music_enabled,
            music_provider=music_provider,
            music_track=music_track,
            music_volume=music_volume,
            subtitles_enabled=subtitles_enabled,
            subtitles_burn_in=subtitles_burn_in,
            ai_disclosure_enabled=ai_disclosure_enabled,
            location_map_enabled=location_map_enabled,
            thumbnail_enabled=thumbnail_enabled,
            thumbnail_source=thumbnail_source,
        )

        project_service = ProjectService()
        project_dir = project_service.create(project)

        console.print("[bold green]✅ Project created[/bold green]\n")

        return self._run_pipeline(project_dir, cancel_event=cancel_event)

    def resume(
        self,
        project_path: str,
        cancel_event: threading.Event | None = None,
    ) -> Path:
        """Resume an existing project from incomplete stages."""

        project_dir = Path(project_path)

        if not project_dir.exists():
            raise FileNotFoundError(
                f"Project directory not found: {project_dir}"
            )

        if not (project_dir / "project.json").exists():
            raise FileNotFoundError(
                f"project.json not found in: {project_dir}"
            )

        console.print(
            f"[bold cyan]▶ Resuming project:[/bold cyan] "
            f"{project_dir}\n"
        )

        return self._run_pipeline(project_dir, cancel_event=cancel_event)

    def regenerate_step(
        self,
        project_path: str,
        step_key: str,
        overrides: dict[str, Any] | None = None,
    ) -> Path:
        """Re-run a single stage, invalidating everything downstream of it.

        Downstream output files are deleted so a later resume() naturally
        regenerates them; this step itself is generated immediately so the
        caller can review it before continuing.

        `overrides` lets the caller change the project settings that
        matter for this specific step (e.g. voice_name when regenerating
        "voice") before it runs -- persisted to project.json, not just
        used for this one call. Only fields listed in
        STEP_ALLOWED_OVERRIDES[step_key] are accepted; anything else
        raises, since a step's action wouldn't read it anyway.
        """

        project_dir = Path(project_path)

        if not (project_dir / "project.json").exists():
            raise FileNotFoundError(
                f"project.json not found in: {project_dir}"
            )

        if overrides:
            self._apply_overrides(project_dir, step_key, overrides)

        project_data = load_project(str(project_dir))
        state = self._load_state(project_dir)

        agent_steps = get_default_pipeline_steps()
        service_steps = self._build_service_steps(
            project_dir,
            project_data,
        )

        agent_step_by_key = {step.key: step for step in agent_steps}
        service_step_by_key = {
            step["key"]: step for step in service_steps
        }

        ordered_keys = [step.key for step in agent_steps] + [
            step["key"] for step in service_steps
        ]

        if step_key not in ordered_keys:
            raise ValueError(f"Unknown pipeline step: {step_key}")

        step_index = ordered_keys.index(step_key)
        downstream_keys = ordered_keys[step_index + 1:]

        for key in downstream_keys:
            self._invalidate_step(
                project_dir=project_dir,
                state=state,
                step_key=key,
                agent_step_by_key=agent_step_by_key,
                service_step_by_key=service_step_by_key,
                is_target=False,
            )

        self._invalidate_step(
            project_dir=project_dir,
            state=state,
            step_key=step_key,
            agent_step_by_key=agent_step_by_key,
            service_step_by_key=service_step_by_key,
            is_target=True,
        )

        state["status"] = "running"
        self._save_state(project_dir, state)

        console.print(
            f"[bold cyan]🔁 Regenerating step:[/bold cyan] "
            f"{step_key}\n"
        )

        if step_key in agent_step_by_key:
            definition = get_agent_definition(step_key)
            self._run_agent_step(
                index=1,
                total_steps=1,
                step=agent_step_by_key[step_key],
                definition=definition,
                project_dir=project_dir,
                project_data=project_data,
                state=state,
            )
        else:
            self._run_service_step(
                index=1,
                total_steps=1,
                step=service_step_by_key[step_key],
                project_dir=project_dir,
                state=state,
            )

        return project_dir

    def _apply_overrides(
        self,
        project_dir: Path,
        step_key: str,
        overrides: dict[str, Any],
    ) -> None:
        allowed = STEP_ALLOWED_OVERRIDES.get(step_key, set())
        unknown = set(overrides) - allowed

        if unknown:
            raise ValueError(
                f"Step '{step_key}' does not accept overrides for: "
                f"{', '.join(sorted(unknown))}. "
                f"Allowed: {', '.join(sorted(allowed)) or '(none)'}"
            )

        project_service = ProjectService()
        project = project_service.load(project_dir)

        data = project.to_dict()
        data.update(overrides)

        updated_project = DocumentaryProject.from_dict(data)
        project_service.save(project_dir, updated_project)

    def _invalidate_step(
        self,
        *,
        project_dir: Path,
        state: dict[str, Any],
        step_key: str,
        agent_step_by_key: dict[str, Any],
        service_step_by_key: dict[str, Any],
        is_target: bool,
    ) -> None:
        """Delete a step's output (or reset it) and drop it from state.

        `voice` is a special case: its registered output file
        (audio/manifest.json) is also narration_scenes' output and is read
        as VoiceService's *input*. When voice is the step being
        regenerated directly, reset its per-scene status instead of
        deleting the manifest outright, so VoiceService still has
        somewhere to read scene text from.
        """

        if step_key == "voice" and is_target:
            self._reset_voice_manifest(project_dir)
        else:
            if step_key in agent_step_by_key:
                definition = get_agent_definition(step_key)
                output_path = project_dir / definition.output_file
            else:
                output_path = Path(
                    service_step_by_key[step_key]["output"]
                )

            if output_path.exists():
                output_path.unlink()

            if step_key == "thumbnail":
                # ThumbnailService writes its own 4 variants + a vertical
                # cover alongside the canonical output file above --
                # clear those too so a stale variant never outlives the
                # step that made it.
                self._clear_thumbnail_variants(project_dir)

        state.get("steps", {}).pop(step_key, None)

    def _clear_thumbnail_variants(self, project_dir: Path) -> None:
        for name in (
            *ThumbnailService.VARIANT_NAMES,
            "thumbnail_vertical.jpg",
        ):
            path = project_dir / name
            if path.exists():
                path.unlink()

    def _reset_voice_manifest(self, project_dir: Path) -> None:
        """Mark every scene as needing new audio without losing scene text."""

        manifest_path = project_dir / "audio" / "manifest.json"
        manifest = self._try_load_json(manifest_path)

        if manifest is None:
            return

        scenes = manifest.get("scenes")

        if isinstance(scenes, list):
            for scene in scenes:
                if isinstance(scene, dict):
                    scene["status"] = "text_ready"
                    scene["audio_duration"] = None

        manifest_path.write_text(
            json.dumps(
                manifest,
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )

    def _build_service_steps(
        self,
        project_dir: Path,
        project_data: dict[str, Any],
    ) -> list[dict[str, Any]]:
        service_steps: list[dict[str, Any]] = [
            {
                "key": "media",
                "icon": "📦",
                "name": "Media Builder",
                "output": project_dir / "media" / "manifest.json",
                "action": lambda: MediaBuilder().build(
                    str(project_dir)
                ),
                "validator": lambda: self._media_is_complete(
                    project_dir
                ),
            },
            {
                "key": "narration_scenes",
                "icon": "📝",
                "name": "Scene Narrations",
                "output": project_dir / "audio" / "manifest.json",
                "action": lambda: NarrationBuilder().build(
                    str(project_dir)
                ),
                "validator": lambda: self._narration_scenes_complete(
                    project_dir
                ),
            },
            {
                "key": "voice",
                "icon": "🎙",
                "name": "Voice Generation",
                "output": project_dir / "audio" / "manifest.json",
                "action": lambda: VoiceService().generate(
                    str(project_dir),
                    provider_key=str(
                        project_data.get(
                            "voice_provider",
                            "supertonic",
                        )
                    ),
                    voice_name=str(
                        project_data.get(
                            "voice_name",
                            "M1",
                        )
                    ),
                    speed=float(
                        project_data.get(
                            "voice_speed",
                            1.0,
                        )
                    ),
                ),
                "validator": lambda: self._voice_is_complete(
                    project_dir
                ),
            },
            {
                "key": "render",
                "icon": "🎬",
                "name": "FFmpeg Render",
                "output": (
                    project_dir
                    / "render"
                    / "final_video.mp4"
                ),
                "action": lambda: RenderService().render(
                    str(project_dir)
                ),
                "validator": lambda: self._render_is_complete(
                    project_dir
                ),
            },
        ]

        if project_data.get("thumbnail_enabled"):
            service_steps.append({
                "key": "thumbnail",
                "icon": "🖼",
                "name": "Thumbnail",
                "output": project_dir / "thumbnail.jpg",
                "action": lambda: ThumbnailService().generate(
                    str(project_dir)
                ),
                "validator": lambda: (
                    project_dir / "thumbnail.jpg"
                ).exists(),
            })

        return service_steps

    def _check_cancelled(
        self,
        cancel_event: threading.Event | None,
        project_dir: Path,
        state: dict[str, Any],
    ) -> None:
        if cancel_event is None or not cancel_event.is_set():
            return

        state["status"] = "cancelled"
        self._save_state(project_dir, state)

        console.print(
            "[bold yellow]⏹ Pipeline cancelled by request[/bold yellow]"
        )

        raise PipelineCancelled(
            "Üretim kullanıcı tarafından iptal edildi."
        )

    def _run_pipeline(
        self,
        project_dir: Path,
        cancel_event: threading.Event | None = None,
    ) -> Path:
        """Run AI-agent and production-service stages in order."""

        project_data = load_project(str(project_dir))
        state = self._load_state(project_dir)
        total_start = time.perf_counter()

        agent_steps = get_default_pipeline_steps()
        service_steps = self._build_service_steps(
            project_dir,
            project_data,
        )

        total_steps = len(agent_steps) + len(service_steps)

        for index, step in enumerate(agent_steps, start=1):
            self._check_cancelled(cancel_event, project_dir, state)

            definition = get_agent_definition(step.key)
            output_path = project_dir / definition.output_file

            output_exists = (
                output_path.exists()
                and output_path.stat().st_size > 0
            )

            if output_exists:
                state_was_complete = (
                    state.get("steps", {})
                    .get(step.key, {})
                    .get("status")
                    == "completed"
                )

                self._record_existing_completion(
                    project_dir=project_dir,
                    state=state,
                    step_key=step.key,
                    output_path=output_path,
                )

                message = (
                    "already completed — skipped"
                    if state_was_complete
                    else "output found — registered and skipped"
                )

                console.print(
                    f"[dim][{index}/{total_steps}] "
                    f"{definition.icon} {definition.name} "
                    f"{message}[/dim]\n"
                )
                continue

            self._run_agent_step(
                index=index,
                total_steps=total_steps,
                step=step,
                definition=definition,
                project_dir=project_dir,
                project_data=project_data,
                state=state,
            )

        service_start_index = len(agent_steps) + 1

        for index, service_step in enumerate(
            service_steps,
            start=service_start_index,
        ):
            self._check_cancelled(cancel_event, project_dir, state)

            self._run_service_step(
                index=index,
                total_steps=total_steps,
                step=service_step,
                project_dir=project_dir,
                state=state,
            )

        total_elapsed = time.perf_counter() - total_start

        state["status"] = "completed"
        state["failed_step"] = None
        state["total_duration_seconds"] = round(
            total_elapsed,
            2,
        )

        self._save_state(project_dir, state)

        console.print(
            "[bold green]🎉 All pipeline stages completed[/bold green]"
        )

        return project_dir

    def _run_agent_step(
        self,
        *,
        index: int,
        total_steps: int,
        step: Any,
        definition: Any,
        project_dir: Path,
        project_data: dict[str, Any],
        state: dict[str, Any],
    ) -> None:
        """Execute one registered AI-agent stage."""

        output_path = project_dir / definition.output_file

        console.print(
            f"[bold][{index}/{total_steps}] "
            f"{definition.icon} Running "
            f"{definition.name} Agent...[/bold]"
        )

        # Clear a stale failure marker from a previous attempt the
        # instant this step actually starts (re)running -- otherwise a
        # live progress poll during a resume/retry still reads the old
        # "Hata: ..." from before, even though the step is genuinely in
        # progress right now, not stuck.
        state["failed_step"] = None
        self._save_state(project_dir, state)

        step_start = time.perf_counter()

        try:
            agent_input = step.input_loader(
                project_dir,
                project_data,
            )

            agent = AgentRegistry.create(step.key)
            language = str(
                project_data.get("language", "en")
            ).strip().lower()

            content_type = str(
                project_data.get("content_type", "documentary")
            )
            target_duration_seconds = int(
                project_data.get("target_duration_seconds", 600)
            )

            if step.key in {
                "research",
                "script",
                "storyboard",
                "seo",
            }:
                step_kwargs: dict[str, Any] = {
                    "language": language,
                    "content_type": content_type,
                    "target_duration_seconds": target_duration_seconds,
                }

                if step.key == "research":
                    step_kwargs["source_material"] = str(
                        project_data.get("source_material", "")
                    )

                if step.key == "seo":
                    step_kwargs["source_citation"] = str(
                        project_data.get("source_citation", "")
                    )

                result = agent.run(agent_input, **step_kwargs)
            else:
                result = agent.run(agent_input)



            if not isinstance(result, str) or not result.strip():
                raise ValueError(
                    f"{definition.name} Agent returned empty output."
                )

            output_path.write_text(
                result,
                encoding="utf-8",
            )

            elapsed = time.perf_counter() - step_start

            self._record_success(
                project_dir=project_dir,
                state=state,
                step_key=step.key,
                output_path=output_path,
                elapsed=elapsed,
            )

            console.print(
                f"[bold green]✅ {definition.name} "
                "completed[/bold green]"
            )
            console.print(
                f"[cyan]⏱ Step time: "
                f"{elapsed:.2f} seconds[/cyan]\n"
            )

        except Exception as error:
            self._record_failure_and_raise(
                project_dir=project_dir,
                state=state,
                step_key=step.key,
                step_name=definition.name,
                output_path=output_path,
                step_start=step_start,
                error=error,
            )

    def _run_service_step(
        self,
        *,
        index: int,
        total_steps: int,
        step: dict[str, Any],
        project_dir: Path,
        state: dict[str, Any],
    ) -> None:
        """Execute one non-agent production-service stage."""

        step_key = str(step["key"])
        icon = str(step["icon"])
        step_name = str(step["name"])
        output_path = Path(step["output"])

        action: Callable[[], Path] = step["action"]
        validator: Callable[[], bool] = step["validator"]

        state_complete = (
            state.get("steps", {})
            .get(step_key, {})
            .get("status")
            == "completed"
        )

        output_complete = validator()

        if state_complete and output_complete:
            console.print(
                f"[dim][{index}/{total_steps}] "
                f"{icon} {step_name} "
                "already completed — skipped[/dim]\n"
            )
            return

        if output_complete:
            self._record_existing_completion(
                project_dir=project_dir,
                state=state,
                step_key=step_key,
                output_path=output_path,
            )

            console.print(
                f"[dim][{index}/{total_steps}] "
                f"{icon} {step_name} output found "
                "— registered and skipped[/dim]\n"
            )
            return

        console.print(
            f"[bold][{index}/{total_steps}] "
            f"{icon} Running {step_name}...[/bold]"
        )

        # Clear a stale failure marker from a previous attempt the
        # instant this step actually starts (re)running -- otherwise a
        # live progress poll during a resume/retry still reads the old
        # "Hata: ..." from before, even though the step is genuinely in
        # progress right now, not stuck.
        state["failed_step"] = None
        self._save_state(project_dir, state)

        step_start = time.perf_counter()

        try:
            result_path = action()
            result_path = Path(result_path)

            if (
                not result_path.exists()
                or result_path.stat().st_size == 0
            ):
                raise RuntimeError(
                    f"{step_name} did not create a valid output: "
                    f"{result_path}"
                )

            elapsed = time.perf_counter() - step_start

            self._record_success(
                project_dir=project_dir,
                state=state,
                step_key=step_key,
                output_path=result_path,
                elapsed=elapsed,
            )

            console.print(
                f"[bold green]✅ {step_name} completed[/bold green]"
            )
            console.print(
                f"[cyan]⏱ Step time: "
                f"{elapsed:.2f} seconds[/cyan]\n"
            )

        except PipelineAwaitingUpload as awaiting:
            # A cooperative pause, not a failure: mark the run as awaiting
            # manual uploads (distinct from "failed") and re-raise so the
            # web layer can surface the upload UI. The next resume() picks
            # up right here once every scene image is in place.
            state["status"] = "awaiting_upload"
            state["failed_step"] = None
            state["awaiting_scenes"] = list(awaiting.missing_scenes)
            self._save_state(project_dir, state)

            console.print(
                "[bold yellow]⏸ Elle görsel yüklemesi bekleniyor: "
                f"{awaiting.missing_scenes}[/bold yellow]"
            )
            raise

        except Exception as error:
            self._record_failure_and_raise(
                project_dir=project_dir,
                state=state,
                step_key=step_key,
                step_name=step_name,
                output_path=output_path,
                step_start=step_start,
                error=error,
            )

    def _record_success(
        self,
        *,
        project_dir: Path,
        state: dict[str, Any],
        step_key: str,
        output_path: Path,
        elapsed: float,
    ) -> None:
        """Save a successfully completed pipeline stage."""

        state.setdefault("steps", {})

        state["steps"][step_key] = {
            "status": "completed",
            "duration_seconds": round(elapsed, 2),
            "output": str(output_path),
            "error": None,
            "finished_at": datetime.now(timezone.utc).isoformat(),
        }

        state["status"] = "running"
        state["failed_step"] = None

        self._save_state(project_dir, state)

    def _record_existing_completion(
        self,
        *,
        project_dir: Path,
        state: dict[str, Any],
        step_key: str,
        output_path: Path,
    ) -> None:
        """Register valid pre-existing output in pipeline state."""

        current = (
            state.get("steps", {})
            .get(step_key, {})
        )

        if (
            current.get("status") == "completed"
            and current.get("output")
        ):
            return

        state.setdefault("steps", {})

        state["steps"][step_key] = {
            "status": "completed",
            "duration_seconds": current.get(
                "duration_seconds",
                0,
            ),
            "output": str(output_path),
            "error": None,
            "finished_at": current.get("finished_at"),
        }

        state["status"] = "running"
        state["failed_step"] = None

        self._save_state(project_dir, state)

    def _record_failure_and_raise(
        self,
        *,
        project_dir: Path,
        state: dict[str, Any],
        step_key: str,
        step_name: str,
        output_path: Path,
        step_start: float,
        error: Exception,
    ) -> None:
        """Save stage failure and raise a pipeline exception."""

        elapsed = time.perf_counter() - step_start

        state.setdefault("steps", {})

        state["steps"][step_key] = {
            "status": "failed",
            "duration_seconds": round(elapsed, 2),
            "output": str(output_path),
            "error": str(error),
            "finished_at": datetime.now(timezone.utc).isoformat(),
        }

        state["status"] = "failed"
        state["failed_step"] = step_key

        self._save_state(project_dir, state)

        console.print(
            f"\n[bold red]❌ {step_name} failed[/bold red]"
        )
        console.print(f"[red]Error: {error}[/red]")

        console.print(
            "\n[yellow]Fix the problem, then run:[/yellow]"
        )
        console.print(
            f"[bold]docuforge resume {project_dir}[/bold]"
        )

        raise RuntimeError(
            f"{step_name} failed: {error}"
        ) from error

    def _media_is_complete(
        self,
        project_dir: Path,
    ) -> bool:
        """Validate the downloaded-media manifest and files."""

        manifest_path = (
            project_dir
            / "media"
            / "manifest.json"
        )

        manifest = self._try_load_json(manifest_path)

        if manifest is None:
            return False

        scenes = manifest.get("scenes")

        if not isinstance(scenes, list) or not scenes:
            return False

        if manifest.get("failed_count", 0) != 0:
            return False

        if manifest.get("completed_count") != len(scenes):
            return False

        for scene in scenes:
            if not isinstance(scene, dict):
                return False

            local_path = scene.get("local_path")

            if not isinstance(local_path, str):
                return False

            media_path = Path(local_path)

            if (
                not media_path.exists()
                or media_path.stat().st_size == 0
            ):
                return False

        return True

    def _narration_scenes_complete(
        self,
        project_dir: Path,
    ) -> bool:
        """Validate scene narration text files."""

        manifest_path = (
            project_dir
            / "audio"
            / "manifest.json"
        )

        manifest = self._try_load_json(manifest_path)

        if manifest is None:
            return False

        scenes = manifest.get("scenes")

        if not isinstance(scenes, list) or not scenes:
            return False

        for scene in scenes:
            if not isinstance(scene, dict):
                return False

            text_file = scene.get("text_file")

            if not isinstance(text_file, str):
                return False

            text_path = Path(text_file)

            if (
                not text_path.exists()
                or text_path.stat().st_size == 0
            ):
                return False

        return True

    def _voice_is_complete(
        self,
        project_dir: Path,
    ) -> bool:
        """Validate generated narration audio files."""

        manifest_path = (
            project_dir
            / "audio"
            / "manifest.json"
        )

        manifest = self._try_load_json(manifest_path)

        if manifest is None:
            return False

        scenes = manifest.get("scenes")

        if not isinstance(scenes, list) or not scenes:
            return False

        for scene in scenes:
            if not isinstance(scene, dict):
                return False

            if scene.get("status") != "audio_ready":
                return False

            audio_file = scene.get("audio_file")
            audio_duration = scene.get("audio_duration")

            if not isinstance(audio_file, str):
                return False

            audio_path = Path(audio_file)

            if (
                not audio_path.exists()
                or audio_path.stat().st_size == 0
            ):
                return False

            try:
                if float(audio_duration) <= 0:
                    return False
            except (TypeError, ValueError):
                return False

        return True

    def _render_is_complete(
        self,
        project_dir: Path,
    ) -> bool:
        """Validate the final rendered video.

        Non-empty isn't enough -- a render interrupted mid-write (a
        service restart, an OOM kill) can leave a truncated MP4 that's
        still non-empty on disk but has no moov atom and won't play.
        Without the playability check, resuming/regenerating a project
        would see that broken file and skip re-rendering entirely.
        """

        output_path = (
            project_dir
            / "render"
            / "final_video.mp4"
        )

        if not output_path.exists() or output_path.stat().st_size == 0:
            return False

        return RenderService().is_valid_output(output_path)

    def _try_load_json(
        self,
        path: Path,
    ) -> dict[str, Any] | None:
        """Safely load an optional JSON object."""

        if not path.exists() or path.stat().st_size == 0:
            return None

        try:
            data = json.loads(
                path.read_text(encoding="utf-8")
            )
        except (OSError, json.JSONDecodeError):
            return None

        if not isinstance(data, dict):
            return None

        return data

    def _load_state(
        self,
        project_dir: Path,
    ) -> dict[str, Any]:
        """Read pipeline state or create a new state object."""

        state_path = project_dir / self.STATE_FILE

        if state_path.exists():
            try:
                data = json.loads(
                    state_path.read_text(encoding="utf-8")
                )

                if isinstance(data, dict):
                    data.setdefault("steps", {})
                    return data

            except (OSError, json.JSONDecodeError):
                console.print(
                    "[yellow]⚠ Invalid pipeline state found; "
                    "creating a new one.[/yellow]"
                )

        return {
            "status": "running",
            "failed_step": None,
            "total_duration_seconds": 0,
            "steps": {},
        }

    def _save_state(
        self,
        project_dir: Path,
        state: dict[str, Any],
    ) -> None:
        """Persist pipeline progress to disk."""

        state_path = project_dir / self.STATE_FILE

        state_path.write_text(
            json.dumps(
                state,
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
