# uCapture Session Notes

## Project
Android audio recording app with GPS/calendar metadata, Google Drive upload.

**Package:** `ca.dgbi.ucapture`
**Stack:** Kotlin, Jetpack Compose, MVVM, Room, Hilt, WorkManager
**SDK:** min 29, target 35, compile 36

## Status
| Task | Status | Notes |
|------|--------|-------|
| 1.0 Project setup | Complete (8/9) | ProGuard rules remaining |
| 2.0 Audio recording service | **Complete** | AAC/M4A (not MP3) |
| 3.0 Metadata collection | Complete (13/14) | Adaptive sampling deferred |
| 4.0 Local storage (Room) | Complete (15/18) | Storage monitoring not yet |
| 5.0 Google Drive integration | Partial (19/20) | Upload progress notification remaining |
| 6.0 UI | Partial (19/29) | Missing: audio playback, some settings |
| 7.0 Permissions/errors | Partial (13/19) | Missing: PermissionManager, onboarding, error UX |
| 8.0 Testing/docs | Partial (14/32) | 107 tests passing, needs instrumented + manual tests |
| Token refresh & upload recovery | Complete | |
| Debug logging cleanup | Complete | |
| Task list & PRD audit | Complete | Updated 2026-02-07 |

## What's Working
- Google Sign-In via Credential Manager
- Token persistence (EncryptedSharedPreferences)
- **Silent token refresh** (tokens auto-refresh before expiry, retry on 401)
- Drive authorization and folder creation
- Recording with chunking (30-min default, production settings)
- Chunks upload to Drive with JSON metadata sidecars
- Auto-retry: hourly periodic retry + immediate retry on sign-in
- **Pending uploads flush on app startup** (not just on sign-in)
- **HTTP error classification** (401→NotAuthenticated, 403 quota→QuotaExceeded, 404→NoTargetFolder)
- Rock-solid recording that survives navigation
- Pause immediately creates chunk (no lost audio)
- Stop creates final chunk before ending
- All 107 unit tests passing

## Key Changes This Session (2026-02-07)

### Project Audit & Documentation
1. **Task list updated** - `tasks/tasks-0001-prd-audio-recording-app.md` fully audited against codebase. ~120 subtasks checked off, PRD deviations documented (AAC vs MP3, JSON sidecar vs ID3, CredentialManager vs Google Sign-In, EncryptedSharedPrefs vs Keystore).
2. **ARCHITECTURE.md updated** - Removed stale "pending" labels, updated file tree, replaced "What's Next" with accurate "Status" section.
3. **PRD mindmap created** - `docs/prd-overview.mmd` (+ .svg, .png) — Mermaid mindmap covering all PRD sections: system overview, goals, user stories, FRs, tech stack, decisions, metrics, future enhancements. Rendered via `@mermaid-js/mermaid-cli`.
4. **session.mmd reviewed** - Existing runtime architecture diagram confirmed as good session memory; PRD mindmap complements it as a static reference.

### Upload Recovery Fix (earlier this session)
1. **Token refresh** - `GoogleDriveAuthManager.refreshToken()` silently calls `AuthorizationClient.authorize()` to get a fresh token without UI (scope already granted).
2. **Proactive refresh** - `ensureFreshToken()` refreshes if token is older than 45 minutes (they expire at 60). Called before every upload and verify.
3. **Retry on auth error** - `GoogleDriveStorage.upload()` catches auth errors, refreshes token, and retries once automatically.
4. **HTTP error classification** - New `classifyHttpError()` parses `GoogleJsonResponseException` status codes instead of treating all errors as generic retries.
5. **Pending uploads on startup** - `UCaptureApplication.onCreate()` now calls `schedulePendingUploads()` so stuck PENDING recordings get re-enqueued every app launch.

### Cleanup
6. **Debug logging removed** - ~20 verbose `Log.d` calls removed from `GoogleDriveAuthManager` (mutex acquisition, step-by-step progress). Only error/warning logs remain.
7. **Tests fixed** - `SettingsViewModelTest` updated for 3-param constructor and `getTargetFolderName()`. `GoogleDriveStorageTest` and `UploadWorkerTest` fixed with test dispatchers and `ensureFreshToken()` mocks. Added `unitTests.isReturnDefaultValues = true` to build.gradle.kts.

