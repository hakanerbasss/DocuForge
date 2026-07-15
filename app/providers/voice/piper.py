import subprocess
from pathlib import Path
from typing import Any

from app.providers.base import VoiceProvider


class PiperVoiceProvider(VoiceProvider):
    """Generate natural local WAV narration using Piper TTS."""

    provider_key = "piper"
    provider_name = "Piper TTS"

    DEFAULT_MODEL = Path(
        "models/piper/tr_TR-fahrettin-medium/"
        "tr_TR-fahrettin-medium.onnx"
    )

    def synthesize(
        self,
        text: str,
        output_path: Path,
        **options: Any,
    ) -> Path:
        cleaned_text = text.strip()

        if not cleaned_text:
            raise ValueError("Text cannot be empty.")

        model_path = Path(
            options.get(
                "model_path",
                self.DEFAULT_MODEL,
            )
        )

        if not model_path.exists():
            raise FileNotFoundError(
                f"Piper model not found: {model_path}"
            )

        config_path = Path(f"{model_path}.json")

        if not config_path.exists():
            raise FileNotFoundError(
                f"Piper model config not found: {config_path}"
            )

        output_path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        length_scale = float(
            options.get("length_scale", 1.0)
        )

        sentence_silence = float(
            options.get("sentence_silence", 0.15)
        )

        volume = float(
            options.get("volume", 1.0)
        )

        command = [
            "piper",
            "--model",
            str(model_path),
            "--config",
            str(config_path),
            "--output_file",
            str(output_path),
            "--length-scale",
            str(length_scale),
            "--sentence-silence",
            str(sentence_silence),
            "--volume",
            str(volume),
        ]

        try:
            subprocess.run(
                command,
                input=cleaned_text,
                check=True,
                capture_output=True,
                text=True,
            )
        except FileNotFoundError as error:
            raise RuntimeError(
                "Piper is not installed or not available in PATH."
            ) from error
        except subprocess.CalledProcessError as error:
            raise RuntimeError(
                f"Piper failed: {error.stderr}"
            ) from error

        if not output_path.exists():
            raise RuntimeError(
                f"Piper output was not created: {output_path}"
            )

        if output_path.stat().st_size == 0:
            raise RuntimeError(
                f"Piper output is empty: {output_path}"
            )

        return output_path
