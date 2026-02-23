# TDD: Audio Capture & Transcription Pipeline

## 0. Metadata

| Attribute | Details |
| :--- | :--- |
| **PRD** | `docs/prd-audio-pipeline.md` |
| **Status** | Draft |
| **Tech Lead** | Geoff |
| **Standards** | `process/standards/global/coding-style.md`, `process/standards/global/error-handling.md`, `process/standards/backend/api.md` |

---

## 1. Technology Choices

| Category | Choice | Rationale | Alternatives Considered |
| :--- | :--- | :--- | :--- |
| **Ingest Runtime** | Cloudflare Workers | Edge deployment, free DDoS/WAF, 0-egress R2 integration, D1 proximity | AWS Lambda (higher cold start, egress fees), GCP Cloud Functions (no edge) |
| **Ingest Language** | TypeScript | Type safety, Cloudflare Workers SDK native support, shared types with client | JavaScript (no type safety), Rust (steeper learning curve) |
| **Processing Runtime** | GCP Cloud Run | Supports native binaries (Picovoice), scales to zero, pay-per-use | GCP Compute Engine (always-on cost), AWS Fargate (similar, but team prefers GCP) |
| **Processing Language** | Python 3.11+ | First-class Picovoice SDK support, Speechmatics client library, simple deployment | Node.js (requires Python subprocess for Picovoice) |
| **Object Storage** | Cloudflare R2 | Zero egress fees (critical for GCP pulls), S3-compatible API, cheap storage ($0.015/GB/mo) | GCS (egress fees to Cloud Run), S3 (egress fees, no edge benefit) |
| **Relational Index** | Cloudflare D1 | Serverless SQLite, low latency to Worker, sufficient for metadata scale (~10 users × 100 batches/day = 365K rows/year) | PostgreSQL on GCP (overkill, adds ops burden), Firestore (query limitations) |
| **Job Queue** | Cloudflare Queues | Native Worker integration, automatic retries, FIFO + priority support | GCP Pub/Sub (adds cross-cloud complexity), SQS (not Cloudflare-native) |
| **Event Stream** | Cloudflare Pub/Sub | MQTT-based, mobile-friendly, user-scoped topics, persistent connections | Server-Sent Events (requires open HTTP connection), Polling (inefficient), Firebase FCM (external dependency) |
| **Authentication** | OAuth 2.0 (Google) | Leverages existing Google auth from Android app (already used for Drive), standard protocol, supports refresh tokens | Custom API keys (reinventing wheel), Auth0 (external cost) |
| **ASR Engine** | Speechmatics Batch API | Chosen in PRD (high quality), speaker diarization, word timestamps | Whisper (slower, local compute cost), Deepgram (comparable, less familiar) |
| **VAD** | Picovoice Cobra | Chosen in PRD, low latency, accurate silence trimming | WebRTC VAD (less accurate), Silero VAD (requires PyTorch, heavier) |
| **Noise Suppression** | Picovoice Koala | Chosen in PRD, pairs with Cobra, optimized for voice | RNNoise (good but requires recompilation), Krisp SDK (paid, closed source) |
| **Emotion Analysis** | Google Cloud Natural Language API | Native GCP (same project as Cloud Run, no cross-cloud hop), text-based sentiment (score + magnitude per sentence), negligible cost (~$0.001/1K chars), trivial Python integration via `google-cloud-language` SDK | Hume AI (highest quality, audio + text, 48-dim prosody, but $0.064/min, no self-host); j-hartmann/emotion-english-distilroberta-base (free, self-hosted, 7-class categorical, ~250MB model, but lower accuracy on ambient speech); audeering/wav2vec2-large-robust (free self-hosted, dimensional arousal/valence/dominance from audio, requires GPU) |
| **Schema Validation** | Zod | TypeScript-first, type inference, clear error messages | Joi (JS-only, no TS inference), AJV (JSON Schema, verbose) |
| **Testing** | Vitest (Worker), pytest (Python) | Fast, Vite-native for Workers; pytest standard for Python | Jest (slower), Mocha (more config) |

---

## 2. Architecture Overview

### System Components

The system is divided into two **deployment units** connected by a queue and event stream:

**1. Cloudflare Edge (Ingest + Index)**
- **Responsibilities**: Authentication, upload handling, R2 storage orchestration, D1 indexing, job queueing, status queries, event publishing
- **Deployment**: Cloudflare Worker (`cloudflare-audio-processor`)
- **Language**: TypeScript
- **External Interfaces**: HTTPS (Android app), R2, D1, Cloudflare Queues, Cloudflare Pub/Sub

**2. GCP Cloud Run (Processing)**
- **Responsibilities**: Audio transcoding, VAD (Cobra), denoising (Koala), ASR (Speechmatics), result storage
- **Deployment**: GCP Cloud Run service (`audio-processor-gcp`)
- **Language**: Python 3.11
- **External Interfaces**: Cloudflare Queues (consumer), R2 (fetch/store), D1 (status updates), Speechmatics API

### Component Boundaries

See companion architecture diagram: [`tdd-audio-pipeline-figure1.mmd`](tdd-audio-pipeline-figure1.mmd)

The system consists of three primary deployment units:

**1. Android App (uCapture)**
- OAuth 2.0 authentication with Google
- Multipart upload to Cloudflare Worker
- MQTT subscription to Cloudflare Pub/Sub for completion events

**2. Cloudflare Edge (Ingest + Index)**
- **Worker Components**:
  - Auth Middleware (OAuth 2.0 token validation)
  - Upload Handler (parse multipart → R2, create D1 batch, enqueue job)
  - Status Handler (query D1 by batch_id, user-scoped)
  - Event Publisher (publish to Pub/Sub topic: `batch-completions/{user_id}`)
- **Storage & Messaging**:
  - R2 (artifact storage, S3-compatible, zero egress fees)
  - D1 (batch index, SQLite)
  - Queues (FIFO + priority job queues)
  - Pub/Sub (MQTT event stream for completion notifications)

**3. GCP Cloud Run (Processing)**
- **Queue Consumer**: Receive jobs, update D1 status
- **Audio Pipeline**: Fetch from R2, transcode (ffmpeg), Cobra VAD, Koala denoise, Speechmatics ASR
- **Result Writer**: Store cleaned audio + transcript to R2, update D1, trigger completion event
- **External Integration**: Speechmatics Batch API (ASR + speaker diarization)

### Data Flow: Happy Path (Upload → Transcript)

1. **Upload** (sync):
   - Android sends `POST /v1/upload` with multipart body (audio + metadata + images + notes)
   - Worker validates OAuth token → extracts `user_id`
   - Worker generates `batch_id` = `{YYYYMMDD-HHMMSS-GMT-{uuid4}}`
   - Worker writes artifacts to R2:
     - `{user_id}/{batch_id}/raw-audio/recording.m4a`
     - `{user_id}/{batch_id}/metadata/metadata.json`
     - `{user_id}/{batch_id}/images/{timestamp}-{index}.jpg` (if present)
     - `{user_id}/{batch_id}/notes/notes.json` (if present)
   - Worker creates D1 batch record: `status = "uploaded"`
   - Worker enqueues job to Cloudflare Queue: `{batch_id, user_id, priority}`
   - Worker returns `202 Accepted {batch_id}` to Android

