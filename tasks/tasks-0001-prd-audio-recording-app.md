# Task List: Audio Recording Android App (uCapture)

Based on PRD: `0001-prd-audio-recording-app.md`

## Current State Assessment

This is a new Android project with no existing codebase. The implementation will follow modern Android development best practices using:
- **Language:** Kotlin
- **Architecture:** MVVM (Model-View-ViewModel)
- **UI:** Jetpack Compose
- **Database:** Room
- **DI:** Hilt/Dagger
- **Background Work:** WorkManager, Foreground Service
- **Compile SDK:** Android 16 (API 36)
- **Target SDK:** Android 15 (API 35)
- **Minimum SDK:** Android 10 (API 29)

## Relevant Files

### Core Application Structure
- `app/build.gradle.kts` - App-level Gradle configuration with all dependencies
- `app/src/main/AndroidManifest.xml` - App manifest with permissions and service declarations
- `app/src/main/java/ca/dgbi/ucapture/UCaptureApplication.kt` - Application class with Hilt setup

### Data Layer
- `app/src/main/java/ca/dgbi/ucapture/data/model/Recording.kt` - Recording entity model
- `app/src/main/java/ca/dgbi/ucapture/data/model/LocationSample.kt` - Location data model
- `app/src/main/java/ca/dgbi/ucapture/data/model/CalendarEvent.kt` - Calendar event model
- `app/src/main/java/ca/dgbi/ucapture/data/model/RecordingMetadata.kt` - Complete metadata model
- `app/src/main/java/ca/dgbi/ucapture/data/local/AppDatabase.kt` - Room database
- `app/src/main/java/ca/dgbi/ucapture/data/local/RecordingDao.kt` - Room DAO for recordings
- `app/src/main/java/ca/dgbi/ucapture/data/local/LocationDao.kt` - Room DAO for location samples
- `app/src/main/java/ca/dgbi/ucapture/data/local/CalendarDao.kt` - Room DAO for calendar events
- `app/src/main/java/ca/dgbi/ucapture/data/repository/RecordingRepository.kt` - Recording data repository
- `app/src/main/java/ca/dgbi/ucapture/data/repository/MetadataRepository.kt` - Metadata repository

### Cloud Storage
- `app/src/main/java/ca/dgbi/ucapture/data/remote/CloudStorageProvider.kt` - Storage interface
- `app/src/main/java/ca/dgbi/ucapture/data/remote/GoogleDriveStorage.kt` - Google Drive implementation
- `app/src/main/java/ca/dgbi/ucapture/data/remote/UploadWorker.kt` - WorkManager for uploads

### Recording Service
- `app/src/main/java/ca/dgbi/ucapture/service/RecordingService.kt` - Foreground recording service
- `app/src/main/java/ca/dgbi/ucapture/service/AudioRecorder.kt` - Audio recording logic
- `app/src/main/java/ca/dgbi/ucapture/service/ChunkManager.kt` - Recording chunk management

### Metadata Collection
- `app/src/main/java/ca/dgbi/ucapture/service/metadata/MetadataCollector.kt` - Metadata collector interface
- `app/src/main/java/ca/dgbi/ucapture/service/metadata/LocationMetadataCollector.kt` - GPS tracking
- `app/src/main/java/ca/dgbi/ucapture/service/metadata/CalendarMetadataCollector.kt` - Calendar queries

