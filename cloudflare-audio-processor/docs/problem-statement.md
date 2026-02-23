# Problem Statement: Audio Capture & Transcription Pipeline

## Metadata

- **Author:** Geoff
- **Date:** 2026-02-22
- **Type:** CREATE (Greenfield)
- **Status:** Draft

---

## 1. The Problem

Sense and Motion is building a ubiquitous capture platform — always-on ambient
recording that turns conversations into actionable data. The Android app
(uCapture) already records audio with rich metadata and uploads chunks, but
recordings land in Google Drive as disconnected files with no processing. Raw
ambient audio is noisy, contains long silences, and is useless without
transcription. There is no backend to receive, validate, process, index, or
surface that data.

**Who experiences it:**
- Primary: Sense and Motion's own team as early internal users (~10 people,
  recording up to continuously)
- Future: external users of the ubiq-capture platform

**Cost of not solving:**
- The entire downstream vision — action items, decision capture, idea
  extraction, followup generation — is blocked. Without clean, indexed,
  transcribed audio, none of that is possible. uCapture recordings are
  currently inert data that cannot be acted on.

**Evidence:**
- uCapture (Android) is MVP-complete: 107 passing tests, robust upload system,
  well-defined metadata sidecar format. The client-side is done; the backend
  does not exist.
- Transcription engine (Speechmatics) and audio processing stack (Picovoice
  Cobra + Koala) have been evaluated and chosen.
- Current Google Drive destination provides no processing, indexing, or
  integration capability.

---

## 2. Success Criteria

**Quantitative:**
- Every batch uploaded by uCapture results in a transcript stored in R2 and
  indexed in D1 within a reasonable processing window (async, not real-time)
- Cobra/Koala trimming reduces audio submitted to Speechmatics by the silence
  fraction (cost reduction proportional to speech ratio)
- Zero audio lost: any processing failure leaves raw R2 artifacts intact and
  re-processable
- All batches for a user queryable by batch ID or time range via status endpoint

**Qualitative:**
- The pipeline is the foundational layer that downstream AI features (action
  items, followups, etc.) can build on without needing to revisit this work
- The Cloudflare + GCP architecture pattern is clean enough to reuse across
  future Sense and Motion projects
- A failed batch can be diagnosed and reprocessed by an operator without
  touching the database or storage directly

---

## 3. Scope

**MVP (Must-Have):**
- HTTPS upload endpoint (multipart: audio + metadata JSON + optional images +
  optional notes), authenticated, returns batch ID
- Multi-tenant user isolation: user-scoped R2 paths, D1 records, Worker-level
  access enforcement
- Raw artifact storage in R2 with DR-safe naming (D1 reconstructable from R2
  listing alone)
- D1 batch index with processing status lifecycle
  (`uploaded` → `processing` → `completed` | `failed`)
- Status query endpoint (by batch ID and by user + time range)
- Queue-driven async processing (CF Queue → GCP Cloud Run)
- GCP processing chain: M4A → 16kHz PCM transcode → Cobra VAD → Koala denoise
  → Speechmatics Batch API
- Transcript stored as formatted text with inline `[00:15]` timestamp markers
  at ~15s intervals, plus raw Speechmatics response preserved alongside it
- Speaker diarization (anonymous labels: Speaker 1, Speaker 2)
- Modular ASR interface (swap Speechmatics without pipeline changes)
- Upload priority flag (`priority: immediate`)
- Completion event emitted on success or failure, user-scoped, with Android app
  as primary subscriber
- Audio durability contract: raw R2 artifacts never deleted on failure;
  failed batches re-processable without re-upload
- Retry with exponential backoff (3 attempts before `failed`)
- Observability: per-batch metrics (sizes, durations, cost estimates, latency,
  retry count) and system-wide aggregates (throughput, error rates, queue depth,
  Speechmatics cost rolling 30-day, per-user stats)

**Excluded (Explicitly Out of Scope):**
- Downstream AI processing (action items, followups, summarization, idea
  extraction) — this pipeline stops at "clean audio + transcript + indexed"
- Real-time / streaming transcription
- OCR, image analysis, or NLP on uploaded images and notes
- Named speaker identification (diarization labels are anonymous)
- Web UI for browsing transcripts or playback
- Per-user billing, invoicing, or payment processing
- Android app changes to target this endpoint (separate workstream, though the
  upload format defined here is informed by the existing sidecar)

**Future Enhancements:**
- Downstream AI layer consuming completion events (action items, decisions,
  followups)