2. **Processing** (async):
   - GCP Cloud Run consumes job from queue
   - Updates D1: `status = "processing"`
   - Fetches `{user_id}/{batch_id}/raw-audio/recording.m4a` from R2
   - Transcodes M4A (44.1kHz AAC) → WAV (16kHz mono PCM)
   - **Cobra VAD**: Identifies speech segments, discards silence
   - If no speech detected → skip to step 3 (empty transcript)
   - **Koala**: Denoises speech segments
   - Submits cleaned audio to **Speechmatics Batch API**
   - Waits for transcript (polls Speechmatics job status)
   - Post-processes transcript: walks word timestamps, inserts `[MM:SS]` markers every 15 seconds
   - **Emotion Analysis** (best-effort): submits sentence-level transcript segments to
     the configured emotion provider (default: Google Cloud Natural Language API);
     stores result as `emotion.json` with `provider` field tagging the schema.
     If this step fails, logs the error and continues — batch still completes.
   - Stores results to R2:
     - `{user_id}/{batch_id}/cleaned-audio/cleaned.wav`
     - `{user_id}/{batch_id}/transcript/formatted.txt` (human-readable with markers)
     - `{user_id}/{batch_id}/transcript/raw-speechmatics.json` (full API response)
     - `{user_id}/{batch_id}/transcript/emotion.json` (provider-tagged emotion metadata)
   - Updates D1: `status = "completed"`, artifact paths (incl. `transcript_emotion_path`), metrics

3. **Completion Event** (async):
   - Worker (or GCP via API call to Worker) publishes to Pub/Sub topic: `batch-completions/{user_id}`
   - Payload: `{batch_id, user_id, status, artifact_paths, recording_started_at}`
   - Android app (subscribed via MQTT) receives event, marks recording as processed

4. **Status Query** (optional, sync):
   - Android sends `GET /v1/status/{batch_id}` with OAuth token
   - Worker validates user owns batch, returns D1 record

---

## 3. Data Models

### 3.1 R2 File Naming Convention

**Format**:
```
{user_id}/{batch_id}/{artifact_type}/{filename}
```

**Constraints**:
- `user_id`: Google OAuth `sub` claim (opaque string, e.g., `107234567890123456789`)
- `batch_id`: `YYYYMMDD-HHMMSS-GMT-{uuid4}` (example: `20260222-143027-GMT-a3f2c1b9-8e7d-4c5a-9b1e-2f3a4b5c6d7e`)
  - Timestamp is recording start time (from metadata `recording.started_at`)
  - GMT timezone (no daylight saving ambiguity, UI converts to locale)
  - UUID v4 suffix ensures uniqueness if two uploads start at same second
- `artifact_type`: One of: `raw-audio`, `metadata`, `images`, `notes`, `cleaned-audio`, `transcript`
- `filename`: Original filename or standardized name

**Examples**:
```
107234567890123456789/20260222-143027-GMT-a3f2c1b9-8e7d-4c5a-9b1e-2f3a4b5c6d7e/raw-audio/recording.m4a
107234567890123456789/20260222-143027-GMT-a3f2c1b9-8e7d-4c5a-9b1e-2f3a4b5c6d7e/metadata/metadata.json
107234567890123456789/20260222-143027-GMT-a3f2c1b9-8e7d-4c5a-9b1e-2f3a4b5c6d7e/images/20260222-143500-GMT-0.jpg
107234567890123456789/20260222-143027-GMT-a3f2c1b9-8e7d-4c5a-9b1e-2f3a4b5c6d7e/notes/notes.json
107234567890123456789/20260222-143027-GMT-a3f2c1b9-8e7d-4c5a-9b1e-2f3a4b5c6d7e/cleaned-audio/cleaned.wav
107234567890123456789/20260222-143027-GMT-a3f2c1b9-8e7d-4c5a-9b1e-2f3a4b5c6d7e/transcript/formatted.txt
107234567890123456789/20260222-143027-GMT-a3f2c1b9-8e7d-4c5a-9b1e-2f3a4b5c6d7e/transcript/raw-speechmatics.json
107234567890123456789/20260222-143027-GMT-a3f2c1b9-8e7d-4c5a-9b1e-2f3a4b5c6d7e/transcript/emotion.json
```

**DR Recovery**:
Given R2 file listing, you can reconstruct:
- All batches by parsing unique `{user_id}/{batch_id}` prefixes
- Recording start time from `batch_id` timestamp
- Artifact relationships by grouping files under same `batch_id`

---

### 3.2 D1 Database Schema

**Table: `batches`**
```sql
CREATE TABLE batches (
  id TEXT PRIMARY KEY,  -- batch_id (same format as R2 prefix)
  user_id TEXT NOT NULL,
  status TEXT NOT NULL,  -- 'uploaded' | 'processing' | 'completed' | 'failed'
  priority TEXT NOT NULL DEFAULT 'normal',  -- 'immediate' | 'normal'

  -- Artifact R2 paths (NULL until stored)
  raw_audio_path TEXT,
  metadata_path TEXT,
  cleaned_audio_path TEXT,
  transcript_formatted_path TEXT,
  transcript_raw_path TEXT,
  transcript_emotion_path TEXT,   -- NULL if emotion step skipped or failed

  -- Metadata snapshot (denormalized for query performance)
  recording_started_at TEXT NOT NULL,  -- ISO 8601 from metadata
  recording_ended_at TEXT,             -- ISO 8601 from metadata
  recording_duration_seconds REAL,     -- From metadata

  -- Processing metrics (populated on completion)
  uploaded_at TEXT NOT NULL DEFAULT (datetime('now')),
  processing_started_at TEXT,
  processing_completed_at TEXT,
  processing_wall_time_seconds REAL,
  queue_wait_time_seconds REAL,

  -- Audio metrics
  raw_audio_size_bytes INTEGER,
  raw_audio_duration_seconds REAL,
  speech_duration_seconds REAL,      -- After Cobra VAD
  speech_ratio REAL,                 -- speech / raw
  cleaned_audio_size_bytes INTEGER,

  -- ASR metrics
  speechmatics_job_id TEXT,
  speechmatics_cost_estimate REAL,

  -- Emotion analysis (best-effort; NULL if skipped or failed)
  emotion_provider TEXT,          -- e.g. "google-cloud-nl", "hume-ai"
  emotion_analyzed_at TEXT,       -- ISO 8601

  -- Error tracking
  retry_count INTEGER DEFAULT 0,
  error_message TEXT,
  error_stage TEXT,  -- 'upload' | 'transcode' | 'vad' | 'denoise' | 'asr' | 'storage'

  -- Indexes
  CONSTRAINT status_values CHECK (status IN ('uploaded', 'processing', 'completed', 'failed')),
  CONSTRAINT priority_values CHECK (priority IN ('immediate', 'normal'))
);

CREATE INDEX idx_batches_user_id ON batches(user_id);
CREATE INDEX idx_batches_status ON batches(status);
CREATE INDEX idx_batches_user_status ON batches(user_id, status);
CREATE INDEX idx_batches_user_started ON batches(user_id, recording_started_at DESC);
```

**Table: `batch_images`**
```sql
CREATE TABLE batch_images (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  batch_id TEXT NOT NULL,
  r2_path TEXT NOT NULL,
  captured_at TEXT NOT NULL,  -- ISO 8601 from image EXIF or metadata
  size_bytes INTEGER,
  FOREIGN KEY (batch_id) REFERENCES batches(id) ON DELETE CASCADE
);

CREATE INDEX idx_images_batch ON batch_images(batch_id);
```

**Table: `batch_notes`**
```sql
CREATE TABLE batch_notes (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  batch_id TEXT NOT NULL,
  note_text TEXT NOT NULL,
  created_at TEXT NOT NULL,  -- ISO 8601 from metadata
  FOREIGN KEY (batch_id) REFERENCES batches(id) ON DELETE CASCADE
);

CREATE INDEX idx_notes_batch ON batch_notes(batch_id);
```

