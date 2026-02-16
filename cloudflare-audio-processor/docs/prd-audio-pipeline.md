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
| D-3 | **Speechmatics for ASR, behind a modular interface** | Speechmatics is the chosen engine. Abstract behind an interface so swapping to Whisper, Deepgram, etc. is a config change, not a rewrite. |
| D-4 | **Batch-oriented upload model** | Each upload is a "batch" containing one audio file, one metadata JSON, zero or more images, and zero or more text notes. All artifacts in a batch are linked. |
| D-5 | **DR-safe file naming** | File naming in R2 encodes enough information (user, batch ID, artifact type, timestamp) to reconstruct the D1 index from the R2 file listing alone. |
| D-6 | **Async processing, not real-time** | Phone uploads completed chunks (5-30 min). Processing is queue-driven and asynchronous. No streaming/real-time transcription. |
| D-7 | **Downstream triggering is in scope; downstream processing is not** | The pipeline must emit an event on completion. What consumes that event is a separate concern. |

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

**FR-002: Authentication**
The upload endpoint must require authentication to prevent unauthorized uploads.

*Acceptance Criteria:*
- Given a request without valid credentials, When the endpoint is called, Then a
  401 error is returned.
- Given valid credentials, When the endpoint is called, Then the request is
  processed and the user identity is associated with the batch.

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
from the R2 file listing alone.

*Acceptance Criteria:*
- Given a complete loss of D1, When R2 is listed and file paths are parsed,
  Then all batch relationships (which audio, metadata, images, notes, cleaned
  audio, and transcript belong together) can be reconstructed.
- Given a file path in R2, When it is parsed, Then the user ID, batch ID,
  artifact type, and original timestamp are extractable.

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
  returned with word-level timestamps, confidence scores, and speaker labels.
- Given a conversation between two people, When the transcript is reviewed, Then
  utterances are attributed to distinct speaker identifiers.
- Given the transcript, When it is stored, Then the full Speechmatics response
  is preserved (not just plain text), including word-level timestamps,
  confidence scores, and speaker labels.

**FR-033: Modular ASR interface**
The transcription engine must be accessed through an abstraction layer.

*Acceptance Criteria:*
- Given a new ASR engine implementation, When it conforms to the interface, Then
  it can replace Speechmatics with a configuration change and no code changes
  to the pipeline.

### 3.5 Orchestration

**FR-040: Queue-driven processing**
Upload completion must trigger processing via a queue mechanism, not synchronous
in the upload request.

*Acceptance Criteria:*
- Given a completed upload, When the Worker returns a response to the client,
  Then processing has not yet started (response is immediate).
- Given a queued batch, When a processing worker is available, Then the batch is
  picked up and processed.

**FR-041: Completion event**
The system must emit an event when processing completes, to trigger downstream
workflows.

*Acceptance Criteria:*
- Given a batch that finishes processing (success or failure), Then an event is
  emitted containing the batch ID, user ID, status, and R2 paths of all
  artifacts.
- Given a downstream consumer, When it subscribes to completion events, Then it
  receives events for all completed batches.

**FR-042: Retry on transient failure**
Transient processing failures must be retried automatically.

*Acceptance Criteria:*
- Given a transient failure (network error, Speechmatics timeout), When the
  failure occurs, Then the batch is re-queued with exponential backoff.
- Given 3 consecutive failures for a batch, Then the batch is marked `failed`
  and no further retries are attempted.

### 3.6 Observability (MVP level)

**FR-050: Processing metrics**
The system must log key metrics for each batch.

*Acceptance Criteria:*
- Given a processed batch, When logs are checked, Then the following are
  recorded: upload size, Cobra speech ratio (% of audio that was speech),
  processing duration per stage, Speechmatics job ID, and final status.

---

## 4. Non-Goals (Out of Scope)

| # | Non-Goal | Notes |
| :-- | :--- | :--- |
| NG-1 | **Downstream AI processing** | Action items, followups, idea extraction, summarization — all out of scope. This PRD stops at "clean audio + transcript + metadata stored and indexed." |
| NG-2 | **Real-time / streaming transcription** | Processing is async batch only. |
| NG-3 | **Standalone image/note processing** | Images and notes are stored and indexed as batch metadata. No OCR, image analysis, or NLP is performed on them. |
| NG-4 | **Speaker identification** | Diarization assigns anonymous speaker labels (Speaker 1, Speaker 2). Mapping those to real identities (contact names, team members) is out of scope — that's downstream AI. |
| NG-5 | **Web UI** | No user-facing interface for browsing transcripts, playback, or search. API-only. |
| NG-6 | **Multi-tenant / billing** | Single-org system. All users belong to one organization. |
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
| TC-7 | D1 has a 10GB storage limit (paid plan). Metadata and index only — not audio content. |
| TC-8 | ~10 users recording up to 24x7. Cobra/Koala will substantially reduce stored audio volume, but ingest must handle the full raw volume. |
| TC-9 | Upload chunks are 5-30 minutes of audio. At 128 kbps AAC, that's ~5-22 MB per chunk. |
| TC-10 | Picovoice requires an access key (licensed per platform). Server-side processing needs a server/Linux license. |

### Assumptions

| # | Assumption |
| :-- | :--- |
| A-1 | The existing uCapture metadata sidecar format (JSON with recording, location, and calendar sections) will be extended to include image and note references rather than replaced. |
| A-2 | Images will be uploaded as binary attachments (JPEG/PNG) alongside the audio, not embedded in the metadata JSON. |
| A-3 | Text notes will be included in the metadata JSON sidecar as a `notes` array (each entry: `timestamp` ISO 8601 + `text` string), alongside existing `recording`, `location`, and `calendar` keys. Images are binary and go as separate files in the multipart upload. |
| A-4 | Speechmatics pricing is per hour of audio submitted. Cobra/Koala trimming directly reduces transcription cost. |

---

## 6. Design & Visuals

See companion diagram: [`flow-audio-pipeline.mmd`](flow-audio-pipeline.mmd)

The diagram shows the end-to-end flow:
1. Phone uploads batch to Cloudflare Worker
2. Worker stores artifacts in R2, indexes in D1, queues processing
3. GCP Cloud Run picks up the job, pulls audio from R2
4. Cobra → Koala → Speechmatics processing chain
5. Results written back to R2, D1 updated
6. Completion event emitted for downstream consumers
