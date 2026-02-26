"""Silero VAD v6 engine using ONNX runtime inference.

Processes 16kHz mono PCM WAV in 512-sample frames using the vendored
silero_vad.onnx model. Produces speech segments and a speech-only output WAV.
"""

import os
from pathlib import Path

import numpy as np
import onnxruntime as ort

from audio_processor.audio.vad.interface import SpeechSegment, VADEngine, VADResult
from audio_processor.audio.wav_utils import (
    SAMPLE_RATE,
    read_wav_samples,
    write_wav_samples,
)
from audio_processor.utils.errors import VADError

FRAME_SIZE = 512
DEFAULT_THRESHOLD = 0.5
# Minimum silence gap (in seconds) between segments before merging
MIN_SILENCE_GAP = 0.25

_MODEL_PATH = Path(__file__).parent / "models" / "silero_vad.onnx"


class SileroVADEngine(VADEngine):
    """Silero VAD v6 engine with ONNX runtime inference.

    Args:
        threshold: Speech probability threshold (default 0.5).
        model_path: Path to the ONNX model file. Defaults to vendored model.
    """

    def __init__(
        self,
        threshold: float = DEFAULT_THRESHOLD,
        model_path: str | None = None,
    ) -> None:
        self.threshold = threshold
        resolved_path = model_path or str(_MODEL_PATH)
        try:
            self._session = ort.InferenceSession(resolved_path)
        except Exception as exc:
            raise VADError(
                f"Failed to load Silero VAD model: {resolved_path}",
                detail=str(exc),
            ) from exc

    def process(self, input_path: str, output_dir: str) -> VADResult:
        """Run Silero VAD on a 16kHz mono 16-bit PCM WAV file.

        Processes audio in 512-sample frames, detects speech segments,
        merges nearby segments, and writes speech-only output.

        Args:
            input_path: Path to the input WAV file.
            output_dir: Directory for the speech-only output WAV.

        Returns:
            VADResult with speech segments, durations, and output path.

        Raises:
            VADError: On model inference or I/O failures.
        """
        try:
            samples = read_wav_samples(input_path)
        except ValueError as exc:
            raise VADError(str(exc)) from exc

        total_samples = len(samples)
        if total_samples == 0:
            os.makedirs(output_dir, exist_ok=True)
            output_path = os.path.join(output_dir, "speech.wav")
            write_wav_samples(output_path, [])
            return VADResult(
                segments=[],
                total_duration_seconds=0.0,
                speech_duration_seconds=0.0,
                speech_ratio=0.0,
                output_path=output_path,
            )

        total_duration = total_samples / SAMPLE_RATE
        frame_speech = self._detect_speech_frames(samples)
        raw_segments = self._frames_to_segments(frame_speech, total_samples)
        merged = self._merge_segments(raw_segments)

        speech_samples = self._extract_speech_samples(samples, merged)

        os.makedirs(output_dir, exist_ok=True)
        output_path = os.path.join(output_dir, "speech.wav")
        write_wav_samples(output_path, speech_samples)

        speech_duration = len(speech_samples) / SAMPLE_RATE
        speech_ratio = speech_duration / total_duration if total_duration > 0 else 0.0

        return VADResult(
            segments=merged,
            total_duration_seconds=total_duration,
            speech_duration_seconds=speech_duration,
            speech_ratio=speech_ratio,
            output_path=output_path,
        )

    def _detect_speech_frames(self, samples: list[int]) -> list[bool]:
        """Classify each 512-sample frame as speech or silence.

        Returns a list of booleans, one per frame.
        """
        float_samples = np.array(
            [s / 32768.0 for s in samples], dtype=np.float32
        )
        state = np.zeros((2, 1, 128), dtype=np.float32)
        sr = np.array(SAMPLE_RATE, dtype=np.int64)

        frame_speech: list[bool] = []
        offset = 0

        while offset + FRAME_SIZE <= len(float_samples):
            chunk = float_samples[offset : offset + FRAME_SIZE].reshape(1, -1)
            try:
                output, state = self._session.run(
                    ["output", "stateN"],
                    {"input": chunk, "state": state, "sr": sr},
                )
            except Exception as exc:
                raise VADError(
                    f"ONNX inference failed at offset {offset}",
                    detail=str(exc),
                ) from exc

            prob = float(output[0][0])
            frame_speech.append(prob >= self.threshold)
            offset += FRAME_SIZE

        # Zero-pad partial final frame so tail samples are not discarded
        remaining = len(float_samples) - offset
        if remaining > 0:
            padded = np.zeros(FRAME_SIZE, dtype=np.float32)
            padded[:remaining] = float_samples[offset : offset + remaining]
            chunk = padded.reshape(1, -1)
            try:
                output, state = self._session.run(
                    ["output", "stateN"],
                    {"input": chunk, "state": state, "sr": sr},
                )
            except Exception as exc:
                raise VADError(
                    f"ONNX inference failed at partial frame offset {offset}",
                    detail=str(exc),
                ) from exc

            prob = float(output[0][0])
            frame_speech.append(prob >= self.threshold)

        return frame_speech

    def _frames_to_segments(
        self, frame_speech: list[bool], total_samples: int
    ) -> list[SpeechSegment]:
        """Convert per-frame speech flags to SpeechSegment list."""
        segments: list[SpeechSegment] = []
        in_speech = False
        start_sample = 0

        for i, is_speech in enumerate(frame_speech):
            frame_start = i * FRAME_SIZE
            if is_speech and not in_speech:
                in_speech = True
                start_sample = frame_start
            elif not is_speech and in_speech:
                in_speech = False
                end_sample = frame_start
                segments.append(SpeechSegment(
                    start_sample=start_sample,
                    end_sample=end_sample,
                    start_seconds=start_sample / SAMPLE_RATE,
                    end_seconds=end_sample / SAMPLE_RATE,
                ))

        if in_speech:
            end_sample = min(len(frame_speech) * FRAME_SIZE, total_samples)
            segments.append(SpeechSegment(
                start_sample=start_sample,
                end_sample=end_sample,
                start_seconds=start_sample / SAMPLE_RATE,
                end_seconds=end_sample / SAMPLE_RATE,
            ))

        return segments

    def _merge_segments(
        self, segments: list[SpeechSegment]
    ) -> list[SpeechSegment]:
        """Merge segments separated by gaps shorter than MIN_SILENCE_GAP."""
        if not segments:
            return []

        merged: list[SpeechSegment] = [segments[0]]
        for seg in segments[1:]:
            prev = merged[-1]
            gap = seg.start_seconds - prev.end_seconds
            if gap < MIN_SILENCE_GAP:
                merged[-1] = SpeechSegment(
                    start_sample=prev.start_sample,
                    end_sample=seg.end_sample,
                    start_seconds=prev.start_seconds,
                    end_seconds=seg.end_seconds,
                )
            else:
                merged.append(seg)

        return merged

    def _extract_speech_samples(
        self, samples: list[int], segments: list[SpeechSegment]
    ) -> list[int]:
        """Extract samples from speech segments into a flat list."""
        speech: list[int] = []
        for seg in segments:
            speech.extend(samples[seg.start_sample : seg.end_sample])
        return speech
