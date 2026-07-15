from dataclasses import asdict, dataclass
from typing import Any, Literal


MediaType = Literal["image", "video"]


@dataclass(frozen=True)
class MediaAsset:
    """A media item discovered by an image or video provider."""

    asset_id: str
    provider: str
    media_type: MediaType
    download_url: str

    width: int | None = None
    height: int | None = None
    duration: float | None = None

    page_url: str | None = None
    preview_url: str | None = None

    author: str | None = None
    license_name: str | None = None
    query: str | None = None

    metadata: dict[str, Any] | None = None

    def __post_init__(self) -> None:
        if not self.asset_id.strip():
            raise ValueError("asset_id cannot be empty.")

        if not self.provider.strip():
            raise ValueError("provider cannot be empty.")

        if self.media_type not in {"image", "video"}:
            raise ValueError(
                "media_type must be either 'image' or 'video'."
            )

        if not self.download_url.strip():
            raise ValueError("download_url cannot be empty.")

        if self.width is not None and self.width <= 0:
            raise ValueError("width must be greater than zero.")

        if self.height is not None and self.height <= 0:
            raise ValueError("height must be greater than zero.")

        if self.duration is not None and self.duration <= 0:
            raise ValueError("duration must be greater than zero.")

    @property
    def aspect_ratio(self) -> float | None:
        """Return width divided by height when dimensions are available."""

        if self.width is None or self.height is None:
            return None

        return self.width / self.height

    @property
    def is_landscape(self) -> bool:
        """Return whether the media is wider than it is tall."""

        ratio = self.aspect_ratio
        return ratio is not None and ratio > 1

    @property
    def is_portrait(self) -> bool:
        """Return whether the media is taller than it is wide."""

        ratio = self.aspect_ratio
        return ratio is not None and ratio < 1

    def to_dict(self) -> dict[str, Any]:
        """Convert the media asset into a JSON-serializable dictionary."""

        return asdict(self)
