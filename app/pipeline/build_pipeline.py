import json
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any

from rich.console import Console

from app.agents.registry import AgentRegistry
from app.models.project import DocumentaryProject
from app.pipeline.definitions import (
    get_agent_definition,
    get_default_pipeline_steps,
)
from app.services.media_builder import MediaBuilder
from app.services.narration_builder import NarrationBuilder
from app.services.project_service import ProjectService, load_project
from app.services.render_service import RenderService
from app.services.voice_service import VoiceService


console = Console()


class BuildPipeline:
    """Run and resume the complete DocuForge production pipeline."""

    STATE_FILE = "pipeline_state.json"

    def run(
        self,
        topic: str,
        language: str = "tr",
        template: str = "documentary",
    ) -> Path:
        """Create a new project and run all pipeline stages."""

        console.print("[bold]📂 Creating project...[/bold]")

        project = DocumentaryProject(
            title=topic,
            language=language,
            template=template,
        )

        project_service = ProjectService()
        project_dir = project_service.create(project)

        console.print("[bold green]✅ Project created[/bold green]\n")

        return self._run_pipeline(project_dir)

    def resume(self, project_path: str) -> Path:
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

        return self._run_pipeline(project_dir)

    def _run_pipeline(self, project_dir: Path) -> Path:
        """Run AI-agent and production-service stages in order."""

        project_data = load_project(str(project_dir))
        state = self._load_state(project_dir)
        total_start = time.perf_counter()

        agent_steps = get_default_pipeline_steps()

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
                    str(project_dir)
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

        total_steps = len(agent_steps) + len(service_steps)

        for index, step in enumerate(agent_steps, start=1):
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

            if step.key in {
                "research",
                "script",
                "storyboard",
            }:
                result = agent.run(
                    agent_input,
                    language=language,
                )
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
        """Validate the final rendered video."""

        output_path = (
            project_dir
            / "render"
            / "final_video.mp4"
        )

        return (
            output_path.exists()
            and output_path.stat().st_size > 0
        )

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
