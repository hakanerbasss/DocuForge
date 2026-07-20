import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

from app.providers.base import VoiceProvider
from app.utils.audio_cleanup import apply_loudness_normalization


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

        # VoiceService passes the same 0.5-2.0 "speed" multiplier every
        # other provider uses (1.0 = normal, >1.0 = faster) -- but this
        # only ever read a "length_scale" option key, which VoiceService
        # never sends. So `speed` was silently ignored and every project
        # got Piper's fixed default rate regardless of its voice_speed
        # setting. Piper's --length-scale is duration-based and inverted
        # from "speed" (length_scale=2.0 means twice as LONG, i.e. half
        # speed), so convert explicitly instead of just renaming the key.
        speed_multiplier = self._normalize_speed(
            options.get("speed", 1.0)
        )
        length_scale = round(1.0 / speed_multiplier, 4)

        sentence_silence = float(
            options.get("sentence_silence", 0.15)
        )

        volume = float(
            options.get("volume", 1.0)
        )

        piper_binary = self._resolve_piper_binary()

        command = [
            piper_binary,
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
                f"Piper could not be run ({piper_binary} not executable). "
                "It's usually installed but not reachable from the "
                "service's PATH -- see PiperVoiceProvider._resolve_piper_"
                "binary() docstring for the fix."
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

        # Piper's raw output has a known crackle between sentences (see
        # apply_loudness_normalization()'s docstring). Runs after the file
        # is already confirmed valid, and never fails the synthesis if the
        # cleanup pass itself has a problem.
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

    def _resolve_piper_binary(self) -> str:
        """Locate the `piper` CLI, tolerating the most common deploy gap.

        `pip install piper-tts` drops a `piper` console script into the
        *current interpreter's* bin directory (e.g. a venv's bin/). That's
        on PATH in an interactive shell where you ran the install, but a
        systemd service often runs with a different, minimal PATH -- so
        `subprocess.run(["piper", ...])` raises FileNotFoundError even
        though Piper is genuinely installed.

        Fix order:
        1. `piper` already on PATH -- use it as-is.
        2. A `piper` script next to the current Python interpreter
           (covers "installed in this venv, PATH just doesn't include it").
        3. Otherwise raise -- the caller's error message points at this
           docstring; the real fix is either adding that directory to the
           systemd unit's PATH (Environment="PATH=...") or reinstalling
           with `pip install piper-tts` inside the exact venv the service
           uses (check with `systemctl show docuforge-web -p
           ExecStart,Environment` on the server).
        """

        on_path = shutil.which("piper")

        if on_path:
            return on_path

        interpreter_dir = Path(sys.executable).parent
        candidate = interpreter_dir / "piper"

        if candidate.exists():
            return str(candidate)

        raise RuntimeError(
            "Piper is not installed or not reachable from this process's "
            "PATH. If you already ran `pip install piper-tts`, the "
            "install likely landed in a different Python environment than "
            "the one the DocuForge service runs in. On the server: run "
            "`pip install piper-tts` again inside the SAME venv the "
            "systemd service uses, or find the binary with `find / -name "
            "piper -type f 2>/dev/null` and add its directory to the "
            "service's PATH."
        )
