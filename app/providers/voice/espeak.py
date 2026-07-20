import subprocess
from pathlib import Path
from typing import Any

from app.providers.base import VoiceProvider
from app.utils.audio_cleanup import apply_loudness_normalization


class EspeakVoiceProvider(VoiceProvider):
    """Generate local WAV narration using eSpeak NG."""

    provider_key = "espeak"
    provider_name = "eSpeak NG"

    # eSpeak-ng's own default rate, in words-per-minute -- the baseline
    # the 0.5-2.0 "speed" multiplier (shared across every voice provider,
    # see VoiceService.generate()'s `speed` param and DocumentaryProject.
    # voice_speed) scales against.
    BASE_WPM = 175
    MIN_WPM = 80
    MAX_WPM = 400

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

        # `speed` arrives as the same 0.5-2.0 multiplier every other voice
        # provider uses (1.0 = normal) -- NOT a words-per-minute value.
        # Passing it straight through as eSpeak's `-s` flag (as this used
        # to do, with speed=1.0 becoming `-s 1`, i.e. "1 word per minute")
        # produced garbled near-silent output that still passed the
        # size/duration checks below, so it looked like a fast success
        # instead of the broken result it actually was.
        speed_multiplier = self._normalize_speed(
            options.get("speed", 1.0)
        )
        speed = int(round(self.BASE_WPM * speed_multiplier))
        speed = max(self.MIN_WPM, min(speed, self.MAX_WPM))

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

        # eSpeak-ng's raw output can sound crackly/harsh at its default
        # level -- see apply_loudness_normalization()'s docstring. Runs
        # after the file is already confirmed valid, and never fails the
        # synthesis if the cleanup pass itself has a problem.
        apply_loudness_normalization(output_path)

        return output_path

    def _normalize_speed(self, value: Any) -> float:
        try:
            speed = float(value)
        except (TypeError, ValueError):
            return 1.0

        if speed <= 0:
            return 1.0

        return speed
