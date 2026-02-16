# uCapture Architecture

## Overview

uCapture is an Android audio recording app that captures audio with contextual metadata (GPS location, calendar events) and uploads to Google Drive. The architecture follows **MVVM** (Model-View-ViewModel) with a service layer for background recording.

```
┌─────────────────────────────────────────────────────────────────┐
│                          UI Layer                               │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐              │
│  │  Recording  │  │  Timeline   │  │  Settings   │  (Compose)   │
│  │   Screen    │  │   Screen    │  │   Screen    │              │
│  └──────┬──────┘  └──────┬──────┘  └──────┬──────┘              │
│         │                │                │                     │
│  ┌──────▼──────┐  ┌──────▼──────┐  ┌──────▼──────┐              │
│  │  Recording  │  │  Timeline   │  │  Settings   │  (ViewModels)│
│  │  ViewModel  │  │  ViewModel  │  │  ViewModel  │              │
│  └──────┬──────┘  └─────────────┘  └─────────────┘              │
└─────────┼───────────────────────────────────────────────────────┘
          │ binds to
┌─────────▼───────────────────────────────────────────────────────┐
│                       Service Layer                             │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │                   RecordingService                        │   │
│  │  (Foreground Service - orchestrates everything)           │   │
│  └──────┬─────────────────┬─────────────────┬───────────────┘   │
│         │                 │                 │                   │
│  ┌──────▼──────┐   ┌──────▼──────┐   ┌──────▼──────────────┐   │
│  │ AudioRecorder│   │ChunkManager │   │MetadataCollector   │   │
│  │             │   │             │   │     Manager         │   │
│  │ MediaRecorder│   │ File naming │   │  ┌───────────────┐ │   │
│  │ AAC encoding│   │ Auto-rotate │   │  │Location       │ │   │
│  │ Pause/Resume│   │ 30-min chunks│   │  │Collector      │ │   │
│  └─────────────┘   └─────────────┘   │  └───────────────┘ │   │
│                                       │  ┌───────────────┐ │   │
│                                       │  │Calendar       │ │   │
│                                       │  │Collector      │ │   │
│                                       │  └───────────────┘ │   │
│                                       └────────────────────┘   │
└─────────────────────────────────────────────────────────────────┘
          │ writes to / reads from
┌─────────▼───────────────────────────────────────────────────────┐
│                        Data Layer                               │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────────┐  │
│  │    Room     │  │    File     │  │     Google Drive        │  │
│  │  Database   │  │   Storage   │  │     (via WorkManager)   │  │
│  │ (Task 4.0)  │  │  .m4a files │  │      (Task 5.0)         │  │
│  └─────────────┘  └─────────────┘  └─────────────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
```

## Layer Responsibilities

### UI Layer (Task 6.0 - Core Complete)
- **Screens**: Jetpack Compose UI — Recording, Timeline, Settings
- **ViewModels**: Hold UI state via `StateFlow`, handle user actions
- **Navigation**: Compose Navigation for screen transitions
- **Remaining**: Audio playback (6.16-6.19), some settings UI (quality, retention, storage)

### Service Layer (Tasks 2.0, 3.0 - Complete)
The heart of the app. Runs as a **foreground service** so recording continues when the app is backgrounded or the screen is off.

### Data Layer (Tasks 4.0, 5.0 - Complete)
- **Room**: Local SQLite database for recordings and metadata
- **File Storage**: Audio files stored in app's private storage
- **Cloud**: Google Drive upload via WorkManager with silent token refresh and error classification

## Key Components

### RecordingService
The orchestrator. It's a foreground service (required for long-running background work on Android) that:
- Manages recording lifecycle (start/pause/resume/stop)
- Displays a persistent notification
- Holds a wake lock to prevent CPU sleep during recording
- Coordinates AudioRecorder, ChunkManager, and MetadataCollectors

```kotlin
// Simplified flow
RecordingService.startRecording()
  → AudioRecorder.start(file, quality)
  → ChunkManager.startNewSession()
  → MetadataCollectorManager.startAll()
  → ChunkManager.startChunkTimer() // auto-rotate every 30 min
```

