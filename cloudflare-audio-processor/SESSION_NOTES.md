# cloudflare-audio-processor — Session Notes

## Status
No code yet. PRD complete (`docs/prd-audio-pipeline.md`).

---

## Decisions To Implement

### Silence handling (2026-02-17)

**On-device (android-recorder):**
- Phone polls `MediaRecorder.getMaxAmplitude()` every 500ms during recording
- Amplitude log (boolean or 8-bit value per interval) included in metadata JSON
- If an entire chunk is silent: upload metadata only — no audio file
  - Metadata `audio_file` field: `null`
  - Metadata `skip_reason` field: `"silent_chunk"` (or similar)

**Server-side (this service):**
- On ingest, read amplitude log from metadata
- Use ffmpeg to trim silent regions from audio before storing to R2
  - Goal: minimize file size and storage cost
- Pass trimmed audio (+ time-offset map) to VAD/ASR pipeline
- Silent-chunk metadata records (no audio) should be stored in D1 for continuity
  but require no processing — mark status as `skipped/silent`

---

## Next Task
Read PRD and begin TDD (Technical Design Document).
See TDD template: `/Users/sam/dev/mmv/process/create-tdd.md`
