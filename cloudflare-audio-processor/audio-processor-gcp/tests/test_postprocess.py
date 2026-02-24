"""Tests for transcript post-processing with timestamp markers."""

from audio_processor.asr.interface import (
    Transcript,
    TranscriptSegment,
    TranscriptWord,
)
from audio_processor.asr.postprocess import insert_timestamp_markers


def _word(
    text: str, start: float, end: float, confidence: float = 0.9
) -> TranscriptWord:
    """Shorthand for building a TranscriptWord."""
    return TranscriptWord(
        text=text,
        start_time=start,
        end_time=end,
        confidence=confidence,
    )


class TestInsertTimestampMarkers:
    """Tests for the insert_timestamp_markers function."""

    def test_single_speaker_with_markers(self) -> None:
        """Single speaker with words spanning [00:00], [00:15], [00:30]."""
        transcript = Transcript(
            segments=[
                TranscriptSegment(
                    speaker_label="Speaker 1",
                    words=[
                        _word("Hello", 0.0, 0.5),
                        _word("how", 0.6, 0.9),
                        _word("are", 1.0, 1.3),
                        _word("you", 15.0, 15.4),
                        _word("today", 15.5, 15.9),
                        _word("great", 30.0, 30.5),
                    ],
                )
            ],
            raw_response={},
        )

        result = insert_timestamp_markers(transcript)

        assert "[00:00]" in result
        assert "[00:15]" in result
        assert "[00:30]" in result
        assert "Speaker 1:" in result

    def test_multi_speaker_with_turn_breaks(self) -> None:
        """Multiple speakers with correct labels and empty line between turns."""
        transcript = Transcript(
            segments=[
                TranscriptSegment(
                    speaker_label="Speaker 1",
                    words=[
                        _word("Hello", 0.0, 0.5),
                        _word("everyone", 0.6, 1.0),
                    ],
                ),
                TranscriptSegment(
                    speaker_label="Speaker 2",
                    words=[
                        _word("Hi", 1.5, 1.8),
                        _word("there", 1.9, 2.2),
                    ],
                ),
            ],
            raw_response={},
        )

        result = insert_timestamp_markers(transcript)

        assert "Speaker 1:" in result
        assert "Speaker 2:" in result
        # Empty line between speaker changes
        assert "\n\n" in result

    def test_empty_transcript_returns_empty_string(self) -> None:
        """Empty transcript produces empty string."""
        transcript = Transcript(segments=[], raw_response={})
        result = insert_timestamp_markers(transcript)
        assert result == ""

    def test_short_transcript_only_first_marker(self) -> None:
        """Transcript shorter than 15s gets only [00:00] marker."""
        transcript = Transcript(
            segments=[
                TranscriptSegment(
                    speaker_label="Speaker 1",
                    words=[
                        _word("Quick", 0.0, 0.3),
                        _word("test", 0.4, 0.7),
                    ],
                )
            ],
            raw_response={},
        )

        result = insert_timestamp_markers(transcript)

        assert "[00:00]" in result
        assert "[00:15]" not in result

    def test_markers_past_one_minute(self) -> None:
        """Timestamps past 60s use [01:00], [01:15], etc."""
        transcript = Transcript(
            segments=[
                TranscriptSegment(
                    speaker_label="Speaker 1",
                    words=[
                        _word("Start", 0.0, 0.5),
                        _word("middle", 60.0, 60.5),
                        _word("later", 75.0, 75.5),
                    ],
                )
            ],
            raw_response={},
        )

        result = insert_timestamp_markers(transcript)

        assert "[00:00]" in result
        assert "[01:00]" in result
        assert "[01:15]" in result

    def test_speaker_label_at_start_of_turn_only(self) -> None:
        """Speaker label appears only once per turn, not on every line."""
        transcript = Transcript(
            segments=[
                TranscriptSegment(
                    speaker_label="Speaker 1",
                    words=[
                        _word("Hello", 0.0, 0.5),
                        _word("world", 0.6, 1.0),
                        _word("again", 15.0, 15.5),
                    ],
                )
            ],
            raw_response={},
        )

        result = insert_timestamp_markers(transcript)

        # Speaker label should appear exactly once
        assert result.count("Speaker 1:") == 1

    def test_words_between_markers_joined_by_spaces(self) -> None:
        """Words between timestamp markers are joined by spaces."""
        transcript = Transcript(
            segments=[
                TranscriptSegment(
                    speaker_label="Speaker 1",
                    words=[
                        _word("Hello", 0.0, 0.3),
                        _word("how", 0.4, 0.6),
                        _word("are", 0.7, 0.9),
                        _word("you", 1.0, 1.2),
                    ],
                )
            ],
            raw_response={},
        )

        result = insert_timestamp_markers(transcript)

        # All words should be on the same line, space-separated
        assert "how are you" in result