- Android transcript viewer and "transcript available" tap affordance
- Sentiment/emotion analysis as a separate post-processing pass on stored
  transcripts
- Per-user bucket isolation for regulated or enterprise deployments
- Per-user billing based on audio hours processed (FR-050 metrics provide the
  data foundation)
- Named speaker identification via voice profile matching

---

## 4. Constraints

- **Technical:**
  - Picovoice Cobra and Koala require a native runtime (Python/C); cannot run
    in Cloudflare Workers
  - Cloudflare Workers have a 30-second CPU limit; audio DSP exceeds this
    (hence GCP Cloud Run for processing)
  - Android app produces AAC/M4A at 44.1 kHz mono; Picovoice SDKs require
    16 kHz single-channel 16-bit PCM — transcode happens on GCP, not the phone
  - Upload chunks are 5–30 minutes of audio, ~5–22 MB per chunk at 128 kbps
  - Speechmatics Batch API accepts M4A; cleaned audio format (post-Koala) must
    also be compatible
  - Picovoice requires a server/Linux access key license for server-side use

- **Budget:** No constraint to remain within the free tier of any provider
  (Cloudflare, GCP, Speechmatics, Picovoice). Costs scale with usage; managed
  via FR-050 observability metrics, not architectural sacrifice.

- **Timeline:** No fixed deadline (P0 priority, ship when ready)

- **Compliance:** No formal compliance requirements for MVP. Multi-tenant data
  isolation is implemented as a best-practice architecture choice, not driven by
  a specific regulation.

---

## 5. Risks

| Risk                                       | Likelihood | Impact | Mitigation                                                                                     |
| :----------------------------------------- | :--------- | :----- | :--------------------------------------------------------------------------------------------- |
| Speechmatics cost scales faster than value | Med        | High   | Cobra/Koala reduce submitted audio volume; FR-050 tracks cost per batch and rolling 30-day     |
| Picovoice licensing cost at scale          | Med        | Med    | Per-platform license model; track API calls via FR-050; modular ASR interface allows swap-out  |
| GCP Cloud Run cold-start creates queue lag | Med        | Med    | Use min-instances or keep-warm configuration; queue wait time tracked in FR-050               |
| D1 storage grows unexpectedly              | Low        | Med    | Metadata/index only (no audio); 10GB paid tier is substantial; monitor via aggregated metrics  |
| Audio corruption or loss during processing | Low        | High   | FR-042 durability contract: raw R2 artifacts immutable through processing; audit via checksums |
| uCapture upload format mismatch            | Low        | High   | Upload format defined collaboratively with Android sidecar format; acceptance tests cover this  |
| Speechmatics API availability / rate limits | Low       | Med    | Retry with backoff (FR-042); modular ASR interface allows fallback engine                      |

---

## 6. Dependencies

**External Systems:**
- **Cloudflare Workers** — ingest, auth, routing, queue enqueue
- **Cloudflare R2** — artifact storage (raw audio, metadata, images, notes,
  cleaned audio, transcripts); zero egress fees
- **Cloudflare D1** — batch index and processing status (paid plan, 10GB limit)
- **Cloudflare Queues** — async job delivery from Worker to GCP
- **GCP Cloud Run** — processing runtime (transcode, Cobra, Koala, Speechmatics
  submission, result storage)
- **Speechmatics Batch API** — ASR with speaker diarization
- **Picovoice Cobra** — Voice Activity Detection
- **Picovoice Koala** — Noise suppression

**Internal Systems:**
- **uCapture Android app** — upstream client; produces AAC/M4A + JSON sidecar
  multipart uploads; primary subscriber to completion events

---

## 7. Visual Assets

**Existing:**
- `docs/flow-audio-pipeline.mmd` — end-to-end sequence diagram (upload phase,
  processing phase, completion notification back to Android)

**Required before TDD:**
- Architecture diagram (component view: Worker, R2, D1, Queue, Cloud Run,
  Speechmatics, Android client) — could be derived from existing sequence diagram

**Location:** `docs/`

---

## 8. Next Steps

1. Review this problem statement against PRD for gaps or corrections
2. Proceed to `process/create-tdd.md` to produce the Technical Design Document
   (PRD already exists: `docs/prd-audio-pipeline.md`)
3. Proceed to `process/create-issues.md` to decompose into tracked issues
4. Execute via `process/execute-issues.md`
5. Verify via `process/first-run-qa.md`