### UI Layer
- `app/src/main/java/ca/dgbi/ucapture/ui/MainActivity.kt` - Main activity
- `app/src/main/java/ca/dgbi/ucapture/ui/navigation/AppNavigation.kt` - Navigation setup
- `app/src/main/java/ca/dgbi/ucapture/ui/recording/RecordingScreen.kt` - Main recording screen
- `app/src/main/java/ca/dgbi/ucapture/ui/recording/RecordingViewModel.kt` - Recording view model
- `app/src/main/java/ca/dgbi/ucapture/ui/timeline/TimelineScreen.kt` - Timeline replay screen
- `app/src/main/java/ca/dgbi/ucapture/ui/timeline/TimelineViewModel.kt` - Timeline view model
- `app/src/main/java/ca/dgbi/ucapture/ui/timeline/AudioPlayer.kt` - Audio playback handler
- `app/src/main/java/ca/dgbi/ucapture/ui/settings/SettingsScreen.kt` - Settings screen
- `app/src/main/java/ca/dgbi/ucapture/ui/settings/SettingsViewModel.kt` - Settings view model
- `app/src/main/java/ca/dgbi/ucapture/ui/components/RecordButton.kt` - Custom record button component
- `app/src/main/java/ca/dgbi/ucapture/ui/components/TimelineItem.kt` - Timeline list item component

### Permissions & Utilities
- `app/src/main/java/ca/dgbi/ucapture/util/PermissionManager.kt` - Permission handling utility
- `app/src/main/java/ca/dgbi/ucapture/util/FileManager.kt` - File operations utility
- `app/src/main/java/ca/dgbi/ucapture/util/HashUtil.kt` - MD5 hashing utility
- `app/src/main/java/ca/dgbi/ucapture/util/TimeFormatter.kt` - Timestamp formatting with timezone
- `app/src/main/java/ca/dgbi/ucapture/util/StorageMonitor.kt` - Storage space monitoring
- `app/src/main/java/ca/dgbi/ucapture/util/RetentionManager.kt` - Local file retention logic

### Dependency Injection
- `app/src/main/java/ca/dgbi/ucapture/di/AppModule.kt` - Hilt app module
- `app/src/main/java/ca/dgbi/ucapture/di/DatabaseModule.kt` - Room database module
- `app/src/main/java/ca/dgbi/ucapture/di/NetworkModule.kt` - Network/storage module
- `app/src/main/java/ca/dgbi/ucapture/di/ServiceModule.kt` - Service module

### Preferences
- `app/src/main/java/ca/dgbi/ucapture/data/preferences/AppPreferences.kt` - DataStore preferences

### Test Files
- `app/src/test/java/ca/dgbi/ucapture/ui/recording/RecordingViewModelTest.kt` - Recording ViewModel tests
- `app/src/test/java/ca/dgbi/ucapture/ui/timeline/TimelineViewModelTest.kt` - Timeline ViewModel tests
- `app/src/test/java/ca/dgbi/ucapture/data/repository/RecordingRepositoryTest.kt` - Repository tests
- `app/src/test/java/ca/dgbi/ucapture/util/HashUtilTest.kt` - Utility tests
- `app/src/androidTest/java/ca/dgbi/ucapture/service/RecordingServiceTest.kt` - Service integration tests
- `app/src/androidTest/java/ca/dgbi/ucapture/data/local/AppDatabaseTest.kt` - Database tests

### Notes

- Unit tests should be placed alongside the code files they are testing
- Use `./gradlew test` to run unit tests
- Use `./gradlew connectedAndroidTest` to run instrumented tests on device/emulator
- Follow Kotlin coding conventions and Android architecture best practices
- All coroutines should use proper structured concurrency
- Use StateFlow for UI state management
- Handle all edge cases gracefully with proper error states

## Tasks

- [ ] 1.0 Set up Android project structure and dependencies
  - [x] 1.1 Create new Android Studio project with Empty Compose Activity template
  - [x] 1.2 Configure `build.gradle.kts` (project level) with Kotlin DSL and version catalogs
  - [x] 1.3 Configure `app/build.gradle.kts` with all required dependencies (Hilt, Room, WorkManager, Compose, Coroutines, Google Drive API)
  - [x] 1.4 Set minimum SDK to API 29 (Android 10), target SDK to API 35 (Android 15), and compile SDK to API 36 (Android 16)
  - [x] 1.5 Add internet, microphone, location, calendar, and foreground service permissions to AndroidManifest.xml
  - [x] 1.6 Set up Hilt by creating `UCaptureApplication.kt` with `@HiltAndroidApp`
  - [x] 1.7 Create base package structure (`data`, `domain`, `ui`, `service`, `util`, `di`)
  - [ ] 1.8 Configure ProGuard/R8 rules for production builds
  - [ ] 1.9 Set up version control ignore patterns for Android Studio files

