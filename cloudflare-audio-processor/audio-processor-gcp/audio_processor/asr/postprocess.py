"""ASR post-processing: timestamp markers and formatting.

Converts a Transcript into human-readable text with [MM:SS] timestamp
markers every 15 seconds and speaker labels at turn boundaries.
"""

from audio_processor.asr.interface import Transcript

MARKER_INTERVAL_SECONDS = 15


def _format_timestamp(seconds: float) -> str:
    """Format seconds as [MM:SS] timestamp marker."""
    total_seconds = int(seconds)
    minutes = total_seconds // 60
    secs = total_seconds % 60
    return f"[{minutes:02d}:{secs:02d}]"


def insert_timestamp_markers(transcript: Transcript) -> str:
    """Convert a Transcript into formatted text with timestamps and speaker labels.

    Inserts [MM:SS] markers at each 15-second boundary based on word start times.
    Prepends speaker labels at the start of each speaker turn. Inserts an empty
    line between speaker changes.

    Args:
        transcript: Transcript with speaker-labeled segments.

    Returns:
        Formatted string with timestamp markers and speaker labels.
        Empty string for empty transcripts.
    """
    if not transcript.segments:
        return ""

    lines: list[str] = []
    next_marker_time = 0.0
    prev_speaker: str | None = None

    for segment in transcript.segments:
        if not segment.words:
            continue

        is_speaker_change = (
            prev_speaker is not None and segment.speaker_label != prev_speaker
        )

        if is_speaker_change:
            lines.append("")

        prev_speaker = segment.speaker_label
        speaker_label_emitted = False

        for word in segment.words:
            parts: list[str] = []

            # Emit timestamp marker if we've crossed a boundary
            if word.start_time >= next_marker_time:
                # Snap to the most recent boundary at or before this word
                boundary = (
                    int(word.start_time // MARKER_INTERVAL_SECONDS)
                    * MARKER_INTERVAL_SECONDS
                )
                parts.append(_format_timestamp(boundary))
                next_marker_time = boundary + MARKER_INTERVAL_SECONDS

            # Emit speaker label at start of turn
            if not speaker_label_emitted:
                parts.append(f"{segment.speaker_label}:")
                speaker_label_emitted = True

            parts.append(word.text)

            if len(parts) > 1:
                # This word has a marker and/or speaker label prefix
                line = " ".join(parts)
                lines.append(line)
            else:
                # Append word to the current line
                if lines and not lines[-1].endswith(":"):
                    lines[-1] += f" {word.text}"
                else:
                    lines.append(word.text)

    return "\n".join(lines)
