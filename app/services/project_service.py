import json
import re
from pathlib import Path
from typing import Any

from app.models.project import DocumentaryProject


class ProjectService:
    """Create, load and persist DocuForge projects."""

    ROOT = Path("projects")

    def create(
        self,
        project: DocumentaryProject,
    ) -> Path:
        slug = self.resolve_unique_slug(project.title)
        project_dir = self.ROOT / slug

        project_dir.mkdir(
            parents=True,
            exist_ok=True,
        )

        self.save(
            project_dir,
            project,
        )

        return project_dir

    def resolve_unique_slug(
        self,
        title: str,
    ) -> str:
        """Return a project.json-free slug, appending _2, _3, ... on collision."""

        base_slug = self._slugify(title)
        candidate = base_slug
        suffix = 2

        while (self.ROOT / candidate / "project.json").exists():
            candidate = f"{base_slug}_{suffix}"
            suffix += 1

        return candidate

    def save(
        self,
        project_dir: Path,
        project: DocumentaryProject,
    ) -> Path:
        project_dir.mkdir(
            parents=True,
            exist_ok=True,
        )

        project_file = project_dir / "project.json"

        project_file.write_text(
            json.dumps(
                project.to_dict(),
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )

        return project_file

    def load(
        self,
        project_path: str | Path,
    ) -> DocumentaryProject:
        project_dir = Path(project_path)
        data = load_project(project_dir)

        return DocumentaryProject.from_dict(data)

    def _slugify(
        self,
        title: str,
    ) -> str:
        translations = str.maketrans(
            {
                "ı": "i",
                "İ": "i",
                "ğ": "g",
                "Ğ": "g",
                "ü": "u",
                "Ü": "u",
                "ş": "s",
                "Ş": "s",
                "ö": "o",
                "Ö": "o",
                "ç": "c",
                "Ç": "c",
            }
        )

        slug = title.translate(translations).lower()
        slug = re.sub(r"[^a-z0-9]+", "_", slug)
        slug = slug.strip("_")

        if not slug:
            raise ValueError(
                "Project folder name cannot be empty."
            )

        return slug


def load_project(
    project_path: str | Path,
) -> dict[str, Any]:
    project_dir = Path(project_path)
    project_file = project_dir / "project.json"

    if not project_file.exists():
        raise FileNotFoundError(
            f"project.json not found: {project_file}"
        )

    try:
        data = json.loads(
            project_file.read_text(
                encoding="utf-8",
            )
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
