from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class DocumentaryProject:

    title: str
    language: str = "tr"
    duration: int = 12
    style: str = "cinematic"

    status: str = "created"

    created_at: str = field(
        default_factory=lambda: datetime.utcnow().isoformat()
    )
