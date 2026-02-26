"""M4A to 16kHz WAV transcoder using ffmpeg.

Converts M4A input (44.1kHz AAC mono) to WAV output (16kHz mono 16-bit PCM)
as required by Picovoice SDKs (Cobra VAD, Koala denoise).
"""

import os
import shutil
import subprocess
import wave
from dataclasses import dataclass
from pathlib import Path

from audio_processor.utils.errors import TranscodeError

TARGET_SAMPLE_RATE = 16000
TARGET_CHANNELS = 1
TARGET_SAMPLE_WIDTH = 2  # 16-bit = 2 bytes


@dataclass
class TranscodeResult:
    """Result of a successful transcode operation."""

    input_path: str
    output_path: str
    input_size_bytes: int
    output_size_bytes: int
    duration_seconds: float


FFPROBE_TIMEOUT_SECONDS = 10


def _check_ffmpeg_available() -> str:
    """Verify ffmpeg is available on the system.

    Returns:
        Path to the ffmpeg binary.

    Raises:
        TranscodeError: If ffmpeg is not found.
    """
    ffmpeg_path = shutil.which("ffmpeg")
    if ffmpeg_path is None:
        raise TranscodeError("ffmpeg binary not found on PATH")
    return ffmpeg_path


def _check_audio_valid(input_path: str) -> None:
    """Pre-validate audio file with ffprobe before transcoding.

    Runs ffprobe with a short timeout to detect corrupt files quickly
    instead of waiting for ffmpeg's 120-second timeout.

    Args:
        input_path: Path to the audio file to validate.

    Raises:
        TranscodeError: If ffprobe fails or the file is corrupt.
    """
    ffprobe_path = shutil.which("ffprobe")
    if ffprobe_path is None:
        # ffprobe not available — skip pre-check, let ffmpeg handle it
        return

    cmd = [
        ffprobe_path,
        "-v", "error",
        "-show_format",
        input_path,
    ]

    try:
        subprocess.run(
            cmd,
            check=True,
            capture_output=True,
            text=True,
            timeout=FFPROBE_TIMEOUT_SECONDS,
        )
    except subprocess.CalledProcessError as exc:
        stderr = exc.stderr.strip() if exc.stderr else "unknown error"
        raise TranscodeError(
            f"Audio file is corrupt or unreadable (ffprobe): {stderr}",
            input_path=input_path,
        ) from exc
    except subprocess.TimeoutExpired as exc:
        raise TranscodeError(
            f"ffprobe timed out after {FFPROBE_TIMEOUT_SECONDS}s — file may be corrupt",
            input_path=input_path,
        ) from exc


def _read_wav_duration(wav_path: str) -> float:
    """Read duration from a WAV file header.

    Args:
        wav_path: Path to the WAV file.

    Returns:
        Duration in seconds.
    """
    with wave.open(wav_path, "rb") as wf:
        frames = wf.getnframes()
        rate = wf.getframerate()
        return frames / rate


def transcode_to_wav(
    input_path: str,
    output_dir: str,
    output_filename: str | None = None,
) -> TranscodeResult:
    """Transcode an M4A file to 16kHz mono 16-bit PCM WAV.

    Args:
        input_path: Path to the input M4A (or other audio) file.
        output_dir: Directory to write the output WAV file.
        output_filename: Optional output filename. Defaults to input stem + .wav.

    Returns:
        TranscodeResult with paths, sizes, and duration.

    Raises:
        TranscodeError: If the input file doesn't exist, is corrupt, or ffmpeg fails.
    """
    input_file = Path(input_path)

    if not input_file.exists():
        raise TranscodeError(
            f"Input file does not exist: {input_path}",
            input_path=input_path,
        )

    ffmpeg_path = _check_ffmpeg_available()

    # Pre-validate with ffprobe to fail fast on corrupt audio
    _check_audio_valid(input_path)

    if output_filename is None:
        output_filename = f"{input_file.stem}.wav"

    output_path = os.path.join(output_dir, output_filename)
    os.makedirs(output_dir, exist_ok=True)

    cmd = [
        ffmpeg_path,
        "-y",
        "-i",
        input_path,
        "-ar",
        str(TARGET_SAMPLE_RATE),
        "-ac",
        str(TARGET_CHANNELS),
        "-sample_fmt",
        "s16",
        "-f",
        "wav",
        output_path,
    ]

    try:
        subprocess.run(
            cmd,
            check=True,
            capture_output=True,
            text=True,
            timeout=120,
        )
    except subprocess.CalledProcessError as exc:
        raise TranscodeError(
            f"ffmpeg transcode failed: {exc.stderr.strip()}",
            input_path=input_path,
        ) from exc
    except subprocess.TimeoutExpired as exc:
        stderr_snippet = ""
        if exc.stderr:
            stderr_snippet = f" stderr: {exc.stderr.strip()[:200]}"
        raise TranscodeError(
            f"ffmpeg transcode timed out after 120 seconds.{stderr_snippet}",
            input_path=input_path,
        ) from exc

    if not os.path.exists(output_path):
        raise TranscodeError(
            f"ffmpeg produced no output file: {output_path}",
            input_path=input_path,
        )

    duration = _read_wav_duration(output_path)

    return TranscodeResult(
        input_path=input_path,
        output_path=output_path,
        input_size_bytes=input_file.stat().st_size,
        output_size_bytes=os.path.getsize(output_path),
        duration_seconds=duration,
    )
