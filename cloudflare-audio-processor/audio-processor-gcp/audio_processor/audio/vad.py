"""Picovoice Cobra voice activity detection integration.

Processes 16kHz mono PCM WAV frame-by-frame using Cobra to detect speech
segments, extract speech frames, and produce a speech-only output WAV.
"""

import os
import struct
import wave
from dataclasses import dataclass, field

from audio_processor.utils.errors import VADError

SAMPLE_RATE = 16000
SAMPLE_WIDTH = 2  # 16-bit = 2 bytes
NUM_CHANNELS = 1
DEFAULT_THRESHOLD = 0.5


@dataclass
class SpeechSegment:
    """A contiguous segment of detected speech."""

    start_seconds: float
    end_seconds: float


@dataclass
class VADResult:
    """Result of voice activity detection processing."""

    speech_segments: list[SpeechSegment] = field(default_factory=list)
    speech_duration_seconds: float = 0.0
    speech_ratio: float = 0.0
    output_path: str | None = None


def _read_wav_samples(wav_path: str) -> list[int]:
    """Read all samples from a 16kHz mono 16-bit WAV file.

    Args:
        wav_path: Path to the WAV file.

    Returns:
        List of int16 sample values.

    Raises:
        VADError: If the WAV file cannot be read.
    """
    try:
        with wave.open(wav_path, "rb") as wf:
            raw_data = wf.readframes(wf.getnframes())
    except Exception as exc:
        raise VADError(f"Failed to read WAV file: {wav_path}") from exc

    num_samples = len(raw_data) // SAMPLE_WIDTH
    return list(struct.unpack(f"<{num_samples}h", raw_data))


def _write_wav_samples(
    output_path: str, samples: list[int], sample_rate: int = SAMPLE_RATE
) -> None:
    """Write int16 samples to a 16kHz mono 16-bit WAV file.

    Args:
        output_path: Path for the output WAV file.
        samples: List of int16 sample values.
        sample_rate: Sample rate in Hz (default 16000).
    """
    raw_data = struct.pack(f"<{len(samples)}h", *samples)
    with wave.open(output_path, "wb") as wf:
        wf.setnchannels(NUM_CHANNELS)
        wf.setsampwidth(SAMPLE_WIDTH)
        wf.setframerate(sample_rate)
        wf.writeframes(raw_data)


def run_vad(
    input_path: str,
    output_dir: str,
    access_key: str,
    threshold: float = DEFAULT_THRESHOLD,
    output_filename: str = "speech.wav",
) -> VADResult:
    """Run Cobra VAD on a 16kHz mono WAV file.

    Processes audio frame-by-frame, detects speech segments where voice
    probability exceeds the threshold, and writes speech frames to output.

    Args:
        input_path: Path to 16kHz mono 16-bit PCM WAV input.
        output_dir: Directory for the speech-only output WAV.
        access_key: Picovoice access key for Cobra initialization.
        threshold: Voice probability threshold (default 0.5).
        output_filename: Name for the output WAV file.

    Returns:
        VADResult with segments, durations, and output path.

    Raises:
        VADError: On Cobra init failure or processing errors.
    """
    import pvcobra

    try:
        cobra = pvcobra.create(access_key=access_key)
    except Exception as exc:
        raise VADError(f"Failed to initialize Cobra: {exc}", detail=str(exc)) from exc

    try:
        samples = _read_wav_samples(input_path)
        total_samples = len(samples)

        if total_samples == 0:
            return VADResult()

        total_duration = total_samples / SAMPLE_RATE
        frame_length = cobra.frame_length

        speech_frames: list[int] = []
        segments: list[SpeechSegment] = []
        in_speech = False
        segment_start = 0.0

        offset = 0
        while offset + frame_length <= total_samples:
            frame = samples[offset : offset + frame_length]
            voice_probability = cobra.process(frame)

            frame_start = offset / SAMPLE_RATE

            if voice_probability >= threshold:
                speech_frames.extend(frame)
                if not in_speech:
                    in_speech = True
                    segment_start = frame_start
            else:
                if in_speech:
                    in_speech = False
                    segments.append(
                        SpeechSegment(
                            start_seconds=segment_start,
                            end_seconds=frame_start,
                        )
                    )

            offset += frame_length

        # Close any open segment
        if in_speech:
            segments.append(
                SpeechSegment(
                    start_seconds=segment_start,
                    end_seconds=offset / SAMPLE_RATE,
                )
            )

        # Zero-speech case
        if not speech_frames:
            return VADResult(
                speech_segments=[],
                speech_duration_seconds=0.0,
                speech_ratio=0.0,
                output_path=None,
            )

        # Write speech-only WAV
        os.makedirs(output_dir, exist_ok=True)
        output_path = os.path.join(output_dir, output_filename)
        _write_wav_samples(output_path, speech_frames)

        speech_duration = len(speech_frames) / SAMPLE_RATE
        speech_ratio = speech_duration / total_duration if total_duration > 0 else 0.0

        return VADResult(
            speech_segments=segments,
            speech_duration_seconds=speech_duration,
            speech_ratio=speech_ratio,
            output_path=output_path,
        )

    finally:
        cobra.delete()
