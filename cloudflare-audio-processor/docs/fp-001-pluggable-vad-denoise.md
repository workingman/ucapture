# Feature Proposal: Pluggable VAD & Denoise Engines

## Metadata
- **Author:** Geoff
- **Date:** 2026-02-23
- **Type:** EVOLVE (Brownfield Feature)
- **Status:** Draft

## 1. Feature Description

Replace the hardcoded Picovoice Cobra VAD and Koala noise-suppression functions
with pluggable engine interfaces (ABCs), mirroring the existing `ASREngine` and
`EmotionEngine` patterns. Ship with three concrete implementations:

| Engine              | ABC             | Purpose                                |
|---------------------|-----------------|----------------------------------------|
| `SileroVADEngine`   | `VADEngine`     | Silero VAD v6 (ONNX) speech detection  |
| `NullVADEngine`     | `VADEngine`     | Passthrough: entire audio = one segment |
| `NullDenoiseEngine` | `DenoiseEngine` | Passthrough: copy input to output       |

**Why now:** Picovoice has been dropped (~$899/mo server license). Silero VAD v6
is the replacement ($0, MIT, ONNX). Noise suppression is removed from the
pipeline (paper evidence that enhancement degrades ASR WER 1-47%). Both steps
need pluggable interfaces so future providers can be swapped via config, not
code changes.

## 2. Integration Points

### Existing Modules Affected

| File | Change |
|------|--------|
| `audio_processor/audio/vad.py` | **Rewrite.** Replace bare `run_vad()` + `import pvcobra` with `VADEngine` ABC, `SpeechSegment`/`VADResult` data classes, and shared WAV helpers. Move to `audio_processor/audio/vad/interface.py`. |
| `audio_processor/audio/denoise.py` | **Rewrite.** Replace bare `run_denoise()` + `import pvkoala` with `DenoiseEngine` ABC and `DenoiseResult` data class. Move to `audio_processor/audio/denoise/interface.py`. |
| `audio_processor/utils/errors.py` | **Update.** Change `VADError` docstring from "Picovoice Cobra" to generic. Change `DenoiseError` docstring from "Picovoice Koala" to generic. |
| `audio_processor/pipeline.py` | **Update** (when orchestrator is implemented). Call `vad_engine.process()` and `denoise_engine.process()` instead of `run_vad()` / `run_denoise()`. |
| `requirements.txt` | **Update.** Remove `pvkoala>=2.0.0` and `pvcobra>=2.0.0`. Add `onnxruntime>=1.17.0`. |
| `tests/test_vad.py` | **Rewrite.** Remove `pvcobra` mocking. Test `VADEngine` ABC contract, `SileroVADEngine` with mocked ONNX, `NullVADEngine` directly. |
| `tests/test_denoise.py` | **Rewrite.** Remove `pvkoala` mocking. Test `DenoiseEngine` ABC contract, `NullDenoiseEngine` directly. |

### New Modules

| File | Purpose |
|------|---------|
| `audio_processor/audio/vad/interface.py` | `VADEngine` ABC + `SpeechSegment`, `VADResult` data classes |
| `audio_processor/audio/vad/silero.py` | `SileroVADEngine` — ONNX-based Silero VAD v6 |
| `audio_processor/audio/vad/null.py` | `NullVADEngine` — passthrough (returns entire audio as one segment) |
| `audio_processor/audio/vad/registry.py` | Registry + factory: `get_vad_engine(provider_name)` |
| `audio_processor/audio/denoise/interface.py` | `DenoiseEngine` ABC + `DenoiseResult` data class |
| `audio_processor/audio/denoise/null.py` | `NullDenoiseEngine` — passthrough (copies input to output unchanged) |
| `audio_processor/audio/denoise/registry.py` | Registry + factory: `get_denoise_engine(provider_name)` |
| `audio_processor/audio/wav_utils.py` | Shared WAV I/O helpers (extracted from duplicate code in vad.py and denoise.py) |

