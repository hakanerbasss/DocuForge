from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from app.agents.defaults import register_default_agents
from app.agents.registry import AgentRegistry


@dataclass(frozen=True)
class PipelineStep:
    """Defines one stage of the DocuForge build pipeline."""

    key: str
    input_loader: Callable[[Path, dict], str]


def _load_project_title(
    project_dir: Path,
    project_data: dict,
) -> str:
    return project_data["title"]


def _load_research(
    project_dir: Path,
    project_data: dict,
) -> str:
    return _read_required_file(project_dir / "research.md")


def _load_script(
    project_dir: Path,
    project_data: dict,
) -> str:
    return _read_required_file(project_dir / "script.md")


def _load_storyboard(
    project_dir: Path,
    project_data: dict,
) -> str:
    return _read_required_file(project_dir / "storyboard.json")


def get_default_pipeline_steps() -> list[PipelineStep]:
    """Return the built-in documentary pipeline order."""

    register_default_agents()

    return [
        PipelineStep(
            key="research",
            input_loader=_load_project_title,
        ),
        PipelineStep(
            key="script",
            input_loader=_load_research,
        ),
        PipelineStep(
            key="storyboard",
            input_loader=_load_script,
        ),
        PipelineStep(
            key="images",
            input_loader=_load_storyboard,
        ),
        PipelineStep(
            key="videos",
            input_loader=_load_storyboard,
        ),
        PipelineStep(
            key="narration",
            input_loader=_load_storyboard,
        ),
        PipelineStep(
            key="seo",
            input_loader=_load_script,
        ),
    ]


def get_agent_definition(key: str):
    """Return metadata and factory for a registered agent."""

    register_default_agents()
    return AgentRegistry.get(key)


def _read_required_file(file_path: Path) -> str:
    if not file_path.exists():
        raise FileNotFoundError(
            f"Required file not found: {file_path}"
        )

    content = file_path.read_text(encoding="utf-8").strip()

    if not content:
        raise ValueError(
            f"Required file is empty: {file_path}"
        )

    return content
