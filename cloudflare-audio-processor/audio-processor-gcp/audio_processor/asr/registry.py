"""ASR engine registry with configuration-driven provider selection.

Maps provider name strings to engine classes. Use get_asr_engine() to
instantiate an engine by name with engine-specific configuration.
"""

from audio_processor.asr.interface import ASREngine
from audio_processor.asr.speechmatics import SpeechmaticsEngine
from audio_processor.utils.errors import ASRError

ASR_ENGINES: dict[str, type[ASREngine]] = {
    "speechmatics": SpeechmaticsEngine,
}


def get_asr_engine(provider: str, **kwargs: object) -> ASREngine:
    """Create an ASR engine instance by provider name.

    Args:
        provider: Provider name (e.g., "speechmatics").
        **kwargs: Engine-specific configuration passed to the constructor.

    Returns:
        An initialized ASREngine instance.

    Raises:
        ASRError: If the provider name is not registered.
    """
    engine_cls = ASR_ENGINES.get(provider)
    if not engine_cls:
        available = ", ".join(sorted(ASR_ENGINES.keys()))
        raise ASRError(
            f"Unknown ASR provider: '{provider}'. Available: {available}",
            provider=provider,
        )
    return engine_cls(**kwargs)