### Directory Structure Change

```
audio_processor/audio/
  __init__.py
  transcode.py            # unchanged
  wav_utils.py            # NEW — shared WAV read/write helpers
  vad/
    __init__.py            # NEW — re-exports VADEngine, VADResult, etc.
    interface.py           # NEW — VADEngine ABC + data classes
    silero.py              # NEW — SileroVADEngine
    null.py                # NEW — NullVADEngine
    registry.py            # NEW — engine registry + factory
  denoise/
    __init__.py            # NEW — re-exports DenoiseEngine, DenoiseResult, etc.
    interface.py           # NEW — DenoiseEngine ABC + data class
    null.py                # NEW — NullDenoiseEngine
    registry.py            # NEW — engine registry + factory
```

Old files `audio_processor/audio/vad.py` and `audio_processor/audio/denoise.py`
are deleted (replaced by the subpackages above).

## 3. Interface Design

### VADEngine ABC

```python
class VADEngine(ABC):
    """Abstract base class for VAD engine implementations."""

    @abstractmethod
    def process(self, input_path: str, output_dir: str) -> VADResult:
        """Detect speech segments in audio and write speech-only output.

        Args:
            input_path: Path to 16kHz mono 16-bit PCM WAV input.
            output_dir: Directory for the speech-only output WAV.

        Returns:
            VADResult with segments, durations, and output path.
        """
```

**Design notes:**
- Synchronous (not async) — matches current code and Silero's sync ONNX inference.
- `access_key` removed from the method signature — it was Picovoice-specific.
  Provider-specific config (API keys, model paths, thresholds) goes in `__init__`.
- `threshold` removed from method signature — it's a per-engine tuning parameter,
  set in `__init__` (Silero default: 0.5, same as Cobra was).

### DenoiseEngine ABC

```python
class DenoiseEngine(ABC):
    """Abstract base class for noise suppression engine implementations."""

    @abstractmethod
    def process(self, input_path: str, output_dir: str) -> DenoiseResult:
        """Apply noise suppression to audio.

        Args:
            input_path: Path to 16kHz mono 16-bit PCM WAV input.
            output_dir: Directory for the denoised output WAV.

        Returns:
            DenoiseResult with input/output sizes and output path.
        """
```

### NullVADEngine

Returns the entire input audio as a single speech segment. Output WAV is a copy
of the input. Used for testing or when VAD should be bypassed.

### NullDenoiseEngine

Copies input WAV to output directory unchanged. Returns `DenoiseResult` with
matching input/output sizes. Used as the default (noise suppression is removed
from the pipeline).

### Registry Pattern

Mirrors the emotion runner pattern:

```python
VAD_ENGINES = {
    "silero": SileroVADEngine,
    "null": NullVADEngine,
}

def get_vad_engine(provider: str, **kwargs) -> VADEngine:
    engine_cls = VAD_ENGINES.get(provider)
    if not engine_cls:
        raise VADError(f"Unknown VAD provider: {provider}")
    return engine_cls(**kwargs)
```

### Silero VAD v6 Integration

- **Model:** `silero_vad.onnx` (~2 MB), loaded via `onnxruntime.InferenceSession`
- **Input:** 16kHz 16-bit mono PCM WAV (same as Cobra required)
- **Processing:** 512-sample frames (32ms at 16kHz), returns speech probability
  per frame — same frame-by-frame pattern as the current Cobra code
- **Output:** Same `VADResult` + speech-only WAV as current code produces
- **Dependencies:** `onnxruntime>=1.17.0` (~80 MB wheel)
- **Model download:** Silero distributes via PyTorch Hub or direct ONNX download.
  We'll vendor the `.onnx` file in `audio_processor/audio/vad/models/` to avoid
  runtime downloads.

## 4. Pattern Compliance

**Coding Style:** Follows existing linter config (ruff + black): yes