**Table: `processing_stages`** (optional, for granular observability)
```sql
CREATE TABLE processing_stages (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  batch_id TEXT NOT NULL,
  stage TEXT NOT NULL,  -- 'transcode' | 'vad' | 'denoise' | 'asr_submit' | 'asr_wait' | 'post_process'
  started_at TEXT NOT NULL,
  completed_at TEXT,
  duration_seconds REAL,
  success BOOLEAN,
  error_message TEXT,
  FOREIGN KEY (batch_id) REFERENCES batches(id) ON DELETE CASCADE
);

CREATE INDEX idx_stages_batch ON processing_stages(batch_id);
```

---

### 3.3 Metadata JSON Schema (uCapture Sidecar)

**File**: `{user_id}/{batch_id}/metadata/metadata.json`

**Schema** (extends existing uCapture format):
```typescript
interface Metadata {
  recording: {
    started_at: string;      // ISO 8601 UTC
    ended_at: string;        // ISO 8601 UTC
    duration_seconds: number;
    audio_format: string;    // "m4a"
    sample_rate: number;     // 44100
    channels: number;        // 1 (mono)
    bitrate: number;         // 128000 (128 kbps)
    file_size_bytes: number;
  };

  location?: {
    latitude: number;
    longitude: number;
    accuracy_meters: number;
    captured_at: string;     // ISO 8601 UTC
    address?: string;        // Reverse geocoded (if available)
  };

  calendar?: {
    event_id?: string;       // Google Calendar event ID (if linked)
    event_title?: string;
    attendees?: string[];    // Email addresses
  };

  images?: Array<{
    filename: string;        // Matches R2 filename in batch_images
    captured_at: string;     // ISO 8601 UTC
    size_bytes: number;
  }>;

  notes?: Array<{
    text: string;
    created_at: string;      // ISO 8601 UTC
  }>;

  device: {
    model: string;           // "Pixel 7"
    os_version: string;      // "Android 14"
    app_version: string;     // "1.0.5"
  };
}
```

---

### 3.4 Transcript Format

**File**: `{user_id}/{batch_id}/transcript/formatted.txt`

**Format** (human-readable with speaker labels and time markers):
```
[00:00] Speaker 1: Hey, how's the project going?

[00:15] Speaker 2: Pretty good! We finished the API integration yesterday. The Speechmatics transcription quality is really impressive.

[00:30] Speaker 1: That's great to hear. What about the noise suppression? Is Koala working well?

[00:45] Speaker 2: Yeah, it's cutting out almost all the background noise. I tested it with traffic sounds and it still captured the speech clearly.

[01:00] Speaker 1: Perfect. Let's schedule a demo for next week.
```

**Rules**:
- Time markers `[MM:SS]` inserted every 15 seconds (based on word timestamps from Speechmatics)
- Speaker labels from Speechmatics diarization (`Speaker 1`, `Speaker 2`, etc.)
- Empty line between speaker turns for readability
- No speaker label if no speech detected at 15s interval

**File**: `{user_id}/{batch_id}/transcript/raw-speechmatics.json`

**Format**: Full Speechmatics API response (JSON), preserved for future reprocessing

---

### 3.5 Emotion Metadata Schema

**File**: `{user_id}/{batch_id}/transcript/emotion.json`

**Purpose**: Provider-tagged per-segment emotion/sentiment annotation. The
`provider` field is the discriminant — downstream consumers branch on it to
interpret the `analysis` object, since providers produce incompatible schemas.

**Envelope** (common across all providers):
```json
{
  "provider": "google-cloud-nl",
  "provider_version": "v2",
  "analyzed_at": "2026-02-22T14:38:20Z",
  "batch_id": "20260222-143027-GMT-a3f2c1b9-...",
  "segments": [
    {
      "segment_index": 0,
      "start_seconds": 0.0,
      "end_seconds": 15.0,
      "speaker": "Speaker 1",
      "text": "Hey, how's the project going?",
      "analysis": { }
    }
  ]
}
```

**`analysis` schemas by provider:**

`google-cloud-nl` (initial):
```json
{ "score": 0.4, "magnitude": 0.4 }
```
`score`: -1.0 (very negative) → +1.0 (very positive). `magnitude`: 0.0→∞,
intensity of sentiment regardless of polarity.

`hume-ai` (future — audio-based):
```json
{ "prosody": { "Joy": 0.73, "Excitement": 0.51, "Calmness": 0.31 } }
```
48-dimensional continuous emotion space; only top-N values typically shown.
Requires audio input (cleaned WAV), not text.

`j-hartmann-distilroberta` (future — text-based, self-hosted):
```json
{ "emotion": "joy", "confidence": 0.92 }
```
One of: anger, disgust, fear, joy, neutral, sadness, surprise.

`audeering-wav2vec2` (future — audio-based, self-hosted):
```json
{ "arousal": 0.61, "dominance": 0.45, "valence": 0.72 }
```
Continuous Russell circumplex dimensions; all values in [0, 1].

---

## 4. Interface Contracts

### 4.1 REST API (Cloudflare Worker)

**Base URL**: `https://audio-pipeline.{cf-subdomain}.workers.dev`

**Authentication**: All endpoints require `Authorization: Bearer {google_oauth_token}` header

---

#### `POST /v1/upload`

**Purpose**: Upload a new batch (audio + metadata + optional images/notes)

**Request**:
```
Content-Type: multipart/form-data

Fields:
- audio: File (required, .m4a, max 50MB)
- metadata: File (required, .json, metadata schema)
- images: File[] (optional, .jpg/.png, max 10 files, 5MB each)
- priority: string (optional, "immediate" | "normal", default: "normal")
```

**Response** (202 Accepted):
```json
{
  "batch_id": "20260222-143027-GMT-a3f2c1b9-8e7d-4c5a-9b1e-2f3a4b5c6d7e",
  "status": "uploaded",
  "uploaded_at": "2026-02-22T14:30:28Z"
}
```

**Errors**:
- `400`: Missing audio or metadata, invalid metadata JSON, file too large
- `401`: Missing or invalid OAuth token
- `413`: Payload too large (>100MB total)
- `500`: R2 or D1 write failure

**Access Control**:
- Extract `user_id` from OAuth token `sub` claim
- All R2 writes use `{user_id}` prefix
- D1 batch record stores `user_id`

---

#### `GET /v1/status/:batch_id`

**Purpose**: Query batch processing status and artifacts

**Request**:
```
Authorization: Bearer {google_oauth_token}
```

**Response** (200 OK):
```json
{
  "batch_id": "20260222-143027-GMT-a3f2c1b9-8e7d-4c5a-9b1e-2f3a4b5c6d7e",
  "user_id": "107234567890123456789",
  "status": "completed",
  "recording_started_at": "2026-02-22T14:30:00Z",
  "recording_duration_seconds": 1847.3,
  "uploaded_at": "2026-02-22T14:30:28Z",
  "processing_completed_at": "2026-02-22T14:38:15Z",
  "artifacts": {
    "raw_audio": "107234567890123456789/20260222-143027-GMT-.../raw-audio/recording.m4a",
    "metadata": "107234567890123456789/20260222-143027-GMT-.../metadata/metadata.json",
    "cleaned_audio": "107234567890123456789/20260222-143027-GMT-.../cleaned-audio/cleaned.wav",
    "transcript_formatted": "107234567890123456789/20260222-143027-GMT-.../transcript/formatted.txt",
    "transcript_raw": "107234567890123456789/20260222-143027-GMT-.../transcript/raw-speechmatics.json",
    "transcript_emotion": "107234567890123456789/20260222-143027-GMT-.../transcript/emotion.json",
    "images": [
      "107234567890123456789/20260222-143027-GMT-.../images/20260222-143500-GMT-0.jpg"
    ]
  },
  "metrics": {
    "speech_duration_seconds": 420.5,
    "speech_ratio": 0.23,
    "speechmatics_cost_estimate": 0.63
  }
}
```