- [ ] 2.0 Implement core audio recording service with background operation
  - [ ] 2.1 Create `RecordingService.kt` as a foreground service extending `Service`
  - [ ] 2.2 Implement service notification with recording status (required for foreground service)
  - [ ] 2.3 Create `AudioRecorder.kt` class using `MediaRecorder` API for MP3 recording
  - [ ] 2.4 Implement recording state machine (IDLE, RECORDING, PAUSED, STOPPED)
  - [ ] 2.5 Add start recording functionality with quality settings (64/128/256 kbps)
  - [ ] 2.6 Implement pause/resume recording functionality
  - [ ] 2.7 Implement stop recording and finalize file
  - [ ] 2.8 Create `ChunkManager.kt` to handle automatic chunking (30-60 minute default)
  - [ ] 2.9 Implement file naming convention with timestamp and timezone (e.g., `ucap-YYYYMMDD-HHMMSS-PDT-001.mp3`)
  - [ ] 2.10 Add wake lock management to prevent system from stopping recording
  - [ ] 2.11 Handle doze mode and battery optimization exemptions
  - [ ] 2.12 Integrate metadata collectors to associate GPS and calendar data with chunks
  - [ ] 2.13 Add service lifecycle management (start, bind, unbind)
  - [ ] 2.14 Register service in AndroidManifest.xml with foreground service type

- [ ] 3.0 Implement metadata collection services (location and calendar)
  - [ ] 3.1 Create `MetadataCollector.kt` interface with `collectMetadata()` and `isAvailable()` methods
  - [ ] 3.2 Create `LocationSample.kt` data class with latitude, longitude, altitude, accuracy, timestamp, provider
  - [ ] 3.3 Create `CalendarEvent.kt` data class with title, description, start/end times, location, attendees, event ID
  - [ ] 3.4 Implement `LocationMetadataCollector.kt` using Fused Location Provider
  - [ ] 3.5 Configure location requests with PRIORITY_BALANCED_POWER_ACCURACY
  - [ ] 3.6 Implement periodic location sampling (default 1 minute interval, code-configurable)
  - [ ] 3.7 Add adaptive sampling logic based on movement detection (future optimization)
  - [ ] 3.8 Handle location permissions gracefully (continue without location if denied)
  - [ ] 3.9 Implement `CalendarMetadataCollector.kt` using Android Calendar Provider API
  - [ ] 3.10 Query calendar for events overlapping with recording time
  - [ ] 3.11 Extract event title, description, times, location, attendees from calendar
  - [ ] 3.12 Handle calendar permissions gracefully (continue without calendar if denied)
  - [ ] 3.13 Cache calendar queries to avoid repeated lookups (once per chunk)
  - [ ] 3.14 Store metadata in Room database with foreign keys to recordings

- [ ] 4.0 Implement local storage and data management
  - [ ] 4.1 Create Room entities: `Recording`, `LocationSample`, `CalendarEvent`
  - [ ] 4.2 Define relationships between recordings and their metadata (one-to-many)
  - [ ] 4.3 Create `AppDatabase.kt` with version 1 and all entities
  - [ ] 4.4 Create `RecordingDao.kt` with CRUD operations and queries
  - [ ] 4.5 Create `LocationDao.kt` for location sample operations
  - [ ] 4.6 Create `CalendarDao.kt` for calendar event operations
  - [ ] 4.7 Create `RecordingRepository.kt` to abstract database operations
  - [ ] 4.8 Create `MetadataRepository.kt` for metadata CRUD
  - [ ] 4.9 Implement `FileManager.kt` for file system operations
  - [ ] 4.10 Add function to calculate available storage space
  - [ ] 4.11 Add function to calculate app storage usage
  - [ ] 4.12 Implement storage space monitoring with configurable thresholds
  - [ ] 4.13 Create `HashUtil.kt` with MD5 hash generation for files
  - [ ] 4.14 Create `RetentionManager.kt` to handle local file retention policy
  - [ ] 4.15 Implement retention logic: keep files for user-configured duration (default: 30 minutes)
  - [ ] 4.16 Add cleanup logic to delete files after retention period expires
  - [ ] 4.17 Create `RecordingMetadata.kt` class to aggregate all metadata for JSON export
  - [ ] 4.18 Implement metadata embedding in MP3 files (ID3 tags) or JSON sidecar