## Key Files Modified This Session
```
# Upload recovery & cleanup (earlier)
data/remote/GoogleDriveAuthManager.kt   # refreshToken(), ensureFreshToken(), logging cleanup
data/remote/GoogleDriveStorage.kt       # executeUpload(), classifyHttpError(), retry on auth error
data/remote/UploadWorker.kt             # Diagnostic logging
data/remote/RetryFailedUploadsWorker.kt # Diagnostic logging
UCaptureApplication.kt                  # schedulePendingUploads on startup
app/build.gradle.kts                    # unitTests.isReturnDefaultValues
test/.../SettingsViewModelTest.kt       # Fixed for current API
test/.../GoogleDriveStorageTest.kt      # Test dispatchers, ensureFreshToken mock
test/.../UploadWorkerTest.kt            # Test dispatchers

# Project audit & docs (later)
tasks/tasks-0001-prd-audio-recording-app.md  # Full status audit, PRD deviations
docs/ARCHITECTURE.md                         # Updated status, file tree
docs/prd-overview.mmd                        # New PRD mindmap
docs/prd-overview.svg                        # Rendered SVG
docs/prd-overview.png                        # Rendered PNG
```

## Architecture Notes

### Token Lifecycle
```
Sign-In → accessToken stored + lastTokenRefreshMs set
  ↓
Upload requested → ensureFreshToken()
  ├→ Token < 45 min old → use as-is
  └→ Token stale → refreshToken() via AuthorizationClient.authorize()
      ├→ Success → new token, rebuild Drive service
      └→ Needs resolution → return false (user must re-sign-in)
  ↓
Upload fails with 401 → refreshToken() + retry once
```

### Upload Error Classification
```
GoogleJsonResponseException
  ├→ 401 → NotAuthenticated (refresh token + retry)
  ├→ 403 quota reasons → QuotaExceeded (permanent failure)
  ├→ 403 other → NotAuthenticated (re-auth may help)
  ├→ 404 → NoTargetFolder (folder deleted)
  └→ other → ApiError(code, message)
IOException → NetworkError (transient, retry)
Exception → ApiError(0, message) (transient, retry)
```

### Service Binding vs Starting
- `bindService()` with `BIND_AUTO_CREATE` creates service but destroys it when last client unbinds
- `startForegroundService()` keeps service alive independently
- UI binds for state observation, but commands go via intents

### Chunk Lifecycle
```
Start Recording → Chunk 1 starts
  ↓
[30 min or Pause] → Chunk 1 finalized, persisted, upload queued
  ↓
Resume → Chunk 2 starts (same session)
  ↓
Stop → Chunk 2 finalized (if recording) or cleanup (if paused)
```

## Key Changes This Session (2026-02-17)

### Silence Detection Design
Designed on-device silence detection strategy. No compute-intensive work or licensing on device.

