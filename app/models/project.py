from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from typing import Any


@dataclass
class DocumentaryProject:
    """Metadata for a DocuForge project."""

    title: str
    language: str = "tr"
    template: str = "documentary"
    status: str = "created"
    created_at: str = ""

    def __post_init__(self) -> None:
        self.title = self.title.strip()
        self.language = self.language.strip().lower()
        self.template = self.template.strip().lower()
        self.status = self.status.strip().lower()

        if not self.title:
            raise ValueError("Project title cannot be empty.")

        if not self.language:
            raise ValueError("Project language cannot be empty.")

        if not self.template:
            raise ValueError("Project template cannot be empty.")

        if not self.status:
            raise ValueError("Project status cannot be empty.")

        if not self.created_at:
            self.created_at = datetime.now(timezone.utc).isoformat()

    def to_dict(self) -> dict[str, Any]:
        """Convert project metadata to a serializable dictionary."""

        return asdict(self)
