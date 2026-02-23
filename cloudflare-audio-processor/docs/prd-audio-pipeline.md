# PRD: Audio Capture & Transcription Pipeline

## 0. Metadata

| Attribute          | Details                                        |
| :----------------- | :--------------------------------------------- |
| **Author**         | Geoff                                          |
| **Status**         | Draft                                          |
| **Priority**       | P0                                             |
| **Target Release** | TBD                                            |
| **Project**        | ubiq-capture / cloudflare-audio-processor      |

---

## 1. Problem & Opportunity (The "Why")

### The Problem

Sense and Motion is building a ubiquitous capture platform — always-on ambient
recording that turns conversations into actionable data. The phone app (uCapture)
already records audio with rich metadata and uploads it. But there is no backend
to receive, process, and organize that data. Raw ambient audio is noisy, contains
long silences, and is useless without transcription. Today, recordings land in
Google Drive as disconnected files with no processing pipeline.

### The Evidence

- The Android recorder (uCapture) is MVP-complete with 107 passing tests, a
  robust upload system, and a well-defined metadata sidecar format.
- The team has chosen Speechmatics for transcription quality, and Picovoice
  Cobra/Koala for noise suppression — both evaluated and decided.
- The existing Google Drive destination provides no processing, indexing, or
  downstream integration capability.

### The Opportunity

A working ingest-to-transcript pipeline unlocks the entire downstream vision:
action items, followups, decision capture, idea extraction, and more. None of
that is possible without clean, indexed, transcribed audio. This pipeline is the
foundational layer that everything else builds on.

Additionally, the Cloudflare (ingest/storage) + GCP (compute) architecture
pattern is reusable across future Sam projects, making this a platform
investment.

---

## 2. Key Decisions & Trade-offs (Alignment)

