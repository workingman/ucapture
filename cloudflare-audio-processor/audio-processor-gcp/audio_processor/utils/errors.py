"""Custom exception hierarchy for the audio processing pipeline.

All exceptions inherit from PipelineError, enabling targeted handling
at pipeline boundaries while preserving specific failure context.
"""


class PipelineError(Exception):
    """Base exception for all audio pipeline errors."""

    def __init__(self, message: str, batch_id: str | None = None) -> None:
        self.batch_id = batch_id
        super().__init__(message)

    def __str__(self) -> str:
        if self.batch_id:
            return f"[batch={self.batch_id}] {super().__str__()}"
        return super().__str__()


class AudioFetchError(PipelineError):
    """Raised when fetching audio from R2 storage fails."""

    def __init__(
        self, message: str, batch_id: str | None = None, key: str | None = None
    ) -> None:
        self.key = key
        super().__init__(message, batch_id)


class TranscodeError(PipelineError):
    """Raised when ffmpeg transcoding fails."""

    def __init__(
        self,
        message: str,
        batch_id: str | None = None,
        input_path: str | None = None,
    ) -> None:
        self.input_path = input_path
        super().__init__(message, batch_id)


class VADError(PipelineError):
    """Raised when voice activity detection fails."""

    def __init__(
        self,
        message: str,
        batch_id: str | None = None,
        detail: str | None = None,
    ) -> None:
        self.detail = detail
        super().__init__(message, batch_id)


class DenoiseError(PipelineError):
    """Raised when noise suppression fails."""

    def __init__(
        self,
        message: str,
        batch_id: str | None = None,
        detail: str | None = None,
    ) -> None:
        self.detail = detail
        super().__init__(message, batch_id)


class ASRError(PipelineError):
    """Raised when automatic speech recognition fails."""

    def __init__(
        self,
        message: str,
        batch_id: str | None = None,
        provider: str | None = None,
    ) -> None:
        self.provider = provider
        super().__init__(message, batch_id)


class StorageError(PipelineError):
    """Raised when storage operations (R2/D1) fail."""

    def __init__(
        self,
        message: str,
        batch_id: str | None = None,
        operation: str | None = None,
    ) -> None:
        self.operation = operation
        super().__init__(message, batch_id)


class EmotionAnalysisError(PipelineError):
    """Raised when emotion analysis fails."""

    def __init__(
        self,
        message: str,
        batch_id: str | None = None,
        detail: str | None = None,
    ) -> None:
        self.detail = detail
        super().__init__(message, batch_id)
