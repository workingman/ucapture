"""Tests for project scaffold: imports, logger, and custom exceptions."""

import json

import pytest

from audio_processor.observability.logger import StructuredJsonFormatter, get_logger
from audio_processor.utils.errors import (
    ASRError,
    AudioFetchError,
    DenoiseError,
    EmotionAnalysisError,
    PipelineError,
    StorageError,
    TranscodeError,
    VADError,
)


class TestModuleImports:
    """Verify all package modules are importable."""

    def test_top_level_import(self) -> None:
        import audio_processor

        assert audio_processor is not None

    def test_subpackage_imports(self) -> None:
        import audio_processor.audio
        import audio_processor.asr
        import audio_processor.emotion
        import audio_processor.storage
        import audio_processor.queue
        import audio_processor.observability
        import audio_processor.utils

        assert audio_processor.audio is not None
        assert audio_processor.asr is not None
        assert audio_processor.emotion is not None
        assert audio_processor.storage is not None
        assert audio_processor.queue is not None
        assert audio_processor.observability is not None
        assert audio_processor.utils is not None


class TestCustomExceptions:
    """Verify custom exception hierarchy and string representations."""

    def test_all_exceptions_inherit_from_pipeline_error(self) -> None:
        exception_classes = [
            AudioFetchError,
            TranscodeError,
            VADError,
            DenoiseError,
            ASRError,
            StorageError,
            EmotionAnalysisError,
        ]
        for cls in exception_classes:
            assert issubclass(cls, PipelineError), (
                f"{cls.__name__} must inherit from PipelineError"
            )

    def test_pipeline_error_str_without_batch_id(self) -> None:
        error = PipelineError("something failed")
        assert str(error) == "something failed"

    def test_pipeline_error_str_with_batch_id(self) -> None:
        error = PipelineError("something failed", batch_id="batch-123")
        assert "[batch=batch-123]" in str(error)
        assert "something failed" in str(error)

    def test_transcode_error_includes_context(self) -> None:
        error = TranscodeError(
            "ffmpeg failed", batch_id="b-1", input_path="/tmp/test.m4a"
        )
        assert error.input_path == "/tmp/test.m4a"
        assert "[batch=b-1]" in str(error)

    def test_audio_fetch_error_includes_key(self) -> None:
        error = AudioFetchError("not found", key="user/batch/audio.m4a")
        assert error.key == "user/batch/audio.m4a"

    def test_asr_error_includes_provider(self) -> None:
        error = ASRError("timeout", provider="speechmatics")
        assert error.provider == "speechmatics"

    def test_storage_error_includes_operation(self) -> None:
        error = StorageError("write failed", operation="put_object")
        assert error.operation == "put_object"

    def test_exceptions_are_catchable_as_pipeline_error(self) -> None:
        with pytest.raises(PipelineError):
            raise TranscodeError("test error")


class TestStructuredLogger:
    """Verify structured JSON logger output format."""

    def test_logger_output_is_valid_json(self, capsys: pytest.CaptureFixture[str]) -> None:
        logger = get_logger("test.json_output")
        logger.info("test message")

        captured = capsys.readouterr()
        parsed = json.loads(captured.out.strip())

        assert "timestamp" in parsed
        assert "severity" in parsed
        assert "message" in parsed

    def test_logger_severity_levels(self, capsys: pytest.CaptureFixture[str]) -> None:
        logger = get_logger("test.severity")
        logger.info("info message")

        captured = capsys.readouterr()
        parsed = json.loads(captured.out.strip())
        assert parsed["severity"] == "INFO"

    def test_logger_includes_extra_fields(self, capsys: pytest.CaptureFixture[str]) -> None:
        logger = get_logger("test.extra")
        logger.info("processing", extra={"batch_id": "b-42", "stage": "transcode"})

        captured = capsys.readouterr()
        parsed = json.loads(captured.out.strip())
        assert parsed["batch_id"] == "b-42"
        assert parsed["stage"] == "transcode"

    def test_logger_timestamp_format(self, capsys: pytest.CaptureFixture[str]) -> None:
        logger = get_logger("test.timestamp")
        logger.warning("check format")

        captured = capsys.readouterr()
        parsed = json.loads(captured.out.strip())
        # Should be ISO 8601 format: YYYY-MM-DDTHH:MM:SSZ
        timestamp = parsed["timestamp"]
        assert timestamp.endswith("Z")
        assert "T" in timestamp