- [ ] 5.0 Implement cloud storage integration (Google Drive)
  - [ ] 5.1 Create `CloudStorageProvider.kt` interface with authenticate, upload, verifyUpload, delete methods
  - [ ] 5.2 Add Google Drive API dependencies to build.gradle
  - [ ] 5.3 Configure OAuth 2.0 credentials (client ID, client secret)
  - [ ] 5.4 Implement `GoogleDriveStorage.kt` implementing CloudStorageProvider
  - [ ] 5.5 Add Google Sign-In for Drive authentication
  - [ ] 5.6 Store Drive credentials securely using Android Keystore
  - [ ] 5.7 Implement folder selection UI for user to choose Drive destination
  - [ ] 5.8 Create upload function for audio files with metadata
  - [ ] 5.9 Implement MD5 verification after upload (compare local hash with Drive file hash)
  - [ ] 5.10 Create `UploadWorker.kt` extending Worker for background uploads
  - [ ] 5.11 Configure WorkManager constraints (network type, battery level)
  - [ ] 5.12 Implement upload queue management (queue when offline, upload when online)
  - [ ] 5.13 Add retry logic with exponential backoff for failed uploads
  - [ ] 5.14 Implement upload status tracking (pending, uploading, uploaded, failed)
  - [ ] 5.15 Add notification for upload progress and completion
  - [ ] 5.16 Handle upload failures with user notification after max retries
  - [ ] 5.17 Design abstraction to support future GCS migration (interface-based approach)

- [ ] 6.0 Implement user interface (recording controls, timeline, settings)
  - [ ] 6.1 Set up Jetpack Compose navigation with NavHost
  - [ ] 6.2 Create `MainActivity.kt` with Hilt integration
  - [ ] 6.3 Create `RecordingScreen.kt` as the main screen
  - [ ] 6.4 Create `RecordingViewModel.kt` with StateFlow for UI state
  - [ ] 6.5 Implement recording controls UI: start, pause, resume, stop buttons
  - [ ] 6.6 Add visual feedback for recording state (recording indicator, pulsing animation)
  - [ ] 6.7 Display current recording duration and estimated file size
  - [ ] 6.8 Add persistent notification showing recording status
  - [ ] 6.9 Create `TimelineScreen.kt` for audio replay
  - [ ] 6.10 Create `TimelineViewModel.kt` to manage retained recordings
  - [ ] 6.11 Implement vertically scrolling LazyColumn for timeline items
  - [ ] 6.12 Create `TimelineItem.kt` composable showing timestamp and duration
  - [ ] 6.13 Display recordings with most recent at top
  - [ ] 6.14 Format timestamps with timezone (e.g., "Today 2:30 PM PST")
  - [ ] 6.15 Add placeholder for future transcription text snippets
  - [ ] 6.16 Create `AudioPlayer.kt` for local audio playback
  - [ ] 6.17 Implement audio playback controls (play, pause, seek)
  - [ ] 6.18 Add timeline scrubbing functionality (tap to jump, drag to seek)
  - [ ] 6.19 Show visual playback progress indicator
  - [ ] 6.20 Create `SettingsScreen.kt` with user preferences
  - [ ] 6.21 Create `SettingsViewModel.kt` with DataStore integration
  - [ ] 6.22 Add audio quality setting (Low/Medium/High - 64/128/256 kbps)
  - [ ] 6.23 Add retention period setting (e.g., 30 min, 1 hour, 24 hours)
  - [ ] 6.24 Add maximum storage limit setting
  - [ ] 6.25 Add low storage warning threshold setting
  - [ ] 6.26 Add Google Drive folder selection
  - [ ] 6.27 Display current storage usage statistics
  - [ ] 6.28 Use Material Design 3 components throughout
  - [ ] 6.29 Implement dark/light theme support

