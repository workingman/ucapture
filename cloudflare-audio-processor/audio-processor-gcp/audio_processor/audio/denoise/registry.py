"""Denoise engine registry with configuration-driven provider selection.

Maps provider name strings to engine classes. Use get_denoise_engine() to
instantiate an engine by name with engine-specific configuration.
"""

from audio_processor.audio.denoise.interface import DenoiseEngine
from audio_processor.audio.denoise.null import NullDenoiseEngine
from audio_processor.utils.errors import DenoiseError

DENOISE_ENGINES: dict[str, type[DenoiseEngine]] = {
    "null": NullDenoiseEngine,
}


def get_denoise_engine(provider: str, **kwargs: object) -> DenoiseEngine:
    """Create a denoise engine instance by provider name.

    Args:
        provider: Provider name (e.g., "null").
        **kwargs: Engine-specific configuration passed to the constructor.

    Returns:
        An initialized DenoiseEngine instance.

    Raises:
        DenoiseError: If the provider name is not registered.
    """
    engine_cls = DENOISE_ENGINES.get(provider)
    if not engine_cls:
        available = ", ".join(sorted(DENOISE_ENGINES.keys()))
        raise DenoiseError(
            f"Unknown denoise provider: '{provider}'. Available: {available}"
        )
    return engine_cls(**kwargs)
