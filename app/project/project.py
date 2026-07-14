from dataclasses import dataclass
from pathlib import Path
import json
import re


@dataclass
class DocumentaryProject:
    title: str
    language: str = "tr"
    duration: int = 12
    style: str = "cinematic"

    def slug(self) -> str:
        slug = self.title.lower()
        slug = re.sub(r"[^a-zA-Z0-9çğıöşüÇĞİÖŞÜ ]", "", slug)
        slug = slug.replace(" ", "_")
        return slug

    def create(self) -> Path:
        project_dir = Path("projects") / self.slug()

        project_dir.mkdir(parents=True, exist_ok=True)

        data = {
            "title": self.title,
            "language": self.language,
            "duration": self.duration,
            "style": self.style,
        }

        with open(project_dir / "project.json", "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=4)

        return project_dir
