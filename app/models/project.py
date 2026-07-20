from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from typing import Any, ClassVar


@dataclass
class DocumentaryProject:
    """DocuForge project configuration and metadata."""

    CONTENT_TYPES: ClassVar[set[str]] = {
        "documentary",
        "news",
        "shorts",
        "informational",
    }

    MEDIA_MODES: ClassVar[set[str]] = {
        "video",
        "image",
        "mixed",
    }

    VOICE_PROVIDERS: ClassVar[set[str]] = {
        "supertonic",
        "piper",
        "espeak",
        "local_tts",
        "xtts",
    }

    RESOLUTIONS: ClassVar[dict[str, tuple[int, int]]] = {
        "720p": (1280, 720),
        "1080p": (1920, 1080),
        "vertical": (1080, 1920),
        "4k": (3840, 2160),
    }

    THUMBNAIL_SOURCES: ClassVar[set[str]] = {
        "auto",
        "ai",
        "pexels",
        "scene",
    }

    SCENE_TRANSITIONS: ClassVar[set[str]] = {
        "cut",
        "crossfade",
        "fade_black",
    }

    title: str
    language: str = "tr"
    content_type: str = "documentary"
    target_duration_seconds: int = 600
    media_mode: str = "mixed"

    text_provider: str = "deepseek"
    image_provider: str = "pexels"
    video_provider: str = "pexels"

    voice_provider: str = "supertonic"
    voice_name: str = "M1"
    voice_speed: float = 1.0

    resolution: str = "720p"
    fps: int = 30
    scene_transition: str = "crossfade"

    background_music_enabled: bool = False
    music_track: str = ""
    music_provider: str = "local"
    music_volume: float = 0.18
    subtitles_enabled: bool = False
    subtitles_burn_in: bool = False
    ai_disclosure_enabled: bool = False
    location_map_enabled: bool = False
    thumbnail_enabled: bool = False
    thumbnail_source: str = "auto"
    thumbnail_hook_override: str = ""
    source_material: str = ""
    source_citation: str = ""

    status: str = "created"
    created_at: str = ""

    def __post_init__(self) -> None:
        self.title = str(self.title).strip()
        self.language = str(self.language).strip().lower()
        self.content_type = str(self.content_type).strip().lower()
        self.media_mode = str(self.media_mode).strip().lower()

        self.text_provider = str(self.text_provider).strip().lower()
        self.image_provider = str(self.image_provider).strip().lower()
        self.video_provider = str(self.video_provider).strip().lower()

        self.voice_provider = str(self.voice_provider).strip().lower()
        self.voice_name = str(self.voice_name).strip().upper()

        self.resolution = str(self.resolution).strip().lower()
        self.music_track = str(self.music_track).strip()
        self.thumbnail_source = str(self.thumbnail_source).strip().lower()
        self.scene_transition = str(self.scene_transition).strip().lower()
        self.thumbnail_hook_override = str(
            self.thumbnail_hook_override
        ).strip()
        self.source_material = str(self.source_material).strip()
        self.source_citation = str(self.source_citation).strip()
        self.status = str(self.status).strip().lower()

        self.target_duration_seconds = int(
            self.target_duration_seconds
        )
        self.voice_speed = float(self.voice_speed)
        self.music_volume = float(self.music_volume)
        self.fps = int(self.fps)

        self._validate()

        if not self.created_at:
            self.created_at = datetime.now(
                timezone.utc
            ).isoformat()

    def _validate(self) -> None:
        if not self.title:
            raise ValueError("Project title cannot be empty.")

        if not self.language:
            raise ValueError("Project language cannot be empty.")

        if self.content_type not in self.CONTENT_TYPES:
            raise ValueError(
                f"Invalid content type: {self.content_type}. "
                f"Allowed: {sorted(self.CONTENT_TYPES)}"
            )

        if not 15 <= self.target_duration_seconds <= 14400:
            raise ValueError(
                "Target duration must be between "
                "15 seconds and 4 hours."
            )

        if self.media_mode not in self.MEDIA_MODES:
            raise ValueError(
                f"Invalid media mode: {self.media_mode}. "
                f"Allowed: {sorted(self.MEDIA_MODES)}"
            )

        if not self.text_provider:
            raise ValueError("Text provider cannot be empty.")

        if not self.image_provider:
            raise ValueError("Image provider cannot be empty.")

        if not self.video_provider:
            raise ValueError("Video provider cannot be empty.")

        if self.voice_provider not in self.VOICE_PROVIDERS:
            raise ValueError(
                f"Invalid voice provider: {self.voice_provider}. "
                f"Allowed: {sorted(self.VOICE_PROVIDERS)}"
            )

        if not self.voice_name:
            raise ValueError("Voice name cannot be empty.")

        if not 0.5 <= self.voice_speed <= 2.0:
            raise ValueError(
                "Voice speed must be between 0.5 and 2.0."
            )

        if not 0.0 <= self.music_volume <= 1.0:
            raise ValueError(
                "Music volume must be between 0.0 and 1.0."
            )

        if self.resolution not in self.RESOLUTIONS:
            raise ValueError(
                f"Invalid resolution: {self.resolution}. "
                f"Allowed: {sorted(self.RESOLUTIONS)}"
            )

        if not 15 <= self.fps <= 60:
            raise ValueError("FPS must be between 15 and 60.")

        if self.thumbnail_source not in self.THUMBNAIL_SOURCES:
            raise ValueError(
                f"Invalid thumbnail source: {self.thumbnail_source}. "
                f"Allowed: {sorted(self.THUMBNAIL_SOURCES)}"
            )

        if self.scene_transition not in self.SCENE_TRANSITIONS:
            raise ValueError(
                f"Invalid scene transition: {self.scene_transition}. "
                f"Allowed: {sorted(self.SCENE_TRANSITIONS)}"
            )

        if not self.status:
            raise ValueError("Project status cannot be empty.")

    @property
    def width(self) -> int:
        return self.RESOLUTIONS[self.resolution][0]

    @property
    def height(self) -> int:
        return self.RESOLUTIONS[self.resolution][1]

    @property
    def template(self) -> str:
        """
        Backward-compatible alias.

        The application uses content_type as the single source
        of truth. Older code reading project.template still works.
        """
        return self.content_type

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)

        # Keep legacy readers working while content_type remains
        # the only authoritative setting.
        data["template"] = self.content_type
        data["width"] = self.width
        data["height"] = self.height

        return data

    @classmethod
    def from_dict(
        cls,
        data: dict[str, Any],
    ) -> "DocumentaryProject":
        """Load both current and legacy project.json formats."""

        raw_content_type = data.get(
            "content_type",
            data.get("template", "documentary"),
        )

        raw_duration = data.get(
            "target_duration_seconds",
            data.get("duration", 600),
        )

        raw_resolution = str(
            data.get("resolution", "720p")
        ).strip().lower()

        # Compatibility with older vertical project names.
        if raw_resolution == "shorts":
            raw_resolution = "vertical"

        return cls(
            title=str(data.get("title", "")),
            language=str(data.get("language", "tr")),
            content_type=str(raw_content_type),
            target_duration_seconds=int(raw_duration),
            media_mode=str(
                data.get("media_mode", "mixed")
            ),
            text_provider=str(
                data.get("text_provider", "deepseek")
            ),
            image_provider=str(
                data.get("image_provider", "pexels")
            ),
            video_provider=str(
                data.get("video_provider", "pexels")
            ),
            voice_provider=str(
                data.get("voice_provider", "supertonic")
            ),
            voice_name=str(
                data.get("voice_name", "M1")
            ),
            voice_speed=float(
                data.get("voice_speed", 1.0)
            ),
            resolution=raw_resolution,
            fps=int(data.get("fps", 30)),
            scene_transition=str(
                data.get("scene_transition", "crossfade")
            ),
            background_music_enabled=bool(
                data.get(
                    "background_music_enabled",
                    False,
                )
            ),
            music_track=str(
                data.get("music_track", "")
            ),
            music_provider=str(
                data.get("music_provider", "local")
            ),
            music_volume=float(
                data.get("music_volume", 0.18)
            ),
            subtitles_enabled=bool(
                data.get("subtitles_enabled", False)
            ),
            subtitles_burn_in=bool(
                data.get("subtitles_burn_in", False)
            ),
            ai_disclosure_enabled=bool(
                data.get("ai_disclosure_enabled", False)
            ),
            location_map_enabled=bool(
                data.get("location_map_enabled", False)
            ),
            thumbnail_enabled=bool(
                data.get("thumbnail_enabled", False)
            ),
            thumbnail_source=str(
                data.get("thumbnail_source", "auto")
            ),
            thumbnail_hook_override=str(
                data.get("thumbnail_hook_override", "")
            ),
            source_material=str(
                data.get("source_material", "")
            ),
            source_citation=str(
                data.get("source_citation", "")
            ),
            status=str(data.get("status", "created")),
            created_at=str(data.get("created_at", "")),
        )
