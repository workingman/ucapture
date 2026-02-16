# SESSION_NOTES: ubiq-capture

**Updated:** 2026-02-10
**Purpose:** Ubiquitous capture system for recording and archiving the data ocean of daily life

---

## Project Overview

ubiq-capture is a multi-component system for comprehensive data capture across different modalities (audio, phone calls, financial records). Each subdirectory is an independent project targeting a specific capture domain, unified by the philosophy of automated, metadata-rich, cloud-synced archival.

---

## Components

### 1. android-recorder/ (Production-ready)

**What:** Android app (uCapture) for continuous background audio recording with contextual metadata.

**Stack:** Kotlin, Jetpack Compose, Hilt DI, Room DB, WorkManager, Google Drive API

**Status:** All 6 core tasks complete (project setup, recording service, metadata collection, local storage, Google Drive sync, UI). ~5,100 lines production code, ~2,050 lines test code across 12 test files.

**Working features:**
- Foreground recording service with wake locks and 30-min chunk rotation
- GPS location sampling (60s intervals) and calendar event association
- Google Sign-In with token persistence (EncryptedSharedPreferences)
- Auto-upload to Google Drive with hourly retry for failures
- JSON metadata sidecars alongside audio files
- Compose UI: recording control, timeline browser, settings

**Known issues:**
- Chunk duration still set to 1 minute (testing value, needs restoration to 30 min)
- Access token expiration handling incomplete (tokens expire after 1 hour)
- Verbose debug logging in GoogleDriveAuthManager needs cleanup
- Some stale tests in SettingsViewModelTest referencing removed methods
- RetentionManager bug: uploaded files not being deleted from disk

**Upcoming changes (driven by audio pipeline PRD):**
- Replace Google Drive upload with Cloudflare Worker endpoint
- Add camera capture (images attached as metadata to next upload batch)
- Add text note input (stored in metadata JSON sidecar `notes[]` array)
- Keep 44.1 kHz AAC recording (hardware-accelerated, battery-friendly) — transcoding happens server-side

---

### 2. cloudflare-audio-processor/ (PRD complete, implementation next)

**What:** Audio ingest, processing, and transcription pipeline. Cloudflare handles ingest/storage/indexing; GCP handles compute-intensive audio processing.

**Stack:** Cloudflare Workers + R2 + D1 + Queues (ingest side), GCP Cloud Run + Python (processing side), Picovoice Cobra/Koala, Speechmatics Batch API

**Status:** PRD v1 drafted (`docs/prd-audio-pipeline.md`), flow diagram created (`docs/flow-audio-pipeline.mmd`). No implementation code yet.

**Architecture:**
```
Phone → CF Worker (auth, validate, store) → R2 (raw artifacts)
                                          → D1 (batch index)
                                          → Queue → GCP Cloud Run
                                                      ├ Transcode (ffmpeg: M4A → 16kHz PCM)
                                                      ├ Cobra (VAD: trim silence)
                                                      ├ Koala (noise suppression)
                                                      └ Speechmatics (transcription + diarization)
                                                          → R2 (cleaned audio + transcript)
                                                          → D1 (update status)
                                                          → Event (trigger downstream)
```

**Key decisions made:**
- Batch model: each upload = audio + metadata JSON + optional images + optional notes, all linked by batch ID
- DR-safe file naming: R2 paths encode user/batch/type so D1 can be rebuilt from file listing
- Diarization enabled from day one (Speechmatics speaker labels)
- ASR behind modular interface (swappable engine)
- Transcoding on GCP, not phone (battery optimization)
- Text notes in metadata JSON sidecar; images as separate binary files in multipart upload

---

### 3. bluetooth-device/ (Planning phase)

**What:** Raspberry Pi Zero 2W-based Bluetooth HFP audio bridge for recording phone calls with dual-channel audio (caller on left, user on right).

**Stack (planned):** Raspberry Pi OS Lite, BlueZ + oFono, PipeWire + WirePlumber, FFmpeg, Bash/Python

**Status:** PRD v1.0 complete (`device-prd.md`). No implementation code yet.

**Planned features:**
- Bluetooth HFP/HSP headset emulation (phone pairs to Pi as headset)
- Audio passthrough to wired headset via USB audio adapter (target latency <= 30ms)
- Dual-channel stereo WAV recording at 16kHz (optimized for Whisper transcription)
- Rsync-based file offloading to workstation
- 256GB MicroSD local storage

---

### 4. expensify-interface/ (Complete)

**What:** One-time data migration that backs up all Expensify financial data to Cloudflare D1 (structured data) and R2 (receipt images) before account decommission.

**Status:** Complete and audited as of 2026-01-18. 33 reports, 1,068 expenses, 1,063 receipt images.

---

## Recent Session (2026-02-10)

### Audio Pipeline PRD

Designed the end-to-end architecture for the audio capture and transcription pipeline.

**Key outcomes:**
1. Chose Cloudflare + GCP split architecture (CF for ingest/WAF/storage, GCP for native compute)
2. Confirmed Picovoice Cobra/Koala require 16 kHz 16-bit mono PCM — transcoding on GCP via ffmpeg
3. Speechmatics chosen as ASR engine, diarization (speaker labels) included from launch
4. Batch-oriented upload model with DR-safe file naming in R2
5. PRD written following Sam's create-prd.md template with Gherkin acceptance criteria

