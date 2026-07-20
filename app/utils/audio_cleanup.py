import subprocess
from pathlib import Path


def apply_loudness_normalization(
    audio_path: Path,
    sample_rate: int = 24000,
) -> None:
    """Run a gentle EBU R128 loudness-normalize + highpass pass over a WAV
    file, in place.

    eSpeak-ng and Piper's raw output can sound crackly/harsh at their
    default output levels -- loudnorm brings it to a consistent,
    non-clipping level (its built-in limiter catches peaks that would
    otherwise clip and crackle) and a gentle highpass removes sub-80Hz
    rumble/DC offset that shows up as buzz on small speakers. This was a
    known, previously-deferred issue (documented as needing a real
    listening test before doing anything about it) -- PROJECT_STATE.md
    flagged exactly this fix ("loudnorm/highpass") as the plan.

    Never raises: if ffmpeg isn't available or the pass fails for any
    reason, the original (uncleaned but still valid) file is left
    untouched rather than losing a working synthesis over a nice-to-have
    polish step.
    """

    temp_path = audio_path.with_suffix(".cleanup.wav")

    try:
        subprocess.run(
            [
                "ffmpeg",
                "-y",
                "-i",
                str(audio_path),
                "-af",
                "loudnorm=I=-16:TP=-1.5:LRA=11,highpass=f=80",
                "-ar",
                str(sample_rate),
                "-ac",
                "1",
                str(temp_path),
            ],
            check=True,
            capture_output=True,
            text=True,
            timeout=60,
        )

        if temp_path.exists() and temp_path.stat().st_size > 0:
            temp_path.replace(audio_path)
    except Exception as error:
        print(
            f"  ⚠ Ses temizleme adımı atlandı (ham çıktı kullanılıyor): {error}"
        )
    finally:
        temp_path.unlink(missing_ok=True)
