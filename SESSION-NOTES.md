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
| 3.0 Metadata collection | **Next** |
| 4.0 Local storage (Room) | Pending |
| 5.0 Google Drive integration | Pending |
| 6.0 UI | Pending |

## Task 2.0 Implementation (Complete)

| File | Purpose |
|------|---------|
| `service/RecordingService.kt` | Foreground service, notification, state machine, wake lock |
| `service/AudioRecorder.kt` | MediaRecorder wrapper, AAC @ 64/128/256 kbps, pause/resume |
| `service/ChunkManager.kt` | Auto-chunking (5-120 min), sequential numbering |
| `service/metadata/MetadataCollector.kt` | Interface + MetadataCollectorManager (stubs) |
| `service/metadata/LocationSample.kt` | GPS data class |
| `service/metadata/CalendarEvent.kt` | Calendar event data class |
| `util/PowerUtils.kt` | Battery optimization utilities |
| `di/AppModule.kt` | Hilt providers |

**Tests:** 29 unit tests in `test/.../service/` (AudioRecorderTest, ChunkManagerTest)

**File naming:** `ucap-YYYYMMDD-HHMMSS-TZ-NNN.m4a`

**Key decisions:**
- AAC codec (not MP3 - Android doesn't encode MP3)
- Wake lock held during recording
- Chunk timer pauses when recording pauses
- MetadataCollectorManager already wired into RecordingService

## Task 3.0 Subtasks (Next)
From `tasks/tasks-0001-prd-audio-recording-app.md`:
- 3.1-3.8: LocationMetadataCollector (Fused Location Provider, 1-min sampling)
- 3.9-3.13: CalendarMetadataCollector (Calendar Provider API)
- 3.14: Store metadata in Room with foreign keys to recordings

Key requirements:
- Handle permissions gracefully (continue without if denied)
- Cache calendar queries (once per chunk)
- Periodic location sampling (configurable interval)

## Key Files
```
android/
├── app/src/main/java/ca/dgbi/ucapture/
│   ├── service/          # RecordingService, AudioRecorder, ChunkManager
│   ├── service/metadata/ # MetadataCollector interface, data classes
│   ├── di/               # AppModule
│   └── util/             # PowerUtils
└── app/src/test/.../service/  # Unit tests

tasks/
├── 0001-prd-audio-recording-app.md      # PRD
└── tasks-0001-prd-audio-recording-app.md # Full task list
```

## Commands
```bash
cd /Users/gwr/Documents/dev/ubiq-capture/android
./gradlew build
./gradlew testDebugUnitTest
```

---
**Updated:** 2025-12-13