- [ ] 7.0 Implement permissions management and error handling
  - [ ] 7.1 Create `PermissionManager.kt` utility class
  - [ ] 7.2 Implement microphone permission request with rationale
  - [ ] 7.3 Implement location permission request (fine and coarse)
  - [ ] 7.4 Implement calendar permission request (read calendar)
  - [ ] 7.5 Implement notification permission request (Android 13+)
  - [ ] 7.6 Request foreground service permission
  - [ ] 7.7 Implement battery optimization exemption request with explanation dialog
  - [ ] 7.8 Handle permission denial gracefully (show instructions to user)
  - [ ] 7.9 Create permission flow during first launch onboarding
  - [ ] 7.10 Add runtime permission checks before each operation
  - [ ] 7.11 Implement error handling for "no internet connection"
  - [ ] 7.12 Implement error handling for "storage full"
  - [ ] 7.13 Implement error handling for "microphone in use by another app"
  - [ ] 7.14 Implement error handling for "upload failures"
  - [ ] 7.15 Implement error handling for "Google Drive authentication failures"
  - [ ] 7.16 Create user-friendly error messages and notifications
  - [ ] 7.17 Add retry mechanisms for recoverable errors
  - [ ] 7.18 Implement logging for debugging (non-sensitive data only)
  - [ ] 7.19 Add crash reporting setup (optional: Firebase Crashlytics)

- [ ] 8.0 Testing and documentation
  - [ ] 8.1 Write unit tests for `RecordingViewModel`
  - [ ] 8.2 Write unit tests for `TimelineViewModel`
  - [ ] 8.3 Write unit tests for `SettingsViewModel`
  - [ ] 8.4 Write unit tests for `RecordingRepository`
  - [ ] 8.5 Write unit tests for `MetadataRepository`
  - [ ] 8.6 Write unit tests for `HashUtil`
  - [ ] 8.7 Write unit tests for `RetentionManager`
  - [ ] 8.8 Write unit tests for `ChunkManager`
  - [ ] 8.9 Write instrumented tests for `AppDatabase`
  - [ ] 8.10 Write instrumented tests for `RecordingService`
  - [ ] 8.11 Write instrumented tests for upload verification
  - [ ] 8.12 Manual test: Record audio for 5 minutes and verify chunking
  - [ ] 8.13 Manual test: Recording with screen off and phone locked
  - [ ] 8.14 Manual test: Pause/resume functionality
  - [ ] 8.15 Manual test: Upload to Google Drive and verify MD5
  - [ ] 8.16 Manual test: Timeline playback with scrubbing
  - [ ] 8.17 Manual test: Retention policy (files deleted after period expires)
  - [ ] 8.18 Manual test: Location metadata collection (indoor and outdoor)
  - [ ] 8.19 Manual test: Calendar metadata collection with overlapping events
  - [ ] 8.20 Manual test: All error scenarios (no internet, storage full, permissions denied)
  - [ ] 8.21 Manual test: Battery impact over 8-hour recording session
  - [ ] 8.22 Manual test: Recording across DST transition
  - [ ] 8.23 Create README.md with project overview and setup instructions
  - [ ] 8.24 Document code with KDoc comments for public APIs
  - [ ] 8.25 Create developer guide for architecture and key components
  - [ ] 8.26 Document privacy considerations for location and calendar data

---

**Status:** Task list complete with 8 parent tasks and 150+ detailed sub-tasks.
