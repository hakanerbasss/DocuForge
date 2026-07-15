import json
from pathlib import Path
from typing import Any

from app.models.project import DocumentaryProject


class ProjectService:
    """Create and persist DocuForge projects."""

    ROOT = Path("projects")

    def create(
        self,
        project: DocumentaryProject,
    ) -> Path:
        """Create a project directory and project.json file."""

        folder = self._slugify(project.title)
        project_dir = self.ROOT / folder

        project_dir.mkdir(
            parents=True,
            exist_ok=True,
        )

        project_path = project_dir / "project.json"

        project_path.write_text(
            json.dumps(
                project.to_dict(),
                indent=4,
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )

        return project_dir

    def _slugify(self, title: str) -> str:
        """Convert a project title into a safe folder name."""

        replacements = str.maketrans(
            {
                "ı": "i",
                "ğ": "g",
                "ü": "u",
                "ş": "s",
                "ö": "o",
                "ç": "c",
                "İ": "i",
                "Ğ": "g",
                "Ü": "u",
                "Ş": "s",
                "Ö": "o",
                "Ç": "c",
            }
        )

        slug = title.translate(replacements).lower()
        slug = "_".join(slug.split())

        if not slug:
            raise ValueError(
                "Project folder name cannot be empty."
            )

        return slug


def load_project(project_path: str) -> dict[str, Any]:
    """Read project.json from an existing project directory."""

    project_dir = Path(project_path)
    project_file = project_dir / "project.json"

    if not project_file.exists():
        raise FileNotFoundError(
            f"project.json not found: {project_file}"
        )

    try:
        data = json.loads(
            project_file.read_text(encoding="utf-8")
        )
    except json.JSONDecodeError as error:
        raise ValueError(
            f"Invalid project.json: {project_file}: {error}"
        ) from error

    if not isinstance(data, dict):
        raise ValueError(
            f"project.json root must be an object: {project_file}"
        )

    return data