| # | Decision | Rationale |
| :-- | :--- | :--- |
| D-1 | **Cloudflare for ingest, storage, and indexing; GCP for compute** | Picovoice SDKs need a native runtime (can't run in CF Workers). CF provides free WAF/DDoS, cheap storage (R2 zero egress), and simple DB (D1). |
| D-2 | **MVP with platform bones** | Ship a working pipeline fast, but use the queue-driven CF↔GCP split from day one so the architecture doesn't need re-doing. |
| D-3 | **Speechmatics for Automatic Speech Recognition (ASR), behind a modular interface** | Speechmatics is the chosen engine. Abstract behind an interface so swapping to Whisper, Deepgram, etc. is a config change, not a rewrite. |
| D-4 | **Batch-oriented upload model** | Each upload is a "batch" containing one audio file, one metadata JSON, zero or more images, and zero or more text notes. All artifacts in a batch are linked. |
| D-5 | **DR-safe file naming** | File naming in R2 encodes enough information (user, batch ID, artifact type, timestamp) to reconstruct the D1 index from the R2 file listing alone. |
| D-6 | **Async processing, not real-time** | Phone uploads completed chunks (5-30 min). Processing is queue-driven and asynchronous. No streaming/real-time transcription. |
| D-7 | **Downstream triggering is in scope; downstream processing is not** | The pipeline must emit an event on completion. What consumes that event is a separate concern. |
| D-8 | **Pluggable emotion analysis, starting with Google Cloud NL; provider tagged in output** | Different emotion providers produce incompatible schemas (polarity score vs. categorical labels vs. dimensional vectors). Rather than normalising, the `provider` field is stored in the output JSON so downstream consumers can branch on it. Google Cloud NL is the starting point: cheap, native GCP, text-only, trivial to integrate. Hume AI (audio-based, highest quality) and self-hosted HuggingFace models (free, text or audio) are documented alternatives. Emotion analysis is best-effort — failure does not fail the batch. |

---

## 3. Functional Requirements (The "What")

### 3.1 Upload & Ingest

**FR-001: Upload endpoint**
The system must expose an HTTPS endpoint that accepts a multipart upload
containing one audio file, one metadata JSON, and optional image and text note
attachments.

*Acceptance Criteria:*
- Given a valid upload with audio + metadata, When the endpoint is called, Then
  all artifacts are stored and a batch ID is returned.
- Given a valid upload with audio + metadata + 3 images + 1 note, When the
  endpoint is called, Then all 5 artifacts are stored under the same batch ID.
- Given an upload missing the audio file, When the endpoint is called, Then a
  400 error is returned with a descriptive message.

**FR-002: Authentication and multi-tenant user isolation**
The upload endpoint must require authentication. The system must be architected
to support an arbitrary number of users with strict data segregation, even if
the MVP operates in a single-organization context. User isolation is enforced at
the application layer (the Cloudflare Worker is the sole entry point to R2 and
D1) rather than via separate storage buckets per user.

*Acceptance Criteria:*
- Given a request without valid credentials, When the endpoint is called, Then a
  401 error is returned.
- Given valid credentials, When the endpoint is called, Then the request is
  processed and the user identity is associated with the batch.
- Given two different authenticated users, When User A calls any endpoint, Then
  User A cannot access, list, or modify any data belonging to User B.
- Given the R2 file naming scheme (see FR-012), Then all artifacts for a user
  are stored under a user-scoped path prefix, and the Worker refuses any request
  whose authenticated user ID does not match the path prefix being accessed.
- Given the D1 index, Then all batch records include a user ID foreign key and
  all queries are scoped to the authenticated user.

*Architecture note:* A single R2 bucket with user-prefixed paths is sufficient
for this use case. Separate per-user buckets may be evaluated for regulated or
enterprise deployments but are not required here. Per-user metrics (FR-050) are
in scope to support future billing or usage-capped tiers.

**FR-003: Upload priority flag**
The upload must support an optional priority flag ("upload now") that moves the
batch to the front of the processing queue.

*Acceptance Criteria:*
- Given an upload with `priority: immediate`, When processing is queued, Then
  this batch is processed before non-priority batches.

### 3.2 Storage

**FR-010: Raw artifact storage**
All uploaded artifacts (audio, metadata, images, notes) must be stored in their
original form in R2.

*Acceptance Criteria:*
- Given a completed upload, When storage is checked, Then the original audio
  file, metadata JSON, all images, and all notes exist in R2.
- Given the stored files, When their checksums are computed, Then they match the
  originals (no corruption).

**FR-011: Processed artifact storage**
Cleaned audio and transcription output must be stored in R2 alongside the raw
artifacts.

*Acceptance Criteria:*
- Given a completed processing run, When R2 is checked, Then the cleaned audio
  file and transcript JSON exist under the same batch.

**FR-012: DR-safe file naming convention**
Files in R2 must be named such that the D1 index can be fully reconstructed
from the R2 file listing alone. The user-scoped path prefix also serves as the
primary data isolation boundary (see FR-002).

*Acceptance Criteria:*
- Given a complete loss of D1, When R2 is listed and file paths are parsed,
  Then all batch relationships (which audio, metadata, images, notes, cleaned
  audio, and transcript belong together) can be reconstructed.
- Given a file path in R2, When it is parsed, Then the user ID, batch ID,
  artifact type, and original timestamp are extractable.
- Given the Worker's access control (FR-002), Then no authenticated request can
  reach a path whose leading `{user_id}` segment differs from the caller's
  authenticated identity.

**Proposed naming scheme** (constraint for TDD — exact format is a TDD decision):
```
{user_id}/{batch_id}/{artifact_type}/{filename}
```
Where `batch_id` encodes a timestamp (e.g., `20260210-143000-PST`) and
`artifact_type` is one of: `raw-audio`, `metadata`, `images`, `notes`,
`cleaned-audio`, `transcript`.

### 3.3 Indexing

**FR-020: Batch index**
The system must maintain an index (D1) that tracks every batch and its
constituent artifacts, their storage locations, and processing status.

*Acceptance Criteria:*
- Given a completed upload, When D1 is queried, Then the batch record exists
  with references to all stored artifacts.
- Given a batch ID, When the index is queried, Then all related artifacts
  (raw audio, metadata, images, notes, cleaned audio, transcript) are returned
  with their R2 paths and processing status.

**FR-021: Processing status tracking**
Each batch must have a processing status that progresses through defined states.

*Acceptance Criteria:*
- Given a newly uploaded batch, Then its status is `uploaded`.
- Given a batch being processed, Then its status is `processing`.
- Given a successfully processed batch, Then its status is `completed`.
- Given a batch that failed processing, Then its status is `failed` with an
  error message.

**FR-022: Status query endpoint**
The system must expose an endpoint to query batch status.

*Acceptance Criteria:*
- Given a batch ID, When the status endpoint is called, Then the current
  processing status and artifact list are returned.
- Given a user ID, When the status endpoint is called with a time range, Then
  all batches for that user in that range are returned.

### 3.4 Audio Processing

**FR-030: Voice Activity Detection (Cobra)**
The system must identify speech segments in the uploaded audio and discard
non-speech portions.

*Acceptance Criteria:*
- Given a 30-minute audio file that is 80% silence, When VAD is applied, Then
  only the speech segments are passed to downstream processing.
- Given a batch where Cobra detects zero speech, Then the batch is marked
  `completed` with an empty transcript and no cleaned audio file.

**FR-031: Noise Suppression (Koala)**
The system must apply noise suppression to the speech segments identified by
Cobra.

*Acceptance Criteria:*
- Given speech segments with background noise, When Koala processes them, Then
  the output audio has reduced background noise while preserving speech
  intelligibility.

**FR-032: Transcription with speaker diarization (Speechmatics)**
The system must transcribe the cleaned audio using Speechmatics Batch API with
speaker diarization enabled.

*Acceptance Criteria:*
- Given cleaned audio, When Speechmatics processes it, Then a transcript is
  returned with speaker labels and inline timestamp markers at approximately
  15-second intervals.
- Timestamp markers are produced by post-processing the Speechmatics
  word-timestamp response: after receiving the full response, walk the word list
  and emit an inline marker (e.g. `[00:00]`, `[00:15]`, `[00:30]`) each time a
  15-second boundary is crossed. The stored transcript is human-readable text
  with embedded markers and speaker labels.
- Given a conversation between two people, When the transcript is reviewed, Then
  utterances are attributed to distinct speaker identifiers (e.g. `Speaker 1`,
  `Speaker 2`).
- Given the transcript, When it is stored, Then the full raw Speechmatics
  response is also preserved alongside the formatted text, to allow future
  reprocessing at finer granularity without re-submitting audio.

*Note on emotional/sentiment evaluation:* Neither Speechmatics Batch API nor
Koala provide per-utterance sentiment or emotion metadata as standard output.
Koala is a noise suppressor only. Speechmatics returns transcription and
diarization but no affective analysis. Prosodic or sentiment analysis would
require a separate post-processing pass (e.g. LLM-based) applied to the stored
transcript. This is out of scope for MVP; preserving the full raw Speechmatics
response (above) ensures the data is available for it in future.

**FR-033: Modular ASR interface**
The transcription engine must be accessed through an abstraction layer.

*Acceptance Criteria:*
- Given a new ASR engine implementation, When it conforms to the interface, Then
  it can replace Speechmatics with a configuration change and no code changes
  to the pipeline.

**FR-034: Pluggable emotion/sentiment analysis**
After transcription, the system must apply an emotion/sentiment analysis pass to
the transcript and include the results as structured metadata stored alongside
the transcript in R2. The initial provider is Google Cloud Natural Language API
(text-based sentiment).

*Acceptance Criteria:*
- Given a completed transcript with speech segments, When the emotion analysis
  step runs, Then each sentence-level segment is annotated with
  emotion/sentiment metadata from the configured provider.
- Given the stored `emotion.json`, Then a `provider` field identifies which
  analysis engine produced the data, allowing downstream consumers to interpret
  the provider-specific `analysis` object accordingly.
- Given a segment, Then the emotion record includes: `speaker`,
  `start_seconds`, `end_seconds`, `text`, `provider`, `provider_version`, and
  `analysis` (provider-specific schema).
- Given zero speech segments or an empty transcript, Then the emotion step is
  skipped and `emotion.json` contains `{ "provider": "...", "segments": [] }`.
- Given a failure in the emotion analysis step, Then the failure is logged and
  the batch is still marked `completed` — emotion analysis is best-effort and
  does not block the primary transcript artifact. The `transcript_emotion_path`
  in D1 is left null.

**FR-035: Modular emotion provider interface**
The emotion analysis engine must be accessed through an abstraction layer,
following the same pattern as FR-033 for ASR. The `provider` field in the
output JSON is the key that allows downstream consumers to interpret the
varying schemas produced by different providers.

*Acceptance Criteria:*
- Given a new emotion provider implementation, When it conforms to the
  interface, Then it can replace or supplement the current provider with a
  configuration change and no code changes to the pipeline.
- The interface accepts: a list of transcript segments (speaker, timestamps,
  text). It does not require the audio file for text-based providers, but may
  optionally receive the cleaned audio path for audio-based providers (e.g.
  Hume AI, audeering).
- The interface returns a JSON envelope with: `provider`, `provider_version`,
  `analyzed_at` (ISO 8601), and `segments` (array of per-segment results).
- The `analysis` object schema is provider-specific and versioned by the
  `provider` field. Known schemas:
  - `google-cloud-nl`: `{ "score": float, "magnitude": float }` — score
    -1.0 (negative) to +1.0 (positive); magnitude is intensity regardless
    of polarity
  - `hume-ai`: `{ "prosody": { [emotion_name]: float } }` — 48-dimensional
    continuous emotion space from audio waveform
  - `j-hartmann-distilroberta`: `{ "emotion": string, "confidence": float }`
    — one of: anger, disgust, fear, joy, neutral, sadness, surprise
  - `audeering-wav2vec2`: `{ "arousal": float, "dominance": float,
    "valence": float }` — continuous dimensional scores from audio

### 3.5 Orchestration

**FR-040: Queue-driven processing**
Upload completion must trigger processing via a queue mechanism, not synchronous
in the upload request.

*Acceptance Criteria:*
- Given a completed upload, When the Worker returns a response to the client,
  Then processing has not yet started (response is immediate).
- Given a queued batch, When a processing worker is available, Then the batch is
  picked up and processed.

**FR-041: Completion event and downstream subscribers**
The system must emit an event when processing completes. The uCapture Android
app is the primary initial subscriber: it uses this event to mark a recording
as processed and make the transcript available via a tap on the upload history.

*Acceptance Criteria:*
- Given a batch that finishes processing (success or failure), Then an event is
  emitted containing the batch ID, user ID, status, and R2 paths of all
  artifacts.
- Given a downstream consumer authenticated as User A, When it subscribes to
  the event stream, Then it receives events only for User A's batches (events
  are user-scoped).