**Test Pattern:** Matches existing test structure (pytest, tmp_path fixtures,
mock-based unit tests): yes

**Interface Pattern:** Mirrors `ASREngine` (asr/interface.py) and `EmotionEngine`
(emotion/interface.py) ABCs exactly: yes

**Registry Pattern:** Mirrors emotion/runner.py dict-based registry: yes

**Error Handling:** Uses existing `VADError` and `DenoiseError` from
`utils/errors.py` (updated docstrings): yes

## 5. Data Class Reuse

`SpeechSegment` and `VADResult` are unchanged — they move from `vad.py` to
`vad/interface.py` but keep the same fields. `DenoiseResult` is unchanged.
No breaking changes to any consumer of these types.

## 6. Shared WAV Helpers

Both `vad.py` and `denoise.py` currently have identical `_read_wav_samples()`
and `_write_wav_samples()` private functions. These will be extracted to a
shared `wav_utils.py` module:

```python
# audio_processor/audio/wav_utils.py
def read_wav_samples(wav_path: str) -> list[int]: ...
def write_wav_samples(output_path: str, samples: list[int], sample_rate: int = 16000) -> None: ...
```

This is a natural DRY extraction, not premature abstraction — the code is
literally duplicated today.

## 7. Risk Assessment

**Regression Risk:** Medium
- VAD and denoise are core pipeline steps. Changing the interface touches the
  hot path.
- Mitigated by: keeping `VADResult`/`DenoiseResult` data classes unchanged,
  writing tests for both concrete implementations, and running the full test
  suite before merging.

**Breaking Changes:** Yes (internal only)
- `run_vad()` and `run_denoise()` bare functions are removed. All callers
  must use the new engine interface.
- The only caller today is `pipeline.py` which is still a stub
  (`NotImplementedError`), so the real blast radius is zero.
- Test files are rewritten (not backward-compatible, but tests aren't API).

**Dependency Changes:**
- **Removed:** `pvkoala>=2.0.0`, `pvcobra>=2.0.0` (Picovoice SDKs)
- **Added:** `onnxruntime>=1.17.0` (for Silero VAD ONNX inference)
- Net effect: removes proprietary licensed dependencies, adds MIT-licensed one.

## 8. What Changes in PRD and TDD

### PRD updates needed
- FR-030: Change "Voice Activity Detection (Cobra)" → "Voice Activity Detection"
  and remove Picovoice-specific language
- FR-031: Change "Noise Suppression (Koala)" → "Noise Suppression (null/bypass)"
  and note that denoising is disabled by default
- TC-1, TC-4, TC-10: Remove/update Picovoice-specific constraints
- A-4: Update "Cobra/Koala trimming" → "VAD trimming"
- D-1 rationale: Remove "Picovoice SDKs need a native runtime" (Silero runs
  anywhere with ONNX, but GCP is still needed for ffmpeg + Speechmatics)
- Section 6 diagram description: "Cobra → Koala → Speechmatics" → "VAD → Speechmatics"

### TDD updates needed (beyond what's already done in Section 1)
- Section 2 Architecture: References to "Cobra VAD", "Koala denoise" in component
  descriptions and data flow
- Section 4.4: `process_batch()` docstring still references Cobra/Koala errors
- Section 5 directory structure: `vad.py` → `vad/` package, `denoise.py` →
  `denoise/` package
- Section 6 Decision 4 guidance: Add VAD/Denoise interface pattern (parallel to
  ASR interface)
- Section 9: Remove `PICOVOICE_ACCESS_KEY` from GCP env vars
- Section 10: Update test descriptions for new engine-based tests

## 9. Next Steps

1. Get architectural approval (this document)
2. Proceed to `process/create-prd.md` to produce a PRD addendum
3. Proceed to `process/create-tdd.md` to update the TDD with new interfaces
4. Proceed to `process/create-issues.md` to create implementation issues
5. Execute issues (likely 1 parent with 4-5 sub-issues)