**Response** (if `status = "failed"`):
```json
{
  "batch_id": "...",
  "status": "failed",
  "error_message": "Speechmatics API timeout after 3 retries",
  "error_stage": "asr",
  "retry_count": 3
}
```

**Errors**:
- `401`: Missing or invalid OAuth token
- `403`: Batch exists but belongs to different user
- `404`: Batch not found

**Access Control**:
- Extract `user_id` from OAuth token
- Join D1 query: `WHERE id = :batch_id AND user_id = :user_id`

---

#### `GET /v1/batches`

**Purpose**: List batches for authenticated user (paginated, filterable)

**Request**:
```
Authorization: Bearer {google_oauth_token}

Query Parameters:
- status: string (optional, filter by status)
- start_date: string (optional, ISO 8601 date, inclusive)
- end_date: string (optional, ISO 8601 date, inclusive)
- limit: number (optional, default 50, max 100)
- offset: number (optional, default 0)
```

**Response** (200 OK):
```json
{
  "batches": [
    {
      "batch_id": "...",
      "status": "completed",
      "recording_started_at": "2026-02-22T14:30:00Z",
      "uploaded_at": "2026-02-22T14:30:28Z"
    }
  ],
  "pagination": {
    "limit": 50,
    "offset": 0,
    "total": 342
  }
}
```

**Access Control**:
- Query scoped to `user_id` from OAuth token

---

#### `GET /v1/download/:batch_id/:artifact_type`

**Purpose**: Download artifact (pre-signed R2 URL)

**Request**:
```
Authorization: Bearer {google_oauth_token}

Path Parameters:
- artifact_type: "raw_audio" | "cleaned_audio" | "transcript_formatted" | "transcript_raw" | "metadata"
```

**Response** (302 Redirect):
```
Location: https://r2.cloudflarestorage.com/{bucket}/{path}?X-Amz-Signature=...
```

**Errors**:
- `401`: Missing or invalid OAuth token
- `403`: Batch belongs to different user
- `404`: Batch or artifact not found

**Access Control**:
- Verify batch ownership via D1 query
- Generate R2 pre-signed URL with 15-minute expiry

---

### 4.2 Cloudflare Queue Message Schema

**Queue Name**: `audio-processing-jobs`

**Message Format**:
```typescript
interface ProcessingJob {
  batch_id: string;
  user_id: string;
  priority: "immediate" | "normal";
  enqueued_at: string;  // ISO 8601 UTC
}
```

**Consumer**: GCP Cloud Run service

---

### 4.3 Cloudflare Pub/Sub Events

**Topic**: `batch-completions/{user_id}` (user-scoped)

**Message Format**:
```typescript
interface CompletionEvent {
  batch_id: string;
  user_id: string;
  status: "completed" | "failed";
  recording_started_at: string;  // ISO 8601 UTC (for Android to match local recording)
  artifact_paths: {
    raw_audio?: string;
    cleaned_audio?: string;
    transcript_formatted?: string;
    transcript_raw?: string;
  };
  error_message?: string;  // Present if status = "failed"
  published_at: string;    // ISO 8601 UTC
}
```

**Subscriber**: Android app (MQTT connection with OAuth-derived credentials)

---

### 4.4 Python Processing Service Interfaces

**Module**: `audio_processor/pipeline.py`

```python
async def process_batch(batch_id: str, user_id: str) -> ProcessingResult:
    """
    Main processing pipeline entry point.

    Args:
        batch_id: Batch ID from queue
        user_id: User ID (for R2 path construction)

    Returns:
        ProcessingResult with status, artifacts, metrics

    Raises:
        AudioFetchError: Failed to fetch audio from R2
        TranscodeError: Failed to transcode audio
        VADError: Cobra VAD failed
        DenoiseError: Koala processing failed
        ASRError: Speechmatics API error
        StorageError: Failed to write results to R2
    """
```

```python
@dataclass
class ProcessingResult:
    status: Literal["completed", "failed"]
    batch_id: str
    artifact_paths: dict[str, str]
    metrics: ProcessingMetrics
    error: Optional[ProcessingError] = None
```

```python
@dataclass
class ProcessingMetrics:
    raw_audio_duration_seconds: float
    speech_duration_seconds: float
    speech_ratio: float
    cleaned_audio_size_bytes: int
    speechmatics_job_id: str
    speechmatics_cost_estimate: float
    processing_wall_time_seconds: float
    stage_timings: dict[str, float]  # {stage_name: duration_seconds}
```

---

## 5. Directory Structure

### Cloudflare Worker (TypeScript)

```
cloudflare-audio-processor/
├── src/
│   ├── index.ts                    # Worker entry point, route definitions
│   ├── auth/
│   │   ├── middleware.ts           # OAuth token validation middleware
│   │   └── google.ts               # Google OAuth token verification
│   ├── handlers/
│   │   ├── upload.ts               # POST /v1/upload handler
│   │   ├── status.ts               # GET /v1/status/:batch_id handler
│   │   ├── batches.ts              # GET /v1/batches handler
│   │   └── download.ts             # GET /v1/download/:batch_id/:artifact handler
│   ├── storage/
│   │   ├── r2.ts                   # R2 client wrapper, path generation
│   │   └── d1.ts                   # D1 query helpers, batch CRUD
│   ├── queue/
│   │   └── publisher.ts            # Enqueue processing jobs
│   ├── events/
│   │   └── pubsub.ts               # Publish completion events to Pub/Sub
│   ├── types/
│   │   ├── api.ts                  # API request/response types
│   │   ├── batch.ts                # Batch, metadata types
│   │   └── queue.ts                # Queue message types
│   ├── utils/
│   │   ├── batch-id.ts             # Generate timestamp-based batch IDs
│   │   ├── validation.ts           # Zod schemas for request validation
│   │   └── errors.ts               # Custom error classes
│   └── env.d.ts                    # Cloudflare bindings types
├── migrations/
│   └── 0001_create_batches.sql     # D1 schema migration
├── tests/
│   ├── auth.test.ts
│   ├── upload.test.ts
│   ├── status.test.ts
│   └── batch-id.test.ts
├── wrangler.toml                   # Cloudflare config (R2, D1, Queue bindings)
├── package.json
├── tsconfig.json
└── vitest.config.ts
```

---

### GCP Cloud Run Service (Python)

```
audio-processor-gcp/
├── audio_processor/
│   ├── __init__.py
│   ├── main.py                     # Queue consumer entry point
│   ├── pipeline.py                 # Main process_batch() orchestrator
│   ├── audio/
│   │   ├── __init__.py
│   │   ├── transcode.py            # M4A → 16kHz WAV (ffmpeg wrapper)
│   │   ├── vad.py                  # Picovoice Cobra integration
│   │   └── denoise.py              # Picovoice Koala integration
│   ├── asr/
│   │   ├── __init__.py
│   │   ├── interface.py            # Abstract ASR interface (modular)
│   │   ├── speechmatics.py         # Speechmatics Batch API client
│   │   └── postprocess.py          # Insert timestamp markers, format output
│   ├── emotion/
│   │   ├── __init__.py
│   │   ├── interface.py            # Abstract EmotionEngine + EmotionResult types
│   │   ├── runner.py               # Best-effort wrapper, provider registry
│   │   └── google_nl.py            # Google Cloud Natural Language (initial provider)
│   ├── storage/
│   │   ├── __init__.py
│   │   ├── r2_client.py            # R2 fetch/put via boto3 (S3-compatible)
│   │   └── d1_client.py            # D1 updates via Cloudflare API
│   ├── queue/
│   │   ├── __init__.py
│   │   └── consumer.py             # Cloudflare Queue consumer (pull-based)
│   ├── observability/
│   │   ├── __init__.py
│   │   ├── metrics.py              # Metric collection and logging
│   │   └── logger.py               # Structured logging setup
│   └── utils/
│       ├── __init__.py
│       ├── retry.py                # Exponential backoff retry decorator
│       └── errors.py               # Custom exception classes
├── tests/
│   ├── test_transcode.py
│   ├── test_vad.py
│   ├── test_speechmatics.py
│   └── test_pipeline.py
├── Dockerfile                      # Multi-stage build (Python 3.11 + ffmpeg)
├── requirements.txt                # picovoice, boto3, httpx, etc.
├── pyproject.toml                  # pytest, black, ruff config
└── cloudbuild.yaml                 # GCP Cloud Build config
```