- The event payload must include: `batch_id`, `user_id`, `status`
  (`completed` | `failed`), `artifact_paths` (keyed by artifact type), and
  `recording_started_at` (so the client can correlate the event to a local
  recording session).
- Given a `completed` event, When the Android app receives it, Then the app can
  present a "transcript available" affordance on the corresponding upload
  history entry without re-polling the backend.
- Given a `failed` event, When the Android app receives it, Then the app
  indicates the processing failure on the history entry so the user is aware.
- The event stream must deliver events to the Android app even if the phone
  was offline when the event was published (e.g. battery dead, no network).
  Delivery is guaranteed via MQTT persistent sessions (`clean_session=false`,
  QoS 1) — see TDD section 4.3 for implementation requirements.

**FR-042: Audio durability and retry on failure**
Audio must never be lost. The system defines a clear durability contract between
the Android client and the backend.

*Upload safety (Android-side responsibility — stated here for system clarity):*
- Given an upload that fails for any reason (network, server error, auth), Then
  the audio file must remain on-device and be re-queued for upload. The Android
  app must not delete any audio file until it has received a confirmed `202
  Accepted` response from the ingest endpoint (i.e. the file is durably in R2).

*Backend durability:*
- Given audio stored in R2, When any downstream processing step fails (VAD,
  noise suppression, transcription), Then the raw audio in R2 is unaffected.
  Processing failures must never delete or overwrite the raw audio.
