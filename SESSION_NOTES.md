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
| 4.0 Local storage (Room) | **Next** |
| 5.0 Google Drive integration | Pending |
| 6.0 UI | Pending |

## Architecture
See `docs/ARCHITECTURE.md` for full architecture documentation with diagrams.

**Key components:**
- `RecordingService` - Foreground service orchestrator
- `AudioRecorder` - MediaRecorder wrapper (AAC @ 64/128/256 kbps)
- `ChunkManager` - Auto file rotation (30 min default)
- `LocationMetadataCollector` - Fused Location Provider (1 min sampling)
- `CalendarMetadataCollector` - Calendar Provider API (per-chunk caching)

## Task 4.0 Subtasks (Next)
From `tasks/tasks-0001-prd-audio-recording-app.md`:
- 4.1: Create Room entities (Recording, LocationSample, CalendarEvent)
- 4.2-4.6: DAOs and relationships
- 4.7-4.8: Repositories
- 4.9-4.18: File management, hashing, retention

## Key Files
```
android/app/src/main/java/ca/dgbi/ucapture/
├── service/          # RecordingService, AudioRecorder, ChunkManager
├── service/metadata/ # Collectors and data classes
├── di/               # Hilt modules
└── util/             # PowerUtils

docs/ARCHITECTURE.md  # Full architecture documentation

tasks/
├── 0001-prd-audio-recording-app.md       # PRD
└── tasks-0001-prd-audio-recording-app.md # Task list
```

## Commands
```bash
cd /Users/gwr/Documents/dev/ubiq-capture/android
./gradlew build
./gradlew testDebugUnitTest
```

## Tests
- 53 unit tests passing (AudioRecorder, ChunkManager, LocationMetadataCollector, CalendarMetadataCollector)

---
**Updated:** 2025-12-13