**Files created:**
- `cloudflare-audio-processor/docs/prd-audio-pipeline.md`
- `cloudflare-audio-processor/docs/flow-audio-pipeline.mmd`

---

## Next Steps

### Immediate (audio pipeline)
1. **TDD:** Create Technical Design Document for cloudflare-audio-processor (there's a `create-tdd.md` template in ~/dev/mmv/process/)
2. **Picovoice licensing:** Confirm server/Linux license terms and pricing for Cobra + Koala
3. **Speechmatics account:** Set up account, confirm batch API access, verify diarization is available on chosen plan
4. **CF project scaffolding:** Init Wrangler project, create R2 bucket, create D1 database
5. **GCP project scaffolding:** Create Cloud Run service, set up container registry

### Android app updates (after pipeline is live)
6. **CloudStorageProvider swap:** Replace GoogleDriveStorage with new CF Worker endpoint implementation
7. **Camera capture:** Add image attachment to upload batches
8. **Text notes:** Add note input UI, include in metadata sidecar `notes[]` array
9. **Upload frequency:** Make chunk/upload interval configurable (5-30 min) with "upload now" button

### Deferred
10. **bluetooth-device:** Begin implementation (lower priority until audio pipeline is operational)
11. **Downstream AI:** Action items, followups, idea extraction from transcripts (separate PRD)
12. **Speaker identification:** Map anonymous diarization labels to real contacts (separate PRD)

---

## Blockers

| # | Blocker | Impact | Mitigation |
| :-- | :--- | :--- | :--- |
| B-1 | Picovoice server license terms unknown | Can't estimate processing cost or confirm we can run on Cloud Run | Check picovoice.ai pricing page; may need to contact sales |
| B-2 | Speechmatics plan/pricing not confirmed | Diarization may not be available on all plans | Review speechmatics.com plans before TDD |
| B-3 | CF Queue → GCP delivery mechanism not designed | Queue is a CF product — how does it trigger GCP Cloud Run? May need webhook, pub/sub, or polling pattern | TDD decision; options: CF Queue consumer calls GCP endpoint, or GCP polls |

---

## Risks

| # | Risk | Likelihood | Impact | Mitigation |
| :-- | :--- | :--- | :--- | :--- |
| R-1 | Picovoice Cobra/Koala processing time on long audio chunks | Medium | Slow pipeline, Cloud Run timeout | Process in segments; Cloud Run allows up to 60 min timeout |
| R-2 | 24x7 recording × 10 users = massive raw audio volume | High | Storage costs, upload bandwidth | Cobra VAD will trim significantly; monitor and alert on volume |
| R-3 | Speechmatics cost at scale (10 users × hours/day) | Medium | Budget overrun | Cobra/Koala trim reduces billable hours; monitor per-user costs |
| R-4 | CF D1 10GB limit for batch index | Low | Index outgrows D1 | Metadata-only (no audio content); likely fine for months; migrate to Turso or Planetscale if needed |
| R-5 | Multipart upload size limits on CF Workers | Medium | Large batches with multiple images may hit limits | CF Workers allow 100 MB on paid plan; chunk large uploads or upload images separately |

---

## Possible Skills to Create

| Skill | Trigger | What it would do |
| :--- | :--- | :--- |
| `cloudflare-worker` | Working with CF Workers, R2, D1, Queues | Wrangler CLI patterns, R2 bindings, D1 schema migrations, Queue producers/consumers, deployment |
| `speechmatics-api` | Integrating Speechmatics | Batch API patterns, job submission, polling, transcript parsing, diarization config |
| `picovoice-sdk` | Working with Cobra/Koala Python SDK | Frame-based processing, VAD thresholds, noise suppression pipeline, licensing/access key management |
| `gcp-cloud-run` | Deploying to Cloud Run | Container setup, Dockerfile patterns, env vars, secrets, scaling config, IAM for R2 access |

---

## Feature Opportunities

| # | Idea | Notes |
| :-- | :--- | :--- |
| F-1 | **Whisper fallback** | If Speechmatics is down or over budget, fall back to self-hosted Whisper on Cloud Run GPU instance (modular ASR interface makes this easy) |
| F-2 | **Live processing indicator on phone** | Push notification or app badge when a batch finishes processing — "Your 2pm meeting is transcribed" |
| F-3 | **Smart upload scheduling** | Analyze battery level + Wi-Fi availability + time of day to pick optimal upload windows; "upload now" overrides |
| F-4 | **Conversation segmentation** | Use Cobra VAD gaps to split a 30-min chunk into discrete conversations (e.g., 3-min chat, 15-min meeting, 5-min call) |
| F-5 | **Cost dashboard** | Track per-user Speechmatics + GCP + R2 costs; surface in a simple API endpoint |
| F-6 | **Audio quality scoring** | After Koala processing, compute SNR or similar metric to flag recordings that may produce poor transcripts |
| F-7 | **Bluetooth device integration** | Route bluetooth-device recordings through the same pipeline (already outputs 16 kHz WAV — skip transcode step) |
| F-8 | **Calendar-aware processing priority** | If metadata shows a calendar event titled "Board Meeting", auto-promote to priority processing |
| F-9 | **Geo-fenced recording profiles** | Phone detects office vs. home vs. commute via GPS; adjusts recording quality, upload frequency, and metadata collection |
| F-10 | **Cross-batch search** | Full-text search across all transcripts via D1 or a search index (Algolia, Meilisearch, or CF Workers AI embeddings) |
