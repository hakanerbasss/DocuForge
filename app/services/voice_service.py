import json
import subprocess
from pathlib import Path
from typing import Any

from app.core.config import settings
from app.providers.defaults import register_default_providers
from app.providers.registry import ProviderRegistry
from app.providers.base import VoiceProvider


class VoiceService:
    """Generate scene-based narration audio using a configured provider."""

    def generate(
        self,
        project_path: str,
        *,
        provider_key: str | None = None,
        speed: int = 145,
    ) -> Path:
        project_dir = Path(project_path)
        audio_dir = project_dir / "audio"
        manifest_path = audio_dir / "manifest.json"
        project_json_path = project_dir / "project.json"

        if not manifest_path.exists():
            raise FileNotFoundError(
                f"Audio manifest not found: {manifest_path}"
            )

        manifest = self._load_json(manifest_path)
        project_data = self._load_json(project_json_path)

        language = str(
            project_data.get("language", "tr")
        ).strip().lower()

        selected_provider = (
            provider_key
            or getattr(settings, "voice_provider", "espeak")
        ).strip().lower()

        register_default_providers()

        provider = ProviderRegistry.create(
            category="voice",
            key=selected_provider,
        )

        if not isinstance(provider, VoiceProvider):
            raise TypeError(
                f"Configured provider is not a VoiceProvider: "
                f"{selected_provider}"
            )

        scenes = manifest.get("scenes")

        if not isinstance(scenes, list) or not scenes:
            raise ValueError(
                "Audio manifest must contain a non-empty scenes list."
            )

        for index, scene in enumerate(scenes, start=1):
            if not isinstance(scene, dict):
                raise ValueError(
                    f"Audio manifest scene {index} is invalid."
                )

            text_path = Path(scene["text_file"])
            audio_path = Path(scene["audio_file"])

            if not text_path.exists():
                raise FileNotFoundError(
                    f"Narration text not found: {text_path}"
                )

            text = text_path.read_text(
                encoding="utf-8"
            ).strip()

            if not text:
                raise ValueError(
                    f"Narration text is empty: {text_path}"
                )

            print(
                f"[{index}/{len(scenes)}] "
                f"Generating {audio_path.name}..."
            )

            provider.synthesize(
                text,
                audio_path,
                language=language,
                voice=language,
                speed=speed,
            )

            audio_duration = self._probe_duration(
                audio_path
            )

            scene["audio_duration"] = round(
                audio_duration,
                3,
            )
            scene["voice_provider"] = selected_provider
            scene["status"] = "audio_ready"

            print(
                f"  ✅ {audio_path} "
                f"({audio_duration:.2f} s)"
            )

            self._save_json(
                manifest_path,
                manifest,
            )

        manifest["voice_provider"] = selected_provider
        manifest["language"] = language
        manifest["completed_count"] = sum(
            scene.get("status") == "audio_ready"
            for scene in scenes
        )

        self._save_json(
            manifest_path,
            manifest,
        )

        return manifest_path

    def _probe_duration(
        self,
        audio_path: Path,
    ) -> float:
        command = [
            "ffprobe",
            "-v",
            "error",
            "-show_entries",
            "format=duration",
            "-of",
            "default=noprint_wrappers=1:nokey=1",
            str(audio_path),
        ]

        try:
            result = subprocess.run(
                command,
                check=True,
                capture_output=True,
                text=True,
            )
        except FileNotFoundError as error:
            raise RuntimeError(
                "ffprobe is not installed or not available in PATH."
            ) from error
        except subprocess.CalledProcessError as error:
            raise RuntimeError(
                f"ffprobe failed: {error.stderr}"
            ) from error

        try:
            duration = float(result.stdout.strip())
        except ValueError as error:
            raise RuntimeError(
                f"Invalid audio duration for {audio_path}: "
                f"{result.stdout}"
            ) from error

        if duration <= 0:
            raise RuntimeError(
                f"Audio duration must be greater than zero: "
                f"{audio_path}"
            )

        return duration

    def _load_json(
        self,
        path: Path,
    ) -> dict[str, Any]:
        if not path.exists():
            raise FileNotFoundError(
                f"JSON file not found: {path}"
            )

        try:
            data = json.loads(
                path.read_text(encoding="utf-8")
            )
        except json.JSONDecodeError as error:
            raise ValueError(
                f"Invalid JSON file: {path}: {error}"
            ) from error

        if not isinstance(data, dict):
            raise ValueError(
                f"JSON root must be an object: {path}"
            )

        return data

    def _save_json(
        self,
        path: Path,
        data: dict[str, Any],
    ) -> None:
        path.write_text(
            json.dumps(
                data,
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
