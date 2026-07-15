import subprocess
from pathlib import Path
from typing import Any

from app.providers.base import VoiceProvider


class EspeakVoiceProvider(VoiceProvider):
    """Generate local WAV narration using eSpeak NG."""

    provider_key = "espeak"
    provider_name = "eSpeak NG"

    def synthesize(
        self,
        text: str,
        output_path: Path,
        **options: Any,
    ) -> Path:
        cleaned_text = text.strip()

        if not cleaned_text:
            raise ValueError("Text cannot be empty.")

        output_path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        language = str(
            options.get("language", "tr")
        ).strip()

        voice = str(
            options.get("voice", language)
        ).strip()

        speed = int(options.get("speed", 150))
        pitch = int(options.get("pitch", 50))
        amplitude = int(options.get("amplitude", 100))

        command = [
            "espeak-ng",
            "-v",
            voice,
            "-s",
            str(speed),
            "-p",
            str(pitch),
            "-a",
            str(amplitude),
            "-w",
            str(output_path),
            cleaned_text,
        ]

        try:
            subprocess.run(
                command,
                check=True,
                capture_output=True,
                text=True,
            )
        except FileNotFoundError as error:
            raise RuntimeError(
                "eSpeak NG is not installed or not available in PATH."
            ) from error
        except subprocess.CalledProcessError as error:
            raise RuntimeError(
                f"eSpeak NG failed: {error.stderr}"
            ) from error

        if not output_path.exists():
            raise RuntimeError(
                f"Voice output was not created: {output_path}"
            )

        if output_path.stat().st_size == 0:
            raise RuntimeError(
                f"Voice output is empty: {output_path}"
            )

        return output_path
