"""VAD engine registry with configuration-driven provider selection.

Maps provider name strings to engine classes. Use get_vad_engine() to
instantiate an engine by name with engine-specific configuration.
"""

from audio_processor.audio.vad.interface import VADEngine
from audio_processor.audio.vad.null import NullVADEngine
from audio_processor.utils.errors import VADError

VAD_ENGINES: dict[str, type[VADEngine]] = {
    "null": NullVADEngine,
}


def get_vad_engine(provider: str, **kwargs: object) -> VADEngine:
    """Create a VAD engine instance by provider name.

    Args:
        provider: Provider name (e.g., "silero", "null").
        **kwargs: Engine-specific configuration passed to the constructor.

    Returns:
        An initialized VADEngine instance.

    Raises:
        VADError: If the provider name is not registered.
    """
    engine_cls = VAD_ENGINES.get(provider)
    if not engine_cls:
        available = ", ".join(sorted(VAD_ENGINES.keys()))
        raise VADError(
            f"Unknown VAD provider: '{provider}'. Available: {available}"
        )
    return engine_cls(**kwargs)