---

## 6. Key Implementation Decisions

### **Decision 1: OAuth Token Validation Strategy**

**Decision**: Validate Google OAuth tokens by calling Google's `tokeninfo` endpoint (cached for 1 hour per token)

**Rationale**:
- Android app already authenticates with Google for Drive access, so we reuse those tokens
- Google's `tokeninfo` endpoint verifies signature and returns `sub` (user ID), `email`, `exp`
- Caching reduces latency and quota consumption (tokens valid for 1 hour, cache matches)

**Guidance**:
```typescript
// src/auth/google.ts
export async function validateGoogleToken(token: string, cache: KVNamespace): Promise<{ sub: string; email: string }> {
  // Check KV cache first
  const cached = await cache.get(`token:${token}`);
  if (cached) return JSON.parse(cached);

  // Call Google tokeninfo endpoint
  const response = await fetch(`https://oauth2.googleapis.com/tokeninfo?access_token=${token}`);
  if (!response.ok) throw new AuthenticationError("Invalid OAuth token");

  const info = await response.json();
  if (!info.sub || !info.email) throw new AuthenticationError("Token missing required claims");

  // Cache for 1 hour (match token expiry)
  await cache.put(`token:${token}`, JSON.stringify({ sub: info.sub, email: info.email }), { expirationTtl: 3600 });

  return { sub: info.sub, email: info.email };
}
```

**Middleware**:
```typescript
// src/auth/middleware.ts
export async function authMiddleware(c: Context, next: Next) {
  const authHeader = c.req.header("Authorization");
  if (!authHeader?.startsWith("Bearer ")) {
    return c.json({ error: "Missing Authorization header" }, 401);
  }

  const token = authHeader.slice(7);
  try {
    const user = await validateGoogleToken(token, c.env.TOKEN_CACHE);
    c.set("user_id", user.sub);
    c.set("email", user.email);
    await next();
  } catch (error) {
    return c.json({ error: "Invalid OAuth token" }, 401);
  }
}
```

---

### **Decision 2: Batch ID Generation with DR Safety**

**Decision**: Generate batch IDs as `{YYYYMMDD-HHMMSS-GMT}-{uuid4}` using recording start time from metadata

**Rationale**:
- Timestamp component enables DR recovery (can reconstruct timeline from R2 listing)
- GMT timezone avoids daylight saving ambiguity (UI converts to locale)
- UUID suffix ensures uniqueness even if two uploads have same start second
- Human-readable for debugging (can identify batch age at a glance)

**Guidance**:
```typescript
// src/utils/batch-id.ts
import { v4 as uuidv4 } from 'uuid';

export function generateBatchId(recordingStartedAt: string): string {
  const date = new Date(recordingStartedAt);

  // Format: YYYYMMDD-HHMMSS-GMT
  const timestamp = date.toISOString()
    .replace(/[-:]/g, '')
    .replace('T', '-')
    .slice(0, 15) + '-GMT';

  const uuid = uuidv4();

  return `${timestamp}-${uuid}`;
  // Example: 20260222-143027-GMT-a3f2c1b9-8e7d-4c5a-9b1e-2f3a4b5c6d7e
}
```

**DR Recovery Script** (reference for future ops):
```python
# ops/recover-d1-from-r2.py
def reconstruct_batches_from_r2(r2_client):
    """
    Scan R2 bucket, parse file paths, rebuild D1 batches table.
    Use this if D1 is lost but R2 is intact.
    """
    objects = r2_client.list_objects(Prefix="")
    batches = {}

    for obj in objects:
        # Parse: {user_id}/{batch_id}/{artifact_type}/{filename}
        parts = obj.key.split('/')
        if len(parts) < 3:
            continue

        user_id, batch_id, artifact_type = parts[0], parts[1], parts[2]

        # Extract timestamp from batch_id (first 15 chars: YYYYMMDD-HHMMSS)
        recording_started_at = batch_id[:8] + 'T' + batch_id[9:15].replace('-', ':') + 'Z'

        if batch_id not in batches:
            batches[batch_id] = {
                'id': batch_id,
                'user_id': user_id,
                'recording_started_at': recording_started_at,
                'artifacts': {}
            }

        batches[batch_id]['artifacts'][artifact_type] = obj.key

    # Insert into D1 (via API or direct SQLite access)
    for batch in batches.values():
        insert_batch(batch)
```

---

### **Decision 3: Multipart Upload Handling**

**Decision**: Use Cloudflare Workers' native `formData()` parser, stream files directly to R2 (no temp storage)

**Rationale**:
- Workers have 128MB memory limit (paid plan), can't buffer large files in memory
- R2 `put()` accepts `ReadableStream`, enables streaming upload
- Avoid double-write (Worker storage → R2); write once directly to R2

**Guidance**:
```typescript
// src/handlers/upload.ts
export async function handleUpload(c: Context) {
  const formData = await c.req.formData();
  const audioFile = formData.get('audio') as File;
  const metadataFile = formData.get('metadata') as File;
  const images = formData.getAll('images') as File[];
  const priority = (formData.get('priority') as string) || 'normal';

  if (!audioFile || !metadataFile) {
    return c.json({ error: 'Missing audio or metadata' }, 400);
  }

  // Parse metadata to extract recording_started_at
  const metadataText = await metadataFile.text();
  const metadata = JSON.parse(metadataText);
  const batch_id = generateBatchId(metadata.recording.started_at);
  const user_id = c.get('user_id');

  // Stream audio to R2
  const audioPath = `${user_id}/${batch_id}/raw-audio/recording.m4a`;
  await c.env.R2_BUCKET.put(audioPath, audioFile.stream());

  // Stream metadata to R2
  const metadataPath = `${user_id}/${batch_id}/metadata/metadata.json`;
  await c.env.R2_BUCKET.put(metadataPath, metadataText);

  // Upload images (if present)
  for (let i = 0; i < images.length; i++) {
    const img = images[i];
    const imgPath = `${user_id}/${batch_id}/images/${metadata.images[i].captured_at}-${i}.jpg`;
    await c.env.R2_BUCKET.put(imgPath, img.stream());
  }

  // Create D1 batch record
  await c.env.DB.prepare(`
    INSERT INTO batches (id, user_id, status, priority, raw_audio_path, metadata_path, recording_started_at, raw_audio_size_bytes)
    VALUES (?, ?, 'uploaded', ?, ?, ?, ?, ?)
  `).bind(batch_id, user_id, priority, audioPath, metadataPath, metadata.recording.started_at, audioFile.size).run();

  // Enqueue processing job
  await c.env.PROCESSING_QUEUE.send({
    batch_id,
    user_id,
    priority,
    enqueued_at: new Date().toISOString()
  });

  return c.json({ batch_id, status: 'uploaded', uploaded_at: new Date().toISOString() }, 202);
}
```

---

### **Decision 4: ASR Modular Interface Pattern**

**Decision**: Define `ASREngine` abstract base class in Python, implement `SpeechmaticsEngine` as first concrete implementation

**Rationale**:
- PRD requires ability to swap ASR engines with config change, not code rewrite
- Enables A/B testing (process same audio with multiple engines)
- Future engines (Whisper, Deepgram) can be added without touching pipeline logic

**Guidance**:
```python
# audio_processor/asr/interface.py
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import List