**Approach:**
1. Poll `MediaRecorder.getMaxAmplitude()` every 500ms during recording (free — reads codec's internal peak meter)
2. Store amplitude log (boolean or 8-bit value per interval) in metadata JSON alongside each chunk
3. **Silent chunk short-circuit:** if an entire chunk is silent, upload metadata only — no audio file
   - `audio_file: null`
   - `skip_reason: "silent_chunk"`
4. **Server-side trimming:** GCP pipeline uses the amplitude log + ffmpeg to trim silent regions from audio before storing to R2 (minimizes file size and storage cost)
5. Silent-chunk D1 records stored for session continuity, marked `status: skipped/silent`

**Integration point:** chunk completion in ChunkManager/RecordingService, before handing to upload queue.

See `../cloudflare-audio-processor/SESSION_NOTES.md` for server-side details.

**Task:** #1 in task list (pending implementation).

---

## Next Steps

### Backend Integration (cloudflare-audio-processor)
- **Event subscriber for batch completion** (cloudflare-audio-processor FR-041)
  — When the Cloudflare pipeline finishes processing a batch, the Android app
  should subscribe to the completion event stream filtered by user ID.
  On completion event: mark the recording as processed in local history and
  expose a tap-to-view affordance for the transcript. On failure event: show a
  processing-failed indicator on the history entry.
  Requires:
  1. Choose a push mechanism: CF Queues consumer endpoint, webhook, SSE, or
     polling `/status/{batch_id}` (polling is simplest for MVP).
  2. New `RecordingStatus` state: `TRANSCRIPT_AVAILABLE` and
     `PROCESSING_FAILED` alongside existing `UPLOADED`.
  3. Upload history list item UI: show "Transcript available" tap target.
  4. Transcript viewer screen or bottom sheet displaying formatted transcript
     with inline `[00:15]` timestamp markers and speaker labels.

- **MQTT offline gap — startup polling required**
  The Cloudflare Pub/Sub MQTT event stream does NOT guarantee delivery to
  offline clients. If the phone is off or has no network when a batch
  completes, the completion event is lost. The app must compensate by
  polling `GET /v1/batches` on every app startup and on network reconnect,
  comparing completed batches from the backend against local history, and
  updating any entries that are `completed` on the backend but still show
  as `UPLOADED` locally. MQTT is for real-time convenience when online;
  the startup poll is the reliability guarantee.
  Alternative worth evaluating: replace MQTT with FCM (Firebase Cloud
  Messaging), which queues messages for offline Android devices and delivers
  on reconnect. Already in the Google ecosystem; essentially free.

### Remaining MVP Work (by priority)
1. **RetentionManager fix** — Uploaded files (0.9GB) never get deleted from disk. Files from Feb 3 still present 5 days later. Investigate `RetentionManager` / post-upload cleanup logic. (Discovered 2026-02-08 via ADB after phone reboot; reboot itself was not caused by the app.)
2. **Audio playback** (6.16-6.19) — `AudioPlayer.kt`, play/pause/seek, timeline scrubbing, progress indicator
2. **Settings completeness** (6.22-6.25, 6.27) — audio quality picker, retention period, max storage, low storage threshold, storage stats display
3. **Storage monitoring** (4.10-4.12) — available/used space calculation, low-space warnings
4. **Permission onboarding** (7.1, 7.9) — `PermissionManager.kt`, first-launch flow
5. **Error UX** (7.12, 7.13, 7.16) — storage full handling, mic-in-use handling, user-facing error notifications

### Nice-to-Have
- Upload progress UI (5.15)
- Crash reporting (7.19)
- More unit tests (RecordingRepository, MetadataRepository, HashUtil, RetentionManager)
- Instrumented tests (AppDatabase, RecordingService, upload verification)
- Manual test passes (battery, DST, retention, error scenarios)
- Documentation (README, KDoc, privacy considerations)

### Reference Diagrams
- `session.mmd` — runtime architecture (components, data flow, connections)
- `docs/prd-overview.mmd` — PRD mindmap (goals, stories, requirements, tech, decisions)
- `docs/ARCHITECTURE.md` — written architecture guide with ASCII diagrams

## Commands
```bash
cd /Users/gwr/Documents/dev/ubiq-capture/android-recorder/android
./gradlew build
./gradlew assembleDebug        # Skip test compile (avoids WorkManager KTX dupe)
./gradlew installDebug
./gradlew testDebugUnitTest    # Run all 107 unit tests
adb -s 49180DLAQ003R6 logcat -s UploadWorker GoogleDriveAuthManager GoogleDriveStorage RetryFailedUploads
```

## Known Issues
- `./gradlew build` fails at `bundleDebugClassesToRuntimeJar` due to WorkManager KTX duplicate class. Use `assembleDebug` or `testDebugUnitTest` separately. The KTX artifact is redundant in newer WorkManager versions.

## Device
- Pixel 9 (Android 16) - serial: 49180DLAQ003R6

---
**Created:** 2025-12-13
**Updated:** 2026-02-17
