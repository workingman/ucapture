# QA Findings Log — Audio Pipeline

### F-001: R2 path mismatch between Worker and GCP processor
- **Layer:** RENDER
- **Severity:** blocking
- **Domain:** storage/integration
- **Observed:** Worker stores raw audio at `{user_id}/{batch_id}/raw-audio/recording.m4a` (via `buildAudioPath()` in `src/storage/r2.ts:113`). GCP pipeline fetches from `{user_id}/{batch_id}/audio/recording.m4a` (in `audio_processor/pipeline.py:268`). The artifact type segment differs: `raw-audio` vs `audio`.
- **Expected:** Both sides use the same R2 path convention per TDD Section 3.1: `{user_id}/{batch_id}/raw-audio/{filename}` (FR-012)
- **Root cause:** GCP pipeline hardcodes `/audio/` instead of `/raw-audio/` when constructing the fetch key. Also affects zero-speech handler at `pipeline.py:501`.
- **Cluster:** C-001
- **Issue:** #49
- **Status:** verified

### F-002: StatusResponse metrics are flat instead of nested under `metrics` key
- **Layer:** RENDER
- **Severity:** substantive
- **Domain:** worker/api
- **Observed:** `GET /v1/status/:batch_id` returns `speech_duration_seconds`, `speech_ratio` as top-level fields in the JSON response. `speechmatics_cost_estimate` is not included at all.
- **Expected:** TDD Section 4.1 specifies a nested `metrics` object: `{ "metrics": { "speech_duration_seconds": 420.5, "speech_ratio": 0.23, "speechmatics_cost_estimate": 0.63 } }` (FR-022, FR-050)
- **Root cause:** `StatusResponse` interface in `src/types/api.ts` was designed with flat fields. The `buildStatusResponse()` in `src/handlers/status.ts` passes batch row columns directly without nesting.
- **Cluster:** C-002
- **Issue:** #50
- **Status:** verified

### F-003: Batch list returns full StatusResponse instead of summary objects
- **Layer:** RENDER
- **Severity:** substantive
- **Domain:** worker/api
- **Observed:** `GET /v1/batches` returns an array of full `StatusResponse` objects (20+ fields each, including all metrics and error fields) for every batch in the list.
- **Expected:** TDD Section 4.1 specifies a lightweight summary per batch: `{ "batch_id", "status", "recording_started_at", "uploaded_at" }`. The list endpoint should return summaries, not full records. (FR-022)
- **Root cause:** `batchRowToSummary()` in `src/handlers/batches.ts` maps to the same `StatusResponse` type used by the single-batch endpoint instead of a dedicated `BatchSummary` type.
- **Cluster:** C-003
- **Issue:** #51
- **Status:** verified

### F-004: CompletionEvent missing `recording_started_at` field
- **Layer:** RENDER
- **Severity:** blocking
- **Domain:** gcp/pipeline
- **Observed:** `_build_completion_event()` in `pipeline.py` builds the event with `batch_id`, `user_id`, `status`, `artifact_paths`, `published_at`, and optional `error_message`. It does NOT include `recording_started_at`.
- **Expected:** TDD Section 4.3 requires `recording_started_at` (ISO 8601 UTC) "so the client can correlate the event to a local recording session." FR-041 lists it as a required payload field. The Worker's `/internal/publish-event` handler validates this field as required — so this call will fail at runtime.
- **Root cause:** `_build_completion_event()` was not passed the `recording_started_at` value, and the field was omitted from the event dict.
- **Cluster:** C-004
- **Issue:** #52
- **Status:** verified

### F-005: Download endpoint missing `transcript_emotion` artifact type
- **Layer:** RENDER
- **Severity:** cosmetic
- **Domain:** worker/api
- **Observed:** `ARTIFACT_TYPE_COLUMNS` in `src/handlers/download.ts` allows: `raw_audio`, `cleaned_audio`, `transcript_formatted`, `transcript_raw`, `metadata`. The `transcript_emotion` type is not listed.
- **Expected:** TDD Section 4.1 download endpoint lists the same 5 types (so this matches TDD). However, emotion.json is a stored artifact (FR-034) that has no download path — it can only be discovered via the status endpoint's `artifacts.transcript_emotion` field.
- **Root cause:** TDD didn't list `transcript_emotion` as a download type. This is a TDD gap rather than an implementation bug.
- **Cluster:** C-005
- **Issue:** #53
- **Status:** verified

