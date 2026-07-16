import os
import re
import threading
from pathlib import Path
from typing import Any

from app.core.config import settings
from app.providers.base import VoiceProvider


class XTTSVoiceProvider(VoiceProvider):
    """Clone-voice TTS via Coqui XTTS-v2.

    Ports the approach already running in production in the Instagram
    bot (hakanerbasss.github.io, supertonic-web/xtts_clone.py): same
    model, same sentence-chunking (XTTS has a ~400 token limit per
    call), same reference-audio cloning via speaker_wav.
    """

    provider_key = "xtts"
    provider_name = "XTTS Voice Clone"

    MODEL_NAME = "tts_models/multilingual/multi-dataset/xtts_v2"
    SAMPLE_RATE = 24000
    REFERENCE_AUDIO_ENV = "XTTS_REFERENCE_AUDIO"
    DEFAULT_REFERENCE_PATH = Path("models/xtts/reference.wav")

    _tts = None
    _lock = threading.Lock()

    def synthesize(
        self,
        text: str,
        output_path: Path,
        **options: Any,
    ) -> Path:
        os.environ.setdefault("COQUI_TOS_AGREED", "1")

        cleaned_text = text.strip()

        if not cleaned_text:
            raise ValueError("Text cannot be empty.")

        language = str(
            options.get("language", "tr")
        ).strip().lower()

        speed = self._normalize_speed(
            options.get("speed", 1.0)
        )

        reference_audio = self._resolve_reference_audio(
            options.get("reference_audio")
        )

        output_path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        tts = self._get_model()
        chunks = self._chunk_text(cleaned_text)

        import numpy as np

        wavs = []

        for chunk in chunks:
            wav = tts.tts(
                text=chunk,
                speaker_wav=str(reference_audio),
                language=language,
                speed=speed,
            )
            wavs.append(np.array(wav, dtype=np.float32))

        combined = (
            np.concatenate(wavs)
            if len(wavs) > 1
            else wavs[0]
        )

        import scipy.io.wavfile as wavfile

        wavfile.write(
            str(output_path),
            self.SAMPLE_RATE,
            combined,
        )

        if (
            not output_path.exists()
            or output_path.stat().st_size == 0
        ):
            raise RuntimeError(
                f"XTTS output was not created: {output_path}"
            )

        return output_path

    def _resolve_reference_audio(
        self,
        explicit: str | None,
    ) -> Path:
        if explicit:
            candidate = Path(explicit)

            if candidate.exists():
                return candidate

            raise FileNotFoundError(
                f"XTTS reference audio not found: {candidate}"
            )

        configured_value = settings.xtts_reference_audio.strip()

        if configured_value:
            candidate = Path(configured_value)

            if candidate.exists():
                return candidate

            raise FileNotFoundError(
                f"XTTS reference audio not found "
                f"(from {self.REFERENCE_AUDIO_ENV} or /settings): {candidate}"
            )

        if self.DEFAULT_REFERENCE_PATH.exists():
            return self.DEFAULT_REFERENCE_PATH

        raise FileNotFoundError(
            "No XTTS reference audio configured. Set the "
            f"{self.REFERENCE_AUDIO_ENV} environment variable, or place "
            f"a WAV file at {self.DEFAULT_REFERENCE_PATH}."
        )

    @classmethod
    def _get_model(cls):
        """Load the model once and reuse it (thread-safe, double-checked)."""

        if cls._tts is None:
            with cls._lock:
                if cls._tts is None:
                    try:
                        from TTS.api import TTS
                    except ImportError as error:
                        raise RuntimeError(
                            "Coqui TTS is not installed. Run: "
                            "pip install coqui-tts torch torchaudio"
                        ) from error

                    import torch

                    device = (
                        "cuda"
                        if torch.cuda.is_available()
                        else "cpu"
                    )

                    cls._tts = TTS(cls.MODEL_NAME).to(device)

        return cls._tts

    def _chunk_text(
        self,
        text: str,
        max_chars: int = 220,
    ) -> list[str]:
        """Split into sentence-sized chunks to stay under XTTS's token limit."""

        sentences = re.split(r"(?<=[.!?])\s+", text.strip())
        chunks: list[str] = []
        current = ""

        for sentence in sentences:
            candidate = f"{current} {sentence}".strip()

            if len(candidate) <= max_chars:
                current = candidate
                continue

            if current:
                chunks.append(current)

            if len(sentence) > max_chars:
                parts = re.split(r"(?<=,)\s+", sentence)
                buffer = ""

                for part in parts:
                    part_candidate = f"{buffer} {part}".strip()

                    if len(part_candidate) <= max_chars:
                        buffer = part_candidate
                    else:
                        if buffer:
                            chunks.append(buffer)
                        buffer = part

                current = buffer
            else:
                current = sentence

        if current:
            chunks.append(current)

        return chunks or [text]

    def _normalize_speed(self, value: Any) -> float:
        try:
            speed = float(value)
        except (TypeError, ValueError):
            return 1.0

        if speed <= 0:
            return 1.0

        return speed
