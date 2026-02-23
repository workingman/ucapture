# cloudflare-audio-processor — Session Notes

## Session: 2026-02-22 — PRD & TDD Creation

### Status
✅ **PRD Complete**: `docs/prd-audio-pipeline.md` (with emotion analysis)
✅ **TDD Complete**: `docs/tdd-audio-pipeline.md` (with emotion analysis)
✅ **Architecture Diagrams**: Both PRD and TDD have companion Mermaid diagrams
✅ **Process Standards Updated**: All process prompts updated with Mermaid guidelines

---

## Summary

Created comprehensive Product Requirements Document (PRD) and Technical Design Document (TDD) for the ubiquitous audio capture pipeline. The system enables always-on ambient recording from Android devices, with cloud-based processing that includes VAD, noise suppression, ASR transcription, and emotion analysis.

**Key Achievement**: Complete end-to-end specification ready for GitHub issue generation and implementation.

---

## Deliverables

### Documents Created

1. **PRD** (`docs/prd-audio-pipeline.md`)
   - 35 functional requirements (FR-001 through FR-035)
   - 8 key decisions including OAuth 2.0, Cloudflare/GCP split, pluggable emotion analysis
   - Acceptance criteria in Given/When/Then format
   - Companion sequence diagram

2. **TDD** (`docs/tdd-audio-pipeline.md`)
   - 11 technology choices with rationale
   - Complete data models (R2 naming, D1 schema, metadata format)
   - REST API contracts (4 endpoints)
   - Directory structures for both TypeScript (Worker) and Python (GCP) services
   - 7 key implementation decisions with code examples
   - 5 open questions flagged for resolution
   - 7 technical risks with mitigations
   - Companion component diagram

3. **Mermaid Diagrams**
   - `docs/prd-audio-pipeline-figure1.mmd` — Sequence diagram (52 lines)
   - `docs/tdd-audio-pipeline-figure1.mmd` — Component architecture (78 lines)
   - Both use pure Mermaid syntax (no code fences)
   - Edge labels quoted for parser compatibility

### Process Standards Updated

Updated all process prompts with Mermaid diagram standards:
- `process/create-prd.md`
- `process/create-tdd.md`
- `process/ideate.md`
- `process/diagram.md`

