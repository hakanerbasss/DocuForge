import json
import time
from pathlib import Path

from rich.console import Console

from app.agents.registry import AgentRegistry
from app.models.project import DocumentaryProject
from app.pipeline.definitions import (
    get_agent_definition,
    get_default_pipeline_steps,
)
from app.services.project_service import ProjectService, load_project


console = Console()


class BuildPipeline:
    """Run and resume the documentary production pipeline."""

    STATE_FILE = "pipeline_state.json"

    def run(self, topic: str) -> Path:
        """Create a project and run all pipeline stages."""

        console.print("[bold]📂 Creating project...[/bold]")

        project = DocumentaryProject(title=topic)
        project_service = ProjectService()
        project_dir = project_service.create(project)

        console.print("[bold green]✅ Project created[/bold green]\n")

        return self._run_pipeline(project_dir)

    def resume(self, project_path: str) -> Path:
        """Resume an existing project from its first incomplete stage."""

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
            f"[bold cyan]▶ Resuming project:[/bold cyan] {project_dir}\n"
        )

        return self._run_pipeline(project_dir)

    def _run_pipeline(self, project_dir: Path) -> Path:
        """Run incomplete registered pipeline stages in order."""

        project_data = load_project(str(project_dir))
        total_start = time.perf_counter()
        state = self._load_state(project_dir)

        steps = get_default_pipeline_steps()
        total_steps = len(steps)

        for index, step in enumerate(steps, start=1):
            definition = get_agent_definition(step.key)
            output_path = project_dir / definition.output_file

            if self._is_step_complete(
                state=state,
                step_key=step.key,
                output_path=output_path,
            ):
                console.print(
                    f"[dim][{index}/{total_steps}] "
                    f"{definition.icon} {definition.name} "
                    "already completed — skipped[/dim]\n"
                )
                continue

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
                result = agent.run(agent_input)

                output_path.write_text(
                    result,
                    encoding="utf-8",
                )

                elapsed = time.perf_counter() - step_start

                state["steps"][step.key] = {
                    "status": "completed",
                    "duration_seconds": round(elapsed, 2),
                    "output": str(output_path),
                    "error": None,
                }

                state["status"] = "running"
                state["failed_step"] = None

                self._save_state(project_dir, state)

                console.print(
                    f"[bold green]✅ {definition.name} "
                    "completed[/bold green]"
                )
                console.print(
                    f"[cyan]⏱ Step time: "
                    f"{elapsed:.2f} seconds[/cyan]\n"
                )

            except Exception as error:
                elapsed = time.perf_counter() - step_start

                state["steps"][step.key] = {
                    "status": "failed",
                    "duration_seconds": round(elapsed, 2),
                    "output": str(output_path),
                    "error": str(error),
                }

                state["status"] = "failed"
                state["failed_step"] = step.key

                self._save_state(project_dir, state)

                console.print(
                    f"\n[bold red]❌ {definition.name} "
                    "Agent failed[/bold red]"
                )
                console.print(f"[red]Error: {error}[/red]")

                console.print(
                    "\n[yellow]Run the resume command after fixing "
                    "the problem:[/yellow]"
                )
                console.print(
                    f"[bold]docuforge resume {project_dir}[/bold]"
                )

                raise RuntimeError(
                    f"{definition.name} Agent failed: {error}"
                ) from error

        total_elapsed = time.perf_counter() - total_start

        state["status"] = "completed"
        state["failed_step"] = None
        state["total_duration_seconds"] = round(total_elapsed, 2)

        self._save_state(project_dir, state)

        console.print(
            "[bold green]🎉 All pipeline stages completed[/bold green]"
        )

        return project_dir

    def _load_state(self, project_dir: Path) -> dict:
        """Read pipeline state or create a new state object."""

        state_path = project_dir / self.STATE_FILE

        if state_path.exists():
            try:
                return json.loads(
                    state_path.read_text(encoding="utf-8")
                )
            except json.JSONDecodeError:
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
        state: dict,
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

    def _is_step_complete(
        self,
        state: dict,
        step_key: str,
        output_path: Path,
    ) -> bool:
        """Check state data and output file validity."""

        step_state = state.get("steps", {}).get(step_key, {})

        return (
            step_state.get("status") == "completed"
            and output_path.exists()
            and output_path.stat().st_size > 0
        )