- Given a batch in `failed` state, Then the batch can be reprocessed by
  re-enqueuing it without re-uploading the audio. All raw artifacts remain
  available in R2 for retry.
- Given a batch in `failed` state, Then an operator or automated system can
  trigger reprocessing by queuing the batch_id for re-processing.

*Retry:*
- Given a transient failure (network error, Speechmatics timeout, GCP error),
  When the failure occurs, Then the batch is re-queued with exponential backoff.
- Given 3 consecutive failures for a batch, Then the batch is marked `failed`,
  no further automatic retries are attempted, and a `failed` completion event
  is emitted (FR-041) so downstream consumers are notified.

### 3.6 Observability (MVP level)

**FR-050: Processing metrics and observability**
The system must log key metrics for each batch and expose aggregated metrics for
operational, performance, and cost visibility. These form the basis for a future
cost and performance dashboard (costs are expected to scale with usage — see
TC-11).

*Per-batch metrics (logged on completion):*
- Upload artifact sizes: raw audio bytes, metadata bytes, total multipart size
- Audio durations: raw input (seconds), speech-only segment submitted to
  Speechmatics (seconds), and the Cobra speech ratio (speech / total)
- Audio size before and after Koala (bytes) to track denoise compression delta
- Processing wall-clock time per stage: transcode, Cobra VAD, Koala denoise,
  Speechmatics API wait, post-processing (timestamp formatting, storage writes)