@dataclass
class TranscriptWord:
    text: str
    start_time: float  # Seconds
    end_time: float
    confidence: float

@dataclass
class TranscriptSegment:
    speaker_label: str  # "Speaker 1", "Speaker 2", etc.
    words: List[TranscriptWord]

@dataclass
class Transcript:
    segments: List[TranscriptSegment]
    raw_response: dict  # Full API response (for future reprocessing)

class ASREngine(ABC):
    @abstractmethod
    async def transcribe(self, audio_path: str, metadata: dict) -> Transcript:
        """
        Transcribe audio file.

        Args:
            audio_path: Local path to cleaned audio (WAV)
            metadata: Batch metadata (may contain hints like language)

        Returns:
            Transcript with speaker labels and word timestamps

        Raises:
            ASRError: Transcription failed
        """
        pass
```

```python
# audio_processor/asr/speechmatics.py
from .interface import ASREngine, Transcript, TranscriptSegment, TranscriptWord
from speechmatics.client import SpeechmaticsClient
from speechmatics.models import BatchConfig

class SpeechmaticsEngine(ASREngine):
    def __init__(self, api_key: str):
        self.client = SpeechmaticsClient(api_key)

    async def transcribe(self, audio_path: str, metadata: dict) -> Transcript:
        config = BatchConfig(
            language="en",
            enable_diarization=True,
            enable_entities=False  # Not needed for MVP
        )

        # Submit job
        job_id = await self.client.submit(audio_path, config)

        # Poll for completion (with timeout)
        result = await self.client.wait_for_completion(job_id, timeout=600)

        # Convert to common format
        segments = self._convert_response(result)

        return Transcript(segments=segments, raw_response=result)

    def _convert_response(self, response: dict) -> List[TranscriptSegment]:
        # Parse Speechmatics response, group by speaker
        # ...implementation...
        pass
```

**Pipeline Usage**:
```python
# audio_processor/pipeline.py
async def process_batch(batch_id: str, user_id: str) -> ProcessingResult:
    # ... transcode, VAD, denoise steps ...

    # ASR (swappable via config)
    asr_engine = get_asr_engine(config.asr_provider)  # "speechmatics" | "whisper" | "deepgram"
    transcript = await asr_engine.transcribe(cleaned_audio_path, metadata)

    # Post-process (engine-agnostic)
    formatted_text = insert_timestamp_markers(transcript)

    # Emotion analysis (best-effort, swappable via config)
    emotion_result = await run_emotion_analysis(transcript, cleaned_audio_path, config)

    # Store results
    # ...
```

---

### **Emotion Provider Interface (`EmotionEngine`)**

```python
# audio_processor/emotion/interface.py
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import List, Any, Optional

@dataclass
class EmotionSegment:
    segment_index: int
    start_seconds: float
    end_seconds: float
    speaker: str
    text: str
    analysis: dict[str, Any]  # Schema determined by provider

@dataclass
class EmotionResult:
    provider: str           # e.g. "google-cloud-nl"
    provider_version: str   # e.g. "v2"
    analyzed_at: str        # ISO 8601 UTC
    batch_id: str
    segments: List[EmotionSegment]

class EmotionEngine(ABC):
    @property
    @abstractmethod
    def provider_name(self) -> str:
        """Provider identifier stored in output JSON (e.g. 'google-cloud-nl')."""
        pass

    @property
    @abstractmethod
    def provider_version(self) -> str:
        """Model/API version stored in output JSON."""
        pass

    @abstractmethod
    async def analyze(
        self,
        segments: List["TranscriptSegment"],  # From ASR interface
        audio_path: Optional[str] = None       # Required for audio-based providers
    ) -> EmotionResult:
        """
        Analyze emotion/sentiment for each transcript segment.

        Args:
            segments: Transcript segments (speaker, timestamps, text)
            audio_path: Local path to cleaned WAV (required for Hume AI,
                        audeering; ignored by text-only providers)

        Returns:
            EmotionResult with provider-tagged analysis per segment

        Raises:
            EmotionAnalysisError: Provider API failed. Caller handles this
                as a non-fatal error (batch still completes).
        """
        pass
```

**Google Cloud NL implementation** (initial provider):

```python
# audio_processor/emotion/google_nl.py
from datetime import datetime, timezone
from google.cloud import language_v2
from .interface import EmotionEngine, EmotionResult, EmotionSegment

class GoogleNLEngine(EmotionEngine):
    provider_name = "google-cloud-nl"
    provider_version = "v2"

    def __init__(self):
        self.client = language_v2.LanguageServiceClient()

    async def analyze(self, segments, audio_path=None) -> EmotionResult:
        emotion_segments = []
        for i, seg in enumerate(segments):
            # Flatten segment words into text if needed
            text = seg.text if hasattr(seg, "text") else " ".join(w.text for w in seg.words)
            doc = language_v2.Document(
                content=text,
                type_=language_v2.Document.Type.PLAIN_TEXT
            )
            sentiment = self.client.analyze_sentiment(
                request={"document": doc}
            ).document_sentiment
            emotion_segments.append(EmotionSegment(
                segment_index=i,
                start_seconds=seg.start_time,
                end_seconds=seg.end_time,
                speaker=seg.speaker_label,
                text=text,
                analysis={"score": sentiment.score, "magnitude": sentiment.magnitude}
            ))
        return EmotionResult(
            provider=self.provider_name,
            provider_version=self.provider_version,
            analyzed_at=datetime.now(timezone.utc).isoformat(),
            batch_id="",  # Set by caller
            segments=emotion_segments
        )
```

**Pipeline helper** (best-effort wrapper):

```python
# audio_processor/emotion/runner.py
import logging
from .interface import EmotionResult
from .google_nl import GoogleNLEngine

logger = logging.getLogger(__name__)

EMOTION_ENGINES = {
    "google-cloud-nl": GoogleNLEngine,
    # "hume-ai": HumeEngine,          # future
    # "j-hartmann": JHartmannEngine,  # future
    # "audeering": AudeeringEngine,   # future
}

async def run_emotion_analysis(transcript, audio_path, config) -> EmotionResult | None:
    """Run emotion analysis as a best-effort step. Returns None on failure."""
    provider = config.emotion_provider  # e.g. "google-cloud-nl"
    if not provider or not transcript.segments:
        return None

    engine_cls = EMOTION_ENGINES.get(provider)
    if not engine_cls:
        logger.warning(f"Unknown emotion provider: {provider}, skipping")
        return None

    try:
        engine = engine_cls()
        return await engine.analyze(transcript.segments, audio_path=audio_path)
    except Exception as e:
        logger.error(f"Emotion analysis failed (provider={provider}): {e}")
        return None  # Non-fatal — pipeline continues