### F-007: Android app metadata format does not match Worker upload API contract
- **Layer:** FUNCTION
- **Severity:** blocking
- **Domain:** integration/android-worker
- **Observed:** Android app sidecar JSONs use camelCase fields (`startTime`, `endTime`, `durationSeconds`, `fileSizeBytes`, `chunkNumber`, `sessionId`, `md5Hash`) with no `device` object, no `audio_format`, `sample_rate`, `channels`, or `bitrate` fields.
- **Expected:** Worker upload endpoint validates metadata against a strict schema requiring snake_case fields: `recording.started_at`, `recording.ended_at`, `recording.duration_seconds`, `recording.audio_format`, `recording.sample_rate`, `recording.channels`, `recording.bitrate`, `recording.file_size_bytes`, and a `device` object with `model`, `os_version`, `app_version`.
- **Root cause:** Android app and Worker were developed independently with no shared schema contract. The Android app predates the Worker API design.
- **Resolution options:** (a) Update Android app to emit the Worker's expected format, (b) Add a transform/adapter layer in the Worker to accept both formats, (c) Define a shared schema and update both sides.
- **Cluster:** C-007
- **Issue:** #61
- **Status:** open

### F-006: StatusResponse includes undocumented fields not in TDD contract
- **Layer:** RENDER
- **Severity:** cosmetic
- **Domain:** worker/api
- **Observed:** `StatusResponse` includes fields not present in TDD 4.1: `priority`, `recording_ended_at`, `processing_started_at`, `processing_wall_time_seconds`, `queue_wait_time_seconds`, `raw_audio_size_bytes`, `raw_audio_duration_seconds`. These are additive (won't break clients) but diverge from the documented contract.
- **Expected:** Response shape should match TDD 4.1 or TDD should be updated to document the additional fields.
- **Root cause:** StatusResponse was designed to expose all D1 columns rather than curating the response to match the TDD contract.
- **Cluster:** C-006
- **Issue:** #53
- **Status:** verified

### F-008: Retry decorator retries permanent failures (NoSuchKey, corrupt input)
- **Layer:** POLISH
- **Severity:** substantive
- **Domain:** gcp/resilience
- **Observed:** `retry_with_backoff` in `audio_processor/utils/retry.py` catches all `Exception` types equally. R2 `NoSuchKey` errors, corrupt audio `TranscodeError`, and missing VAD model `VADError` are all retried 3 times with exponential backoff (1+2+4 = 7s wasted).
- **Expected:** Only transient failures (network timeouts, 429, 503) should be retried. Permanent failures should fail fast. TDD Decision 6 specifies retry for "transient failures."
- **Root cause:** Decorator is one-size-fits-all without exception classification.
- **Cluster:** C-008
- **Issue:** #54
- **Status:** open

### F-009: Retry count never propagated to completion events
- **Layer:** POLISH
- **Severity:** substantive
- **Domain:** gcp/observability
- **Observed:** `pipeline.py` initializes `retry_count = 0` and attempts to read `getattr(exc, "_retry_count", 0)` from exceptions, but the retry decorator never sets `_retry_count` on raised exceptions. Completion events always report 0 retries.
- **Expected:** TDD specifies `retry_count` in D1 schema and status response. Should reflect actual retry attempts.
- **Root cause:** Retry decorator doesn't annotate exceptions with attempt count before re-raising.
- **Cluster:** C-008
- **Issue:** #54
- **Status:** open

### F-010: VAD threshold hardcoded at 0.5, not configurable
- **Layer:** POLISH
- **Severity:** substantive
- **Domain:** gcp/vad
- **Observed:** `SileroVADEngine` in `audio_processor/audio/vad/silero.py` uses `DEFAULT_THRESHOLD = 0.5`. The engine accepts a threshold parameter but `get_vad_engine("silero")` in the pipeline doesn't pass one. No environment variable or config exposes this.
- **Expected:** FP-001 spec says VAD should have pluggable configuration. Threshold should be configurable via environment variable.
- **Root cause:** Registry returns engine with default config; no config passthrough mechanism.
- **Cluster:** C-009
- **Issue:** #55
- **Status:** open

### F-011: Partial audio frames at end of input silently discarded by VAD
- **Layer:** POLISH
- **Severity:** substantive
- **Domain:** gcp/vad
- **Observed:** ONNX inference loop in `silero.py` processes only full 512-sample frames. Remaining samples (up to 31ms of audio) are excluded from speech detection. If audio ends mid-word, the final word may not be detected in VAD segments.
- **Expected:** Partial frames should be zero-padded and processed, or documented as a known limitation.
- **Root cause:** ONNX model requires exactly 512-sample frames; no padding strategy for tail.
- **Cluster:** C-009
- **Issue:** #55
- **Status:** open

### F-012: Graceful shutdown has no timeout — risks SIGKILL by Cloud Run
- **Layer:** POLISH
- **Severity:** substantive
- **Domain:** gcp/lifecycle
- **Observed:** `main.py` SIGTERM handler calls `consumer.stop()` and waits indefinitely for the current batch to finish. Cloud Run sends SIGKILL after ~30 seconds. If a batch is polling Speechmatics (which can take minutes), shutdown becomes ungraceful SIGKILL.
- **Expected:** Shutdown should have a timeout (e.g., 25 seconds) to ensure clean exit before Cloud Run's SIGKILL deadline.
- **Root cause:** No timeout on `stop_event.wait()` in shutdown handler.
- **Cluster:** C-010
- **Issue:** #56
- **Status:** open

### F-013: ffmpeg hangs 120s on corrupt/truncated audio instead of failing fast
- **Layer:** POLISH
- **Severity:** substantive
- **Domain:** gcp/transcode
- **Observed:** `transcode.py` runs ffmpeg with a 120-second timeout. Corrupt or truncated M4A files may cause ffmpeg to hang for the full duration. 10 queued corrupt batches = 20 minutes of wasted processing time.
- **Expected:** Corrupt audio should be detected quickly. Consider an ffprobe pre-check or a shorter initial timeout with retry.
- **Root cause:** Single large timeout applies to all ffmpeg operations regardless of expected duration.
- **Cluster:** C-011
- **Issue:** #57
- **Status:** open

### F-014: Retry attempts not logged with attempt number or sleep duration
- **Layer:** POLISH
- **Severity:** cosmetic
- **Domain:** gcp/observability
- **Observed:** `retry_with_backoff` decorator in `utils/retry.py` sleeps between retries but doesn't log which attempt is being retried or the backoff delay.
- **Expected:** Per error-handling standards, retried failures should be logged with attempt number for debugging.
- **Root cause:** No logging statements in retry loop.
- **Cluster:** C-012
- **Issue:** #58
- **Status:** open

### F-015: Error stage inference uses timing-based heuristic instead of exception type
- **Layer:** POLISH
- **Severity:** cosmetic
- **Domain:** gcp/observability
- **Observed:** `_determine_error_stage()` in `pipeline.py` infers which stage failed by checking for missing keys in `stage_timings` dict. Works but is fragile if context manager exception handling changes.
- **Expected:** Error stage could be determined directly from exception type (e.g., `TranscodeError` → 'transcode', `VADError` → 'vad').
- **Root cause:** Design choice; functional but unintuitive.
- **Cluster:** C-012
- **Issue:** #58
- **Status:** open

### F-016: D1Client creates new HTTP client per request instead of reusing
- **Layer:** POLISH
- **Severity:** cosmetic
- **Domain:** gcp/performance
- **Observed:** Each D1 operation in `d1_client.py` creates and destroys an `httpx.AsyncClient()` via context manager. A single batch processes 4+ D1 operations, each with new connection overhead.
- **Expected:** A shared client with connection pooling would reduce overhead.
- **Root cause:** Per-call client instantiation pattern.
- **Cluster:** C-013
- **Issue:** #59
- **Status:** open

### F-017: Test coverage gaps across Worker and GCP test suites
- **Layer:** POLISH
- **Severity:** cosmetic
- **Domain:** testing
- **Observed:** Multiple untested paths identified: (a) Worker: malformed Bearer format, empty token, cross-user download access, invalid artifact_type; (b) GCP: emotion analysis failure mid-pipeline, consumer dispatch exception handling, graceful shutdown, ASR retry exhaustion with error_stage, R2 partial write failures.
- **Expected:** Critical error paths should have test coverage for v0.9.
- **Root cause:** Tests written for happy path and basic error cases; edge cases not covered.
- **Cluster:** C-014
- **Issue:** #60
- **Status:** open
