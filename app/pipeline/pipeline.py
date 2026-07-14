from pathlib import Path

from app.models.project import DocumentaryProject
from app.services.project_service import ProjectService


class Pipeline:

    def __init__(self):
        self.project_service = ProjectService()

    def generate(self, topic: str) -> Path:

        project = DocumentaryProject(title=topic)

        project_dir = self.project_service.create(project)

        files = [
            "research.md",
            "script.md",
            "storyboard.json",
            "image_prompts.json",
            "video_prompts.json",
            "narration.txt",
            "thumbnail_prompt.txt",
        ]

        for file in files:
            (project_dir / file).touch(exist_ok=True)

        youtube = project_dir / "youtube"
        youtube.mkdir(exist_ok=True)

        for file in (
            "title.txt",
            "description.txt",
            "tags.txt",
        ):
            (youtube / file).touch(exist_ok=True)

        return project_dir