```

---

### **Decision 5: Completion Event Publishing**

**Decision**: GCP service calls Cloudflare Worker API endpoint to trigger event publish (Worker publishes to Pub/Sub)

**Rationale**:
- Cloudflare Pub/Sub is tightly integrated with Workers (native bindings)
- GCP calling Worker API is simpler than GCP authenticating directly to Cloudflare Pub/Sub
- Keeps event publishing logic centralized in Worker (single source of truth)

**Guidance**:
```typescript
// src/handlers/internal/publish-event.ts (Worker-only endpoint, not public)
export async function publishCompletionEvent(c: Context) {
  // Auth: Verify request is from GCP (shared secret or GCP service account JWT)
  const secret = c.req.header("X-Internal-Secret");
  if (secret !== c.env.INTERNAL_SECRET) {
    return c.json({ error: "Forbidden" }, 403);
  }

  const event: CompletionEvent = await c.req.json();

  // Publish to user-scoped topic
  const topic = `batch-completions/${event.user_id}`;
  await c.env.PUBSUB.publish(topic, JSON.stringify(event));

  return c.json({ success: true }, 200);
}
```

```python
# audio_processor/storage/d1_client.py (GCP side)
async def publish_completion_event(event: CompletionEvent, worker_url: str, secret: str):
    """Call Worker API to publish event to Pub/Sub."""
    async with httpx.AsyncClient() as client:
        response = await client.post(
            f"{worker_url}/internal/publish-event",
            headers={"X-Internal-Secret": secret},
            json=event.__dict__
        )
        response.raise_for_status()
```

---

### **Decision 6: Error Handling and Retry Strategy**

**Decision**: Use exponential backoff with 3 retries for transient failures, mark batch as `failed` after exhausting retries

**Rationale**:
- External APIs (Speechmatics, R2) may have transient failures (rate limits, timeouts)
- Exponential backoff prevents hammering services
- Hard cap at 3 retries prevents infinite loops
- Batch marked `failed` with error details enables manual intervention

**Guidance**:
```python
# audio_processor/utils/retry.py
import asyncio
from functools import wraps
from typing import TypeVar, Callable

T = TypeVar('T')

def retry_with_backoff(max_retries: int = 3, base_delay: float = 1.0):
    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @wraps(func)
        async def wrapper(*args, **kwargs) -> T:
            last_error = None

            for attempt in range(max_retries + 1):
                try:
                    return await func(*args, **kwargs)
                except Exception as e:
                    last_error = e

                    if attempt < max_retries:
                        delay = base_delay * (2 ** attempt)
                        logger.warning(f"Retry {attempt + 1}/{max_retries} after {delay}s: {e}")
                        await asyncio.sleep(delay)
                    else:
                        logger.error(f"Failed after {max_retries} retries: {e}")

            raise last_error

        return wrapper
    return decorator
```

**Usage**:
```python
# audio_processor/asr/speechmatics.py
@retry_with_backoff(max_retries=3)
async def transcribe(self, audio_path: str, metadata: dict) -> Transcript:
    # Speechmatics API call (retries on timeout, 429, 503)
    pass
```

**Failure Handling in Pipeline**:
```python
# audio_processor/pipeline.py
async def process_batch(batch_id: str, user_id: str) -> ProcessingResult:
    try:
        # ... processing steps ...

        return ProcessingResult(status="completed", ...)

    except ASRError as e:
        # Record failure in D1
        await d1_client.update_batch_status(
            batch_id,
            status="failed",
            error_message=str(e),
            error_stage="asr"
        )

        # Publish failure event
        await publish_completion_event(CompletionEvent(
            batch_id=batch_id,
            user_id=user_id,
            status="failed",
            error_message=str(e)
        ))

        return ProcessingResult(status="failed", error=e)
```

---

### **Decision 7: Observability Metrics Collection**

**Decision**: Log all metrics to structured JSON (stdout), ingest via GCP Cloud Logging, export to BigQuery for dashboards

**Rationale**:
- GCP Cloud Run auto-captures stdout as logs
- Structured JSON enables easy parsing and aggregation
- BigQuery provides SQL interface for dashboards (Looker Studio, custom tools)
- No additional services needed (no Prometheus, Grafana setup)

**Guidance**:
```python
# audio_processor/observability/metrics.py
import json
from datetime import datetime
from dataclasses import dataclass, asdict

@dataclass
class BatchMetrics:
    batch_id: str
    user_id: str
    status: str

    # Durations
    raw_audio_duration_seconds: float
    speech_duration_seconds: float
    speech_ratio: float
    processing_wall_time_seconds: float
    queue_wait_time_seconds: float

    # Sizes
    raw_audio_size_bytes: int
    cleaned_audio_size_bytes: int

    # Costs
    speechmatics_job_id: str
    speechmatics_cost_estimate: float

    # Stage timings
    transcode_duration_seconds: float
    vad_duration_seconds: float
    denoise_duration_seconds: float
    asr_submit_duration_seconds: float
    asr_wait_duration_seconds: float
    post_process_duration_seconds: float

    # Error tracking
    retry_count: int = 0
    error_stage: str | None = None
    error_message: str | None = None

def log_batch_metrics(metrics: BatchMetrics):
    """Log metrics as structured JSON for ingestion."""
    print(json.dumps({
        "timestamp": datetime.utcnow().isoformat(),
        "severity": "INFO",
        "metric_type": "batch_completion",
        **asdict(metrics)
    }))
```

**BigQuery Schema** (auto-created by log sink):
```sql
-- Table: audio_pipeline.batch_metrics
CREATE TABLE batch_metrics (
  timestamp TIMESTAMP,
  batch_id STRING,
  user_id STRING,
  status STRING,
  raw_audio_duration_seconds FLOAT64,
  speech_duration_seconds FLOAT64,
  speech_ratio FLOAT64,
  speechmatics_cost_estimate FLOAT64,
  -- ... all fields from BatchMetrics
);
```

**Dashboard Queries** (examples):
```sql
-- Daily cost estimate
SELECT
  DATE(timestamp) as date,
  SUM(speechmatics_cost_estimate) as daily_cost
FROM audio_pipeline.batch_metrics
WHERE status = 'completed'
GROUP BY date
ORDER BY date DESC;

-- Average speech ratio (silence trimming effectiveness)
SELECT AVG(speech_ratio) as avg_speech_ratio
FROM audio_pipeline.batch_metrics
WHERE status = 'completed';

-- Error rate by stage
SELECT
  error_stage,
  COUNT(*) as failure_count