**New Standard**: Diagrams named `{prd|tdd}-[feature]-figure[N].mmd`, contain ONLY valid Mermaid syntax (no ` ```mermaid ` fences).

---

## Key Architectural Decisions

### 1. Authentication (OAuth 2.0 with Google)
**Decision**: Leverage existing Google authentication from Android app
**Rationale**: Android already authenticates for Drive access; reuse those tokens
**Implementation**: Worker validates tokens via Google tokeninfo endpoint, caches 1 hour in KV

### 2. Event Delivery (Cloudflare Pub/Sub + MQTT, persistent sessions)
**Decision**: Use Cloudflare Pub/Sub for completion events to Android
**Rationale**: MQTT is mobile-friendly, supports persistent connections, user-scoped topics
**Offline delivery**: Android connects with `clean_session=false` + QoS 1 subscription so broker queues events while phone is offline and delivers on reconnect
**Open**: Confirm Cloudflare Pub/Sub offline queue depth/TTL limits (TDD Q6); fall back to `GET /v1/batches` catch-up poll if limits are exceeded
**Alternative Rejected**: Polling (inefficient), WebSocket (more complex), FCM (external dependency — but viable fallback if Pub/Sub queue limits prove insufficient)

### 3. Processing Runtime (Python 3.11 on GCP Cloud Run)
**Decision**: Python for all GCP processing (not Node.js)
**Rationale**: First-class Picovoice SDK support, Speechmatics client library, simpler deployment
**Note**: OK to mix languages across architectural boundaries (TypeScript for Worker, Python for GCP)

### 4. Batch ID Format (Timestamp + UUID, GMT)
**Decision**: `YYYYMMDD-HHMMSS-GMT-{uuid4}` (e.g., `20260222-143027-GMT-a3f2c1b9...`)
**Rationale**: DR-safe (can reconstruct D1 index from R2 listing), human-readable, sortable
**GMT Timezone**: Avoids DST ambiguity; UI converts to locale

### 5. Emotion Analysis (Pluggable, Google Cloud NL Starting Point)
**Decision**: Modular emotion provider interface with provider field tagging output JSON
**Starting Provider**: Google Cloud Natural Language API (cheap, native GCP, text-only)
**Documented Alternatives**: Hume AI (audio-based, highest quality), self-hosted HuggingFace models
**Best-Effort**: Emotion analysis failure does not fail batch; logged and skipped

---

## Architecture Pattern

### Three-Tier Deployment

**Tier 1: Android App (uCapture)**
- OAuth 2.0 with Google
- Multipart upload to Cloudflare
- MQTT subscription for completion events

**Tier 2: Cloudflare Edge (TypeScript Worker)**
- Upload handler: multipart → R2, create D1 batch, enqueue job
- Auth middleware: OAuth token validation with KV caching
- Status handler: query D1 by batch_id (user-scoped)
- Event publisher: Pub/Sub to user-scoped topic
- Storage: R2 (zero egress), D1 (batch index), Queue (FIFO + priority), Pub/Sub (MQTT)

**Tier 3: GCP Cloud Run (Python Processing Service)**
- Queue consumer: pull jobs from Cloudflare Queue
- Audio pipeline: transcode → Cobra VAD → Koala denoise → Speechmatics ASR → emotion analysis
- Result writer: store to R2, update D1, trigger completion event
- External APIs: Speechmatics (ASR), emotion provider (Google Cloud NL default)

### Data Flow (Happy Path)

1. **Upload** (sync): Android → Worker → R2 + D1 + Queue → `202 Accepted`
2. **Processing** (async): Queue → GCP → transcode → Cobra → Koala → Speechmatics → Emotion → R2 + D1
3. **Completion** (async): GCP → Worker API → Pub/Sub → Android (MQTT)
4. **Status Query** (optional): Android → Worker → D1 → response

---

## Data Safety & DR

### DR-Safe File Naming
- **Format**: `{user_id}/{batch_id}/{artifact_type}/{filename}`
- **Batch ID**: Embeds recording start timestamp + UUID
- **Recovery**: D1 can be reconstructed from R2 bucket listing alone
- **Algorithm**: Documented in TDD Section 6, Decision 2

### Audio Durability Contract
- **Android**: Keeps audio until `202 Accepted` response (file in R2)
- **Backend**: Never deletes raw audio on processing failure
- **Retry**: 3 attempts with exponential backoff; batch marked `failed` after exhaustion
- **Reprocessing**: Failed batches can be re-queued without re-upload

### User Isolation
- **R2 Paths**: All prefixed with `{user_id}` from OAuth token
- **Worker Enforcement**: Rejects any request where authenticated user ≠ path prefix
- **D1 Queries**: All scoped to `user_id` from token
- **Pub/Sub Topics**: User-scoped: `batch-completions/{user_id}`

---

## Modularity & Extensibility

### Pluggable ASR Interface (FR-033)
- **Current**: Speechmatics Batch API
- **Alternatives**: Whisper, Deepgram, AssemblyAI
- **Swap Method**: Configuration change (no code changes to pipeline)
- **Interface**: `ASREngine.transcribe(audio_path, metadata) → Transcript`

### Pluggable Emotion Provider Interface (FR-035)
- **Current**: Google Cloud Natural Language API (text-based sentiment)
- **Alternatives**:
  - Hume AI (audio-based, 48-dimensional emotion space)
  - j-hartmann/distilroberta (7 categorical emotions: anger, disgust, fear, joy, neutral, sadness, surprise)
  - audeering/wav2vec2 (arousal, dominance, valence from audio)
- **Provider Tagging**: JSON output includes `provider` field so downstream consumers can branch on schema
- **Schemas**: Provider-specific, versioned by `provider` field (no normalization — preserves fidelity)
- **Best-Effort**: Failure logged; batch still completes; `transcript_emotion_path` left null in D1

---

## Observability

### Per-Batch Metrics (Logged on Completion)
- Upload artifact sizes (raw audio bytes, metadata bytes, total)
- Audio durations (raw input, speech-only, speech ratio)
- Processing wall-clock time per stage (transcode, VAD, denoise, ASR, emotion, post-process)
- End-to-end latency (upload timestamp → completed status)
- Queue wait time
- Speechmatics job ID + cost estimate
- Retry count (0 if first attempt succeeded)
- Final status + error stage + error message (if failed)

### System-Wide / Aggregated Metrics
- Batches processed per hour/day (throughput)
- Error rate by stage (upload, VAD, denoise, ASR, emotion, post-processing)
- R2 storage consumed (raw audio, cleaned audio, transcript) — per user and system-wide
- Cumulative Speechmatics cost (rolling 30-day, per user, system-wide)
- Queue depth (backlog of unprocessed or retrying batches)
- Active concurrent GCP jobs
- D1 read/write latency (p50, p95)
- Per-user batch count and audio hours (for capacity planning)

### Logging Strategy
- **Format**: Structured JSON to stdout
- **Ingestion**: GCP Cloud Logging (auto-capture)
- **Analysis**: Export to BigQuery for SQL dashboards

---

## Outstanding Items (Open Questions from TDD Section 7)

These need resolution **before GitHub issue generation**:

1. **Pub/Sub MQTT auth + persistent sessions for Android**: How does Android authenticate to Cloudflare Pub/Sub, and do Cloudflare's credential types support `clean_session=false` persistent sessions?
   - **Proposed**: Worker API endpoint `/v1/pubsub/credentials` generates short-lived MQTT credentials using Google OAuth `sub` as stable client ID (e.g. `ucapture-{sub}`). Must verify persistent session support with these credentials.

2. **R2 bucket naming**: One global or per-environment?
   - **Proposed**: Per-environment: `audio-pipeline-dev`, `audio-pipeline-prod`

3. **D1 recovery script**: Build as part of MVP or defer to ops runbook?
   - **Proposed**: Defer to runbook; algorithm already documented in TDD Decision 2

4. **Priority queue implementation**: Cloudflare Queues lack native priority lanes
   - **Proposed**: Two separate queues (`audio-processing-jobs-priority`, `audio-processing-jobs-normal`); GCP consumer polls priority first

5. **Speechmatics rate limits**: What are API quotas? Need throttling?
   - **Proposed**: Confirm with Speechmatics account manager; add queue throttling (max N concurrent ASR jobs) if needed

6. **Cloudflare Pub/Sub offline queue depth and TTL**: How many messages does the broker queue per offline client, and for how long?
   - **Proposed**: Check Cloudflare docs / confirm with support. If limits are low (e.g. <24h retention), add `GET /v1/batches` catch-up poll on reconnect as a safety net for extended offline gaps.

---

## Technical Highlights

### Zero-Egress Architecture
- **R2 Storage**: $0.015/GB/month storage, $0 egress to GCP
- **Comparison**: S3 charges ~$0.09/GB egress to GCP (6x more expensive at scale)
- **Impact**: 10 users × 8 hours/day × 30 days = ~7.2TB/year raw audio
  - R2 cost: ~$108/year storage + $0 egress
  - S3 equivalent: ~$108/year storage + **$650/year egress**

### Async Queue-Driven Processing
- **Upload returns immediately**: `202 Accepted` with `batch_id`
- **No blocking**: Worker doesn't wait for 5-30 minute processing pipeline
- **Scalability**: GCP Cloud Run scales to zero when idle, scales up under load
- **Retry isolation**: Failed batches don't block subsequent uploads

### Event-Driven Completion
- **No polling**: Android subscribes to MQTT topic `batch-completions/{user_id}`
- **Real-time notification**: Receives event when transcript ready
- **Battery efficient**: MQTT persistent connection cheaper than HTTP polling
- **Payload**: Includes `batch_id`, `status`, `artifact_paths`, `recording_started_at` for correlation

---

## Technology Stack Summary

| Layer | Technology | Language | Purpose |
|-------|-----------|----------|---------|
| **Client** | Android (uCapture) | Kotlin | Audio recording, upload, event subscription |
| **Ingest** | Cloudflare Workers | TypeScript | Upload handling, auth, indexing, event publishing |
| **Storage** | Cloudflare R2 | N/A | Zero-egress artifact storage |
| **Index** | Cloudflare D1 | SQL (SQLite) | Batch metadata, status tracking |
| **Queue** | Cloudflare Queues | N/A | Job queuing (FIFO + priority) |
| **Events** | Cloudflare Pub/Sub | MQTT | Completion notifications |
| **Processing** | GCP Cloud Run | Python 3.11 | Audio pipeline orchestration |
| **VAD** | Picovoice Cobra | Native (via Python) | Voice activity detection |
| **Denoise** | Picovoice Koala | Native (via Python) | Noise suppression |
| **ASR** | Speechmatics Batch API | SaaS | Speech-to-text + diarization |
| **Emotion** | Google Cloud NL (default) | SaaS | Sentiment/emotion analysis |
| **Observability** | GCP Cloud Logging + BigQuery | SQL | Metrics, dashboards |

---

## Risk Mitigation

### High Priority
- **Picovoice licensing**: Confirm server/Linux license pricing (estimated $500-1000/month)
  - **Action**: Contact Picovoice sales before MVP
- **Pub/Sub MQTT auth complexity**: Android MQTT integration may be harder than expected
  - **Mitigation**: Prototype early; fallback to polling `/v1/status` with exponential backoff if needed

### Medium Priority
- **Speechmatics latency**: Batch API may take minutes for long audio
  - **Mitigation**: 10-minute timeout; monitor in testing; consider Real-Time API if timeout common
- **GCP cold starts**: First request after idle may take 5-10s
  - **Mitigation**: Enable Cloud Run min=1 instance (~$10/month for always-on)

### Low Priority
- **D1 query performance**: 365k rows/year expected (10 users × 100 batches/day)
  - **Mitigation**: Current indexes sufficient; monitor p95 latency; migrate to PostgreSQL if degradation
- **OAuth token cache staleness**: 1-hour KV cache may serve revoked tokens
  - **Mitigation**: Acceptable risk; reduce TTL to 5 minutes if tighter revocation needed

---

## Files Modified in Session

### Created
- `docs/prd-audio-pipeline.md`
- `docs/tdd-audio-pipeline.md`
- `docs/prd-audio-pipeline-figure1.mmd`
- `docs/tdd-audio-pipeline-figure1.mmd`

### Updated
- `process/create-prd.md` (Mermaid guidelines)
- `process/create-tdd.md` (Mermaid guidelines)
- `process/ideate.md` (diagram tools section)
- `process/diagram.md` (naming convention note)
- `docs/prd-audio-pipeline.md` (added D-8, FR-034, FR-035 for emotion analysis)
- `docs/tdd-audio-pipeline.md` (added emotion to GCP responsibilities)

---

## Next Steps

### Immediate (Before Issue Generation)
1. ⏳ **Resolve 5 open questions** (TDD Section 7)
2. ⏳ Confirm Picovoice server license pricing
3. ⏳ Validate Speechmatics Batch API rate limits/quotas
4. ⏳ Test Cloudflare Pub/Sub MQTT connection from Android (spike task)

### Issue Generation
Once open questions resolved:
1. Run `process/create-issues.md` prompt with PRD + TDD as input
2. Generate GitHub Issues with dependency graph
3. Tag issues with waves (Wave 1 = foundation, no dependencies)

### Implementation Waves
- **Wave 1** (Foundation, parallel):
  - Cloudflare Worker (upload + status endpoints)
  - GCP Cloud Run service (processing pipeline)
  - D1 schema migration
  - R2 bucket setup
- **Wave 2** (Integration):
  - Android app changes (OAuth + Pub/Sub subscription)
  - End-to-end testing
- **Wave 3** (Rollout):
  - Beta test with 3-5 users
  - Production rollout: 10% → 50% → 100%
  - Disable Google Drive upload path

---

## Lessons Learned

### What Worked Well
1. **Clarifying questions upfront**: Asking about auth, events, runtime, naming before writing saved rework
2. **External Mermaid diagrams**: LLM-parseable, viewer-compatible, version-controllable
3. **Iterative refinement**: Adding emotion analysis mid-session showed modularity working
4. **Provider tagging pattern**: Storing `provider` field instead of normalizing schemas preserves fidelity

### Process Improvements Applied
1. **Mermaid file format**: Standardized on pure syntax (no code fences) across all prompts
2. **Diagram naming**: Document-specific prefixes (`prd-`, `tdd-`) with sequential numbering
3. **Edge label quoting**: Quote labels with special chars (`/`, `+`, `()`) for parser compatibility
4. **Open questions section**: Flagging unknowns instead of assuming improves pre-implementation clarity

---

## Decisions From Previous Session (2026-02-17)

### Silence Handling
**On-device (android-recorder)**:
- Phone polls `MediaRecorder.getMaxAmplitude()` every 500ms during recording
- Amplitude log (boolean or 8-bit value per interval) included in metadata JSON
- If an entire chunk is silent: upload metadata only — no audio file
  - Metadata `audio_file` field: `null`
  - Metadata `skip_reason` field: `"silent_chunk"`

**Server-side (this service)**:
- On ingest, read amplitude log from metadata
- Use ffmpeg to trim silent regions from audio before storing to R2 (minimize storage cost)
- Pass trimmed audio + time-offset map to VAD/ASR pipeline
- Silent-chunk metadata records (no audio) stored in D1 for continuity but marked `skipped/silent`

**Note**: This optimization is compatible with current TDD design (preprocessing step before Cobra VAD).

---

## Session Metrics

- **Duration**: ~2.5 hours
- **Documents created**: 2 major (PRD, TDD) + 2 diagrams
- **Process docs updated**: 4
- **Token usage**: ~156k / 200k (78% at session end)
- **Functional requirements**: 35 (FR-001 through FR-035)
- **Key decisions**: 8 (PRD) + 7 (TDD)
- **Open questions**: 5 (flagged for resolution)
- **Technical risks**: 7 (with mitigations)

---

## Quality Checks Completed

### PRD
- ✅ Follows `process/create-prd.md` template
- ✅ All 6 sections present (Metadata, Problem, Decisions, FRs, Non-Goals, Constraints)
- ✅ Acceptance criteria in Gherkin format
- ✅ Companion diagram referenced

### TDD
- ✅ Follows `process/create-tdd.md` template
- ✅ All 9 sections present
- ✅ Technology choices with rationale + alternatives
- ✅ Concrete data models (field names, types, constraints)
- ✅ Specific interface contracts (can code against them)
- ✅ Implementation decisions with code examples
- ✅ Open questions explicitly flagged
- ✅ Companion diagram referenced

### Diagrams
- ✅ Pure Mermaid syntax (no markdown fences)
- ✅ Document-specific naming
- ✅ Edge labels quoted for compatibility
- ✅ Color-coded for clarity
- ✅ Parseable by viewers

### Alignment
- ✅ PRD and TDD consistent with each other
- ✅ Diagrams align with written specs
- ✅ Emotion analysis integrated across all artifacts

---

## Conclusion

Successfully created production-ready PRD and TDD for the ubiquitous audio capture pipeline. Both documents provide complete specifications for:
- Product requirements (WHAT to build)
- Technical design (HOW to build it)
- Architecture diagrams (visual understanding)

The modular design supports future enhancements (swap ASR engines, add emotion providers) without breaking existing functionality. The DR-safe file naming and audio durability contract ensure data safety at scale.

**Status**: ~~Ready for open question resolution → GitHub issue generation~~ → parallel agent execution

---

*Session completed: 2026-02-22*

---

## Session: 2026-02-23 — GitHub Issue Generation

### Status
✅ **Issue generation complete**: 8 parent issues + 35 sub-issues = 43 total
✅ **All sub-issues linked** to parent issues via GitHub sub-issues API
✅ **Dependencies documented** in each sub-issue body (GraphQL API unavailable)
✅ **Self-validation** passed for all 8 parents (AC coverage, FR coverage, TDD coverage)

---

### Issues Created

| Parent | Title | Sub-Issues | Count |
|--------|-------|------------|-------|
| #1 | Worker project scaffolding and data layer | #9, #10, #11, #12, #13 | 5 |
| #2 | Authentication and upload endpoint | #27, #28, #29, #30, #31 | 5 |
| #3 | Query endpoints (status, batches, download) | #14, #15, #16, #17 | 4 |
| #4 | GCP service scaffolding and audio processing | #18, #19, #20, #21, #22 | 5 |
| #5 | ASR integration with modular interface | #23, #24, #25, #26 | 4 |
| #6 | Pluggable emotion analysis | #32, #33, #34 | 3 |
| #7 | Queue orchestration, event delivery, and retry | #39, #40, #41, #42, #43 | 5 |
| #8 | Observability and metrics | #35, #36, #37, #38 | 4 |

### Cross-Parent Dependency Graph

```
#1 (Worker data layer) ──┬──→ #2 (Auth + Upload) ──→ #3 (Query endpoints)
                          │
#4 (GCP scaffold) ──→ #5 (ASR) ──→ #6 (Emotion)
                          │              │              │
                          └──────────────┴──────────────┴──→ #7 (Orchestration)
                                                                     │
                                                               #8 (Observability)
```

**Parallel tracks:** #1–#3 (Worker/TypeScript) and #4–#6 (GCP/Python) can be built
independently, converging at #7 (orchestration).

### Implementation Order (suggested)

**Wave 1 — Foundation (parallel):**
- #1 Worker scaffolding (#9→#10,#11,#12,#13)
- #4 GCP scaffolding (#18→#19,#20→#21→#22)

**Wave 2 — Core features (parallel after Wave 1):**
- #2 Auth + upload (#27→#28→#29→#30→#31)
- #5 ASR integration (#23→#24,#25→#26)

**Wave 3 — Extensions (parallel after Wave 2):**
- #3 Query endpoints (#14,#15,#16→#17)
- #6 Emotion analysis (#32→#33→#34)

**Wave 4 — Integration (after Waves 1–3):**
- #7 Orchestration (#39,#40→#41→#42,#43)

**Wave 5 — Polish (after Wave 4):**
- #8 Observability (#35→#36→#37,#38)

### Process Notes

- **Issue creation process**: `process/create-issues.md` worked well with the
  three-phase approach (plan → dependency analysis → create). Planning agents
  produced thorough coverage maps. Execution agents created well-structured issues.
- **Context management**: One planning agent per parent (8 parallel), then one
  execution agent per parent (8 parallel, max 5 sub-issues each). Stayed within
  the 5-sub-issue-per-invocation cap.
- **GitHub dependency API**: The `addIssueDependency` GraphQL mutation requires
  GitHub Enterprise. Not available on free/Team plans. Dependencies documented
  in issue bodies instead — adequate for the `execute-issues.md` orchestrator.
- **Sub-issue linking**: REST API `repos/{owner}/{repo}/issues/{parent}/sub_issues`
  works on all plans. Used successfully for all 35 sub-issues.
- **PRD/TDD discrepancy found**: FR-034 says empty transcript produces
  `emotion.json` with `segments: []`; TDD `runner.py` code returns `None`.
  Issue #34 directs implementer to follow PRD.

### TODOs Before Coding

1. ⏳ **Resolve open questions** (TDD Section 7) — particularly:
   - Q1: Pub/Sub MQTT auth — verify Cloudflare Pub/Sub supports persistent
     sessions with short-lived credentials
   - Q6: Pub/Sub offline queue depth/TTL — check Cloudflare docs or support
2. ⏳ **Confirm Picovoice server license** pricing for Cloud Run
3. ⏳ **Confirm Speechmatics plan** includes diarization + check rate limits
4. ⏳ **Consider GitHub Enterprise** if automated dependency tracking becomes
   valuable (adds `addIssueDependency` GraphQL mutation, ~$21/user/month)
5. ⏳ **Create `.claude/CLAUDE.md`** with Agent Execution Rules before coding
   (referenced in every sub-issue footer)

---

*Session completed: 2026-02-23*
*Next session: Begin coding — Wave 1 (Parents #1 and #4 in parallel)*