- End-to-end latency: time from upload timestamp to `completed` or `failed`
  status
- Queue wait time: delta from upload-complete to processing-start
- Speechmatics job ID (for invoice reconciliation) and audio duration as
  reported by Speechmatics
- Speechmatics cost estimate for the batch (audio_duration_hours × rate,
  logged at submission time)
- Retry count (0 if first attempt succeeded; records total attempts on failure)
- Final status and, if `failed`, the failing stage and error message

*System-wide / aggregated metrics:*
- Batches processed per hour and per day (throughput)
- Error rate broken down by stage: upload validation, VAD, denoise, ASR,
  post-processing
- R2 storage consumed: raw audio total, cleaned audio total, transcript total —
  reported per user and system-wide
- Cumulative Speechmatics API cost: rolling 30-day window, per user, and
  system-wide total
- Queue depth at any given time (backlog of unprocessed or retrying batches)
- Active concurrent GCP Cloud Run processing jobs
- D1 read/write latency percentiles (p50, p95) to detect index degradation
- Per-user batch count and audio hours processed (for capacity planning and
  future per-user billing)

---

## 4. Non-Goals (Out of Scope)

| # | Non-Goal | Notes |
| :-- | :--- | :--- |
| NG-1 | **Downstream AI processing** | Action items, followups, idea extraction, summarization — all out of scope. This PRD stops at "clean audio + transcript + metadata stored and indexed." |
| NG-2 | **Real-time / streaming transcription** | Processing is async batch only. |
| NG-3 | **Standalone image/note processing** | Images and notes are stored and indexed as batch metadata. No OCR, image analysis, or NLP is performed on them. |
| NG-4 | **Speaker identification** | Diarization assigns anonymous speaker labels (Speaker 1, Speaker 2). Mapping those to real identities (contact names, team members) is out of scope — that's downstream AI. |
| NG-5 | **Web UI** | No user-facing interface for browsing transcripts, playback, or search. API-only. |
| NG-6 | **Billing and per-user metering** | No per-user billing, invoicing, or payment processing in MVP. The architecture is explicitly designed for multi-tenant use (user-scoped data, user-scoped event streams, per-user metrics in FR-050). Cost observability per user is in scope; charging users for it is not. |
| NG-7 | **Android app changes** | The uCapture app modifications to target this endpoint instead of Google Drive are a separate effort (though the upload format defined here is informed by the existing sidecar format). |

