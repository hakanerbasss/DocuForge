from pathlib import Path
from typing import Any

from app.providers.base import VoiceProvider


class SupertonicVoiceProvider(VoiceProvider):
    """Generate local narration using the Supertonic Python SDK."""

    provider_key = "supertonic"
    provider_name = "Supertonic"

    VALID_VOICES = {
        "M1",
        "M2",
        "M3",
        "M4",
        "M5",
        "F1",
        "F2",
        "F3",
        "F4",
        "F5",
    }

    _tts = None

    def synthesize(
        self,
        text: str,
        output_path: Path,
        **options: Any,
    ) -> Path:
        cleaned_text = text.strip()

        if not cleaned_text:
            raise ValueError("Text cannot be empty.")

        language = str(
            options.get("language", "tr")
        ).strip().lower()

        voice = str(
            options.get(
                "voice_name",
                options.get("voice", "M1"),
            )
        ).strip().upper()

        # VoiceService eski davranış nedeniyle voice="tr"
        # gönderebilir. Bu durumda varsayılan ses kullanılır.
        if voice not in self.VALID_VOICES:
            voice = "M1"

        speed = self._normalize_speed(
            options.get("speed", 1.0)
        )

        total_steps = int(
            options.get("total_steps", 8)
        )

        if total_steps < 1:
            raise ValueError(
                "total_steps must be greater than zero."
            )

        output_path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        tts = self._get_tts()
        voice_style = tts.get_voice_style(
            voice_name=voice
        )

        wav, _duration = tts.synthesize(
            cleaned_text,
            lang=language,
            voice_style=voice_style,
            total_steps=total_steps,
            speed=speed,
        )

        tts.save_audio(
            wav,
            str(output_path),
        )

        if (
            not output_path.exists()
            or output_path.stat().st_size == 0
        ):
            raise RuntimeError(
                f"Supertonic output was not created: "
                f"{output_path}"
            )

        return output_path

    @classmethod
    def _get_tts(cls):
        """Load the model once and reuse it."""

        if cls._tts is None:
            try:
                from supertonic import TTS
            except ImportError as error:
                raise RuntimeError(
                    "Supertonic is not installed. Run: "
                    "docuforge setup-voice supertonic"
                ) from error

            cls._tts = TTS(
                auto_download=True
            )

        return cls._tts

    def _normalize_speed(
        self,
        value: Any,
    ) -> float:
        """Normalize provider-specific speed values."""

        try:
            speed = float(value)
        except (TypeError, ValueError):
            return 1.0

        # eSpeak CLI'daki 145 gibi değerler Supertonic
        # için geçerli değildir.
        if speed > 5:
            return 1.0

        if speed <= 0:
            return 1.0

        return speed