### AudioRecorder
Wraps Android's `MediaRecorder` API:
- **Format**: AAC in M4A container (Android can't encode MP3)
- **Quality levels**: 64/128/256 kbps
- **Pause/Resume**: Native support on Android 24+
- **Sample rate**: 44.1 kHz mono

### ChunkManager
Handles automatic file rotation:
- Default chunk duration: 30 minutes (configurable 5-120 min)
- File naming: `ucap-YYYYMMDD-HHMMSS-TZ-NNN.m4a`
- Emits `CompletedChunk` events when chunks finish
- Timer pauses when recording is paused

### Metadata Collectors
Pluggable system for gathering contextual data:

**LocationMetadataCollector**:
- Uses Fused Location Provider (Google Play Services)
- Samples every 60 seconds (configurable)
- PRIORITY_BALANCED_POWER_ACCURACY (battery-friendly)
- Stores samples in memory, filters by chunk time range

**CalendarMetadataCollector**:
- Queries Android Calendar Provider
- Finds events overlapping with recording time
- Caches results per chunk (queries once, not continuously)
- Extracts title, description, location, attendees

Both collectors handle missing permissions gracefully - recording continues without that metadata type.

## Dependency Injection (Hilt)

Hilt manages object creation and lifecycles:

```
AppModule.kt
├── provideAudioRecorder(context)         → singleton
├── provideChunkManager()                  → singleton
├── provideLocationMetadataCollector(ctx)  → singleton
├── provideCalendarMetadataCollector(ctx)  → singleton
└── provideMetadataCollectorManager(...)   → singleton (with collectors registered)
```

This allows easy testing (swap real implementations for mocks) and ensures single instances where needed.

## Data Flow

### Recording Flow
```
User taps Record
    │
    ▼
RecordingViewModel.startRecording()
    │
    ▼
RecordingService.startRecording()
    │
    ├──► AudioRecorder.start()      → creates .m4a file
    ├──► ChunkManager.start()       → tracks timing, schedules rotation
    └──► MetadataCollectors.start() → begins sampling location/calendar

    ... time passes ...

ChunkManager timer fires (30 min)
    │
    ▼
RecordingService.rotateChunk()
    │
    ├──► AudioRecorder.stop() then start() with new file
    ├──► ChunkManager.completeCurrentChunk() → emits CompletedChunk
    └──► Collect metadata for completed chunk

    ... eventually ...

User taps Stop
    │
    ▼
RecordingService.stopRecording()
    │
    ├──► AudioRecorder.stop()
    ├──► ChunkManager.endSession()
    ├──► MetadataCollectors.stop()
    └──► (Future) Queue upload to Google Drive
```

### Metadata Association
```
CompletedChunk {
    file: /storage/.../ucap-20251213-153000-PST-001.m4a
    startTime: 2025-12-13T15:30:00-08:00
    endTime: 2025-12-13T16:00:00-08:00
}
    │
    ▼
LocationMetadataCollector.getMetadataForChunk(chunk)
    → filters samples where timestamp in [startTime, endTime]
    → returns List<LocationSample>

CalendarMetadataCollector.getMetadataForChunk(chunk)
    → queries events overlapping [startTime, endTime]
    → returns List<CalendarEvent>
```

## File Structure

```
app/src/main/java/ca/dgbi/ucapture/
├── UCaptureApplication.kt      # Hilt application class
├── di/
│   └── AppModule.kt            # Hilt dependency providers
├── service/
│   ├── RecordingService.kt     # Foreground service
│   ├── AudioRecorder.kt        # MediaRecorder wrapper
│   ├── ChunkManager.kt         # File rotation logic
│   └── metadata/
│       ├── MetadataCollector.kt         # Interface + Manager
│       ├── LocationSample.kt            # Data class
│       ├── CalendarEvent.kt             # Data class
│       ├── LocationMetadataCollector.kt # GPS implementation
│       └── CalendarMetadataCollector.kt # Calendar implementation
├── util/
│   └── PowerUtils.kt           # Battery optimization helpers
├── data/
│   ├── local/                  # Room database (entities, DAOs, converters)
│   ├── model/                  # RecordingMetadata (JSON export)
│   ├── repository/             # RecordingRepository, MetadataRepository
│   └── remote/                 # GoogleDriveStorage, UploadWorker, SecureTokenStorage
└── ui/
    ├── navigation/             # AppNavigation (NavHost)
    ├── recording/              # RecordingScreen + ViewModel
    ├── settings/               # SettingsScreen + ViewModel (Drive auth)
    ├── theme/                  # Material 3 theme (Color, Theme, Type)
    └── timeline/               # TimelineScreen + ViewModel + TimelineItem
```

## Threading Model

- **Main thread**: UI, service lifecycle callbacks
- **Coroutines**: Async operations use `Dispatchers.IO` for file/network/database
- **Location callbacks**: Delivered on main looper, processed quickly
- **WorkManager**: Background uploads run on worker threads

## Permissions

| Permission | Purpose | Required? |
|------------|---------|-----------|
| RECORD_AUDIO | Microphone access | Yes |
| FOREGROUND_SERVICE | Background recording | Yes |
| ACCESS_FINE_LOCATION | GPS metadata | No (graceful degradation) |
| ACCESS_COARSE_LOCATION | Network location | No |
| READ_CALENDAR | Calendar metadata | No (graceful degradation) |
| POST_NOTIFICATIONS | Status notification (Android 13+) | Yes |
| INTERNET | Google Drive upload | Yes |

## Status

Tasks 1-6 are substantially complete (107 unit tests passing). Key remaining work:

- **Audio playback**: `AudioPlayer.kt` for timeline replay (6.16-6.19)
- **Settings completeness**: Quality, retention, storage limit, storage stats UI (6.22-6.25, 6.27)
- **Storage monitoring**: Available/used space calculation, low-space warnings (4.10-4.12)
- **Permission onboarding**: First-launch flow, `PermissionManager.kt` (7.1, 7.9)
- **Error UX**: User-facing error messages and notifications (7.12, 7.13, 7.16)
- **Testing**: Instrumented tests, additional manual testing, documentation (8.x)
