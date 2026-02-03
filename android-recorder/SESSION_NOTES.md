# uCapture Session Notes

## Project
Android audio recording app with GPS/calendar metadata, Google Drive upload.

**Package:** `ca.dgbi.ucapture`
**Stack:** Kotlin, Jetpack Compose, MVVM, Room, Hilt, WorkManager
**SDK:** min 29, target 35, compile 36

## Status
| Task | Status |
|------|--------|
| 1.0 Project setup | Complete |
| 2.0 Audio recording service | Complete |
| 3.0 Metadata collection | Complete |
| 4.0 Local storage (Room) | Complete |
| 5.0 Google Drive integration | Complete |
| 6.0 UI | Complete |

## What's Working
- Google Sign-In via Credential Manager
- Token persistence (EncryptedSharedPreferences)
- Drive authorization and folder creation
- Recording with chunking (30-min default, production settings)
- Chunks upload to Drive with JSON metadata sidecars
- Auto-retry: hourly periodic retry + immediate retry on sign-in
- **Rock-solid recording that survives navigation**
- **Pause immediately creates chunk (no lost audio)**
- **Stop creates final chunk before ending**

## Key Changes This Session (2026-02-03)

### Recording Reliability Overhaul
1. **Service lifecycle fix** - Recording now uses `startForegroundService()` instead of just `bindService()`. This ensures the service survives when user navigates to Timeline/Settings.

2. **Pause creates chunk immediately** - When paused, audio is stopped and saved as a completed chunk. Resume starts a fresh chunk in the same session.

3. **Stop creates final chunk** - If actively recording, stop finalizes the current chunk before ending. If paused, chunk was already saved.

4. **Record button resumes** - Tapping the big red button when paused will resume (no need to find the small resume button).

5. **Chunk duration restored** - 30-min default, 5-min minimum (was 1-min for testing).

## Key Files Modified This Session
```
service/RecordingService.kt       # Pause creates chunk, stop creates chunk
service/ChunkManager.kt           # endCurrentChunkForPause(), startNewChunkForResume()
ui/recording/RecordingScreen.kt   # startForegroundService, intent-based controls, record resumes
```

## Architecture Notes

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

## Next Steps
1. **Clean up debug logging** - Remove verbose mutex/auth logs from GoogleDriveAuthManager
2. **Fix test failures** - SettingsViewModelTest has stale tests referencing removed methods
3. **Handle token expiration** - Access tokens expire after 1 hour (currently requires re-sign-in)

## Commands
```bash
cd /Users/gwr/Documents/dev/ubiq-capture/android-recorder/android
./gradlew build
./gradlew installDebug
adb -s 49180DLAQ003R6 logcat -d | grep -iE "ucapture|upload|drive"
```

## Device
- Pixel 9 (Android 16) - serial: 49180DLAQ003R6

---
**Created:** 2025-12-13
**Updated:** 2026-02-03
