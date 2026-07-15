from pathlib import Path


class MediaCache:
    """Shared media cache."""

    def __init__(self, root: Path):
        self.root = root

    def exists(self, filename: str) -> bool:
        return (self.root / filename).exists()

    def path(self, filename: str) -> Path:
        self.root.mkdir(parents=True, exist_ok=True)
        return self.root / filename