---

## 5. Technical Constraints & Assumptions

| # | Constraint |
| :-- | :--- |
| TC-1 | Picovoice Cobra and Koala require a native runtime (Python/C). They cannot run in Cloudflare Workers. |
| TC-2 | Cloudflare Workers have a 30-second CPU time limit (paid plan). Audio DSP exceeds this. |
| TC-3 | The Android app currently produces AAC/M4A at 44.1 kHz mono (64-256 kbps). The pipeline must accept this format. |
| TC-4 | Picovoice SDKs require 16 kHz, single-channel, 16-bit PCM input (confirmed via Koala Python demo docs and shared `pv_sample_rate()`). Audio must be transcoded on GCP before Cobra/Koala processing — not on the phone, to minimize battery consumption (44.1 kHz AAC uses hardware-accelerated encoding on Android). |
| TC-5 | Speechmatics Batch API accepts multiple formats including M4A. Cleaned audio format (post-Koala) must be compatible. |
| TC-6 | R2 has no egress fees. GCP Cloud Run will need to pull raw audio from R2 and push cleaned audio back. |
| TC-7 | D1 is on a paid plan. The 10GB storage limit applies to the paid tier; metadata and index only — not audio content. This is sufficient for the expected data volume at scale. |
| TC-8 | ~10 users recording up to 24x7. Cobra/Koala will substantially reduce stored audio volume, but ingest must handle the full raw volume. |
| TC-9 | Upload chunks are 5-30 minutes of audio. At 128 kbps AAC, that's ~5-22 MB per chunk. |
| TC-10 | Picovoice requires an access key (licensed per platform). Server-side processing needs a server/Linux license. |
| TC-11 | There is no requirement to remain within the free tier of any provider (Cloudflare, GCP, Speechmatics, Picovoice). Costs are expected to scale with usage. Cost management is handled through observability (FR-050), not through architectural constraints that sacrifice capability. |

### Assumptions

| # | Assumption |
| :-- | :--- |
| A-1 | The existing uCapture metadata sidecar format (JSON with recording, location, and calendar sections) will be extended to include image and note references rather than replaced. |
| A-2 | Images will be uploaded as binary attachments (JPEG/PNG) alongside the audio, not embedded in the metadata JSON. |
| A-3 | Text notes will be included in the metadata JSON sidecar as a `notes` array (each entry: `timestamp` ISO 8601 + `text` string), alongside existing `recording`, `location`, and `calendar` keys. Images are binary and go as separate files in the multipart upload. |
| A-4 | Speechmatics pricing is per hour of audio submitted. Cobra/Koala trimming directly reduces transcription cost. |

---

## 6. Design & Visuals

See companion diagrams:
- [`prd-audio-pipeline-figure1.mmd`](prd-audio-pipeline-figure1.mmd) — end-to-end sequence diagram
- [`tdd-audio-pipeline-figure1.mmd`](tdd-audio-pipeline-figure1.mmd) — component architecture diagram

The sequence diagram shows the end-to-end flow:
1. Phone uploads batch to Cloudflare Worker
2. Worker stores artifacts in R2, indexes in D1, queues processing
3. GCP Cloud Run picks up the job, pulls audio from R2
4. Cobra → Koala → Speechmatics processing chain
5. Emotion analysis pass (Google Cloud NL by default, best-effort)
6. Results written back to R2, D1 updated
7. Completion event emitted; Android app marks recording as processed