FROM audio_pipeline.batch_metrics
WHERE status = 'failed'
GROUP BY error_stage;
```

---

### **Decision 8: Emotion Provider Schema Design — Tag, Don't Normalise**

**Decision**: Store the `provider` string in `emotion.json` and let downstream
consumers branch on it. Do not attempt to normalise provider schemas into a
common format.

**Rationale**: The candidate providers produce fundamentally different
representations — a -1/+1 polarity score (Google NL), 48 continuous emotion
dimensions (Hume), 7-class categorical with confidence (j-hartmann), and
arousal/dominance/valence triplets (audeering). Normalising these into a common
schema would lose information (e.g., collapsing 48 Hume dimensions to positive/
negative) or require an unstable union type that changes as providers are added.
Tagging with `provider` and preserving the native schema means: (a) no
information loss, (b) no normalisation bugs, (c) adding a new provider requires
only a new engine class and a new schema entry in the documentation, not a
migration.

**Guidance**:
- Downstream consumers (Android app, future AI layer) must switch on `provider`
  before reading `analysis`. Document this contract clearly in the API
  surface where `emotion.json` is exposed.
- When adding a new provider, add its schema to Section 3.5 of this TDD and to
  FR-035 in the PRD before implementing.
- The `provider_version` field allows schema evolution within a single provider
  (e.g. if Google NL v3 changes the response shape, downstream can gate on it).
- Emotion is best-effort: if `transcript_emotion_path` is null in D1 or the
  status endpoint response, downstream must handle it gracefully (treat as no
  emotion data available, not as an error).

---

## 7. Open Questions & PRD Gaps

| # | Question | Impact | Proposed Resolution |
| :--- | :--- | :--- | :--- |
| 1 | **Pub/Sub subscription credentials for Android**: How does the Android app authenticate to Cloudflare Pub/Sub? | Blocks FR-041 implementation | Use Google OAuth `sub` claim as MQTT client ID, Worker generates short-lived MQTT credentials via API endpoint `/v1/pubsub/credentials` |
| 2 | **R2 bucket naming and creation**: Should we use one global bucket or per-environment buckets (dev/staging/prod)? | Affects deployment and testing | Use per-environment buckets: `audio-pipeline-dev`, `audio-pipeline-prod`. Document in deployment guide. |
| 3 | **D1 database recovery from R2**: Should we build the DR recovery script as part of MVP or defer to ops runbook? | Low urgency but affects DR confidence | Defer to ops runbook (document algorithm in Section 6, Decision 2). Script can be built post-MVP if DR test is needed. |
| 4 | **Priority queue implementation**: Cloudflare Queues support FIFO but not priority lanes out-of-box. How to implement "immediate" priority? | Affects FR-003 (upload priority flag) | Use two separate queues: `audio-processing-jobs-priority` and `audio-processing-jobs-normal`. GCP consumer polls priority queue first. |
| 5 | **Speechmatics rate limits**: What are Speechmatics API rate limits and quotas? Do we need to throttle submissions? | May affect throughput at scale | Confirm limits with Speechmatics account manager. If needed, add queue throttling (max N concurrent ASR jobs). Document in constraints. |

---

## 8. Risk Register

| Risk | Likelihood | Impact | Mitigation |
| :--- | :--- | :--- | :--- |
| **Cloudflare Pub/Sub MQTT auth complexity**: Android MQTT client integration may be more complex than anticipated | Medium | Medium | Prototype MQTT connection in Android app early (spike task). If too complex, fall back to polling `/v1/status` with exponential backoff. |
| **R2 → GCP bandwidth costs**: R2 egress is free, but GCP Cloud Run ingress may have quotas or unexpected costs | Low | Medium | Monitor GCP network ingress in early testing. R2 egress is explicitly zero-fee per Cloudflare docs. |
| **Picovoice licensing**: Server license costs may be higher than estimated | Low | High | Confirm Picovoice server/Linux license pricing before purchasing. Budget $500-1000/month for unlimited processing (verify with vendor). |
| **Speechmatics latency**: Batch API may take minutes for long audio, blocking queue throughput | Medium | Medium | Set ASR timeout to 10 minutes (600s). If timeout common, explore Speechmatics Real-Time API (streaming) as alternative. |
| **D1 query performance at scale**: 10 users × 100 batches/day = 365K rows/year. D1 indexes may degrade. | Low | Low | Current indexes (user_id, status, recording_started_at) should handle this scale. Monitor p95 query latency. If slow, add composite indexes or migrate to PostgreSQL. |
| **GCP Cloud Run cold starts**: First request after idle may take 5-10s, delaying queue processing | Medium | Low | Enable Cloud Run minimum instances (min=1) to keep one instance warm. Cost: ~$10/month for always-on instance. |
| **OAuth token caching stale tokens**: If Google revokes token, Worker cache may serve stale validation for up to 1 hour | Low | Medium | Accept risk (1-hour window is acceptable for this use case). If tighter revocation needed, reduce cache TTL to 5 minutes or validate every request (slower). |

---

## 9. Deployment & Configuration

### Environment Variables

**Cloudflare Worker** (`wrangler.toml` secrets):
```toml
[env.production]
R2_BUCKET = "audio-pipeline-prod"
DB = "audio-pipeline-db"
PROCESSING_QUEUE = "audio-processing-jobs-normal"
PROCESSING_QUEUE_PRIORITY = "audio-processing-jobs-priority"
PUBSUB_NAMESPACE = "audio-pipeline"
TOKEN_CACHE = "token-cache"  # KV namespace

# Secrets (set via `wrangler secret put`)
# INTERNAL_SECRET = "..." (shared with GCP for event publishing)
```

**GCP Cloud Run** (environment variables):
```bash
R2_ENDPOINT=https://<account-id>.r2.cloudflarestorage.com
R2_BUCKET=audio-pipeline-prod
R2_ACCESS_KEY_ID=<...>
R2_SECRET_ACCESS_KEY=<...>

CLOUDFLARE_WORKER_URL=https://audio-pipeline.workers.dev
CLOUDFLARE_INTERNAL_SECRET=<...>

SPEECHMATICS_API_KEY=<...>

PICOVOICE_ACCESS_KEY=<...>

LOG_LEVEL=INFO
```

---

## 10. Testing Strategy

### Unit Tests

**Cloudflare Worker** (Vitest):
- `batch-id.test.ts`: Validate timestamp format, UUID uniqueness
- `validation.test.ts`: Zod schema validation for upload payloads
- `auth/google.test.ts`: Mock Google tokeninfo responses, cache behavior

**GCP Service** (pytest):
- `test_transcode.py`: Validate ffmpeg command generation, 16kHz output
- `test_vad.py`: Mock Cobra VAD, verify speech segment extraction
- `test_speechmatics.py`: Mock Speechmatics API, verify response parsing
- `test_emotion.py`:
  - Mock Google NL API, verify `emotion.json` envelope structure and `provider` field
  - Verify non-fatal behaviour: Google NL 503 → `run_emotion_analysis` returns
    None, pipeline continues to `completed`
  - Verify empty-segments case: no API call made, `segments: []` returned
  - Verify runner registry: unknown provider logs warning and returns None

### Integration Tests

- **Upload → R2 → D1**: Use Cloudflare's Miniflare (local Worker + R2 + D1 emulation)
- **Queue → GCP → Speechmatics**: Use Speechmatics test API key, real audio files (5-10s samples)
- **Event Publishing**: Verify Pub/Sub message format and user-scoping

### End-to-End Test

- Deploy to staging environment
- Upload test audio from Android emulator
- Verify:
  - Batch created in D1 with `status = "uploaded"`
  - GCP processes audio, Speechmatics returns transcript
  - D1 updated to `status = "completed"`
  - Pub/Sub event received on Android
  - Transcript downloadable via `/v1/download`

---

## 11. Migration & Rollout Plan

### Phase 1: MVP Deployment (Week 1-2)
- Deploy Cloudflare Worker (upload + status endpoints)
- Deploy GCP service (processing pipeline)
- Manual testing with 1-2 users

### Phase 2: Android App Integration (Week 3)
- Update Android app to target Worker endpoint (instead of Google Drive)
- Implement MQTT subscription for completion events
- Beta test with 3-5 users

### Phase 3: Production Rollout (Week 4)
- Monitor metrics (error rate, latency, cost)
- Gradual rollout: 10% → 50% → 100% of users
- Disable Google Drive upload path once stable

---

## 12. Future Enhancements (Out of Scope for MVP)

- **Web UI**: Browse transcripts, playback audio with synchronized text
- **Speaker identification**: Map "Speaker 1" to contact names via voice prints or calendar context
- **Multi-language support**: Auto-detect language, pass to Speechmatics
- **Real-time streaming**: Explore Speechmatics Real-Time API for live transcription
- **Emotion provider upgrade**: Swap Google NL for Hume AI (audio-based, 48-dim
  prosody) or audeering wav2vec2 (self-hosted, dimensional) by implementing the
  `EmotionEngine` interface. No pipeline changes required.
- **Cost optimization**: Cache cleaned audio in cheaper storage tier (Glacier) after 30 days

---

*Last Updated: 2026-02-22*
