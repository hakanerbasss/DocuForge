from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any


class BaseProvider(ABC):
    """Common base class for every DocuForge provider."""

    provider_key: str
    provider_name: str

    def __init__(self) -> None:
        if not getattr(self, "provider_key", "").strip():
            raise ValueError(
                f"{self.__class__.__name__} must define provider_key."
            )

        if not getattr(self, "provider_name", "").strip():
            raise ValueError(
                f"{self.__class__.__name__} must define provider_name."
            )


class TextProvider(BaseProvider):
    """Generate text using a local model or cloud API."""

    @abstractmethod
    def generate(self, prompt: str) -> str:
        """Generate text from a prompt."""
        raise NotImplementedError


class ImageProvider(BaseProvider):
    """Search for, download or generate images."""

    @abstractmethod
    def get_images(
        self,
        query: str,
        output_dir: Path,
        limit: int = 1,
        **options: Any,
    ) -> list[Path]:
        """Return local paths for acquired images."""
        raise NotImplementedError


class VideoProvider(BaseProvider):
    """Search for, download or generate video clips."""

    @abstractmethod
    def get_videos(
        self,
        query: str,
        output_dir: Path,
        limit: int = 1,
        **options: Any,
    ) -> list[Path]:
        """Return local paths for acquired videos."""
        raise NotImplementedError


class VoiceProvider(BaseProvider):
    """Generate narration audio."""

    @abstractmethod
    def synthesize(
        self,
        text: str,
        output_path: Path,
        **options: Any,
    ) -> Path:
        """Create an audio file and return its local path."""
        raise NotImplementedError


class RenderProvider(BaseProvider):
    """Render a DocuForge project into a final video."""

    @abstractmethod
    def render(
        self,
        project_dir: Path,
        output_path: Path,
        **options: Any,
    ) -> Path:
        """Render the project and return the final video path."""
        raise NotImplementedError
