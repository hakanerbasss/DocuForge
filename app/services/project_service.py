import json
from pathlib import Path

from app.models.project import DocumentaryProject


class ProjectService:

    ROOT = Path("projects")

    def create(self, project: DocumentaryProject):

        folder = project.title.lower()

        folder = (
            folder
            .replace(" ", "_")
            .replace("ı", "i")
            .replace("ğ", "g")
            .replace("ü", "u")
            .replace("ş", "s")
            .replace("ö", "o")
            .replace("ç", "c")
        )

        project_dir = self.ROOT / folder
        project_dir.mkdir(parents=True, exist_ok=True)

        data = {
            "title": project.title,
            "language": project.language,
            "duration": project.duration,
            "style": project.style,
            "status": project.status,
            "created_at": project.created_at,
        }

        with open(project_dir / "project.json", "w", encoding="utf-8") as f:
            json.dump(data, f, indent=4, ensure_ascii=False)

        return project_dir

import json
from pathlib import Path


def load_project(project_path: str) -> dict:
    project_dir = Path(project_path)

    with open(project_dir / "project.json", "r", encoding="utf-8") as f:
        return json.load(f)
