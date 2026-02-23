"""Tests for ASR engine interface and transcript data models."""

import pytest

from audio_processor.asr.interface import (
    ASREngine,
    Transcript,
    TranscriptSegment,
    TranscriptWord,
)


class TestTranscriptDataModels:
    """Tests for transcript data model instantiation."""

    def test_transcript_word_fields(self) -> None:
        word = TranscriptWord(
            text="hello",
            start_time=0.5,
            end_time=0.9,
            confidence=0.95,
        )
        assert word.text == "hello"
        assert word.start_time == 0.5
        assert word.end_time == 0.9
        assert word.confidence == 0.95

    def test_transcript_segment_with_words(self) -> None:
        words = [
            TranscriptWord(text="hello", start_time=0.0, end_time=0.3, confidence=0.9),
            TranscriptWord(text="world", start_time=0.4, end_time=0.7, confidence=0.85),
        ]
        segment = TranscriptSegment(speaker_label="S1", words=words)

        assert segment.speaker_label == "S1"
        assert len(segment.words) == 2

    def test_transcript_with_segments(self) -> None:
        segment = TranscriptSegment(
            speaker_label="S1",
            words=[TranscriptWord("hi", 0.0, 0.2, 0.9)],
        )
        transcript = Transcript(
            segments=[segment],
            raw_response={"provider": "test"},
        )
        assert len(transcript.segments) == 1
        assert transcript.raw_response["provider"] == "test"


class TestASREngineABC:
    """Tests for ASR engine abstract base class."""

    def test_cannot_instantiate_directly(self) -> None:
        with pytest.raises(TypeError):
            ASREngine()  # type: ignore[abstract]

    def test_concrete_subclass_can_be_instantiated(self) -> None:
        class MockASR(ASREngine):
            async def transcribe(
                self, audio_path: str, metadata: dict
            ) -> Transcript:
                return Transcript(segments=[], raw_response={})

        engine = MockASR()
        assert isinstance(engine, ASREngine)

    @pytest.mark.asyncio
    async def test_concrete_subclass_transcribe_returns_transcript(self) -> None:
        class MockASR(ASREngine):
            async def transcribe(
                self, audio_path: str, metadata: dict
            ) -> Transcript:
                return Transcript(
                    segments=[
                        TranscriptSegment(
                            speaker_label="S1",
                            words=[TranscriptWord("test", 0.0, 0.5, 0.99)],
                        )
                    ],
                    raw_response={"mock": True},
                )

        engine = MockASR()
        result = await engine.transcribe("/fake/path.wav", {})
        assert isinstance(result, Transcript)
        assert len(result.segments) == 1
