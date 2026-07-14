from pathlib import Path

from app.project.project import DocumentaryProject


def generate(topic: str) -> Path:
    project = DocumentaryProject(title=topic)
    project_dir = project.create()

    files = [
        "research.md",
        "script.md",
        "storyboard.json",
        "image_prompts.json",
        "video_prompts.json",
        "narration.txt",
        "thumbnail_prompt.txt",
    ]

    for filename in files:
        (project_dir / filename).touch(exist_ok=True)

    youtube_dir = project_dir / "youtube"
    youtube_dir.mkdir(exist_ok=True)

    for filename in ["title.txt", "description.txt", "tags.txt"]:
        (youtube_dir / filename).touch(exist_ok=True)

    return project_dir
