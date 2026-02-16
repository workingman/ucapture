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

- [x] 1.0 Set up Android project structure and dependencies
  - [x] 1.1 Create new Android Studio project with Empty Compose Activity template
  - [x] 1.2 Configure `build.gradle.kts` (project level) with Kotlin DSL and version catalogs
  - [x] 1.3 Configure `app/build.gradle.kts` with all required dependencies (Hilt, Room, WorkManager, Compose, Coroutines, Google Drive API)
  - [x] 1.4 Set minimum SDK to API 29 (Android 10), target SDK to API 35 (Android 15), and compile SDK to API 36 (Android 16)
  - [x] 1.5 Add internet, microphone, location, calendar, and foreground service permissions to AndroidManifest.xml
  - [x] 1.6 Set up Hilt by creating `UCaptureApplication.kt` with `@HiltAndroidApp`
  - [x] 1.7 Create base package structure (`data`, `domain`, `ui`, `service`, `util`, `di`)
  - [ ] 1.8 Configure ProGuard/R8 rules for production builds
  - [x] 1.9 Set up version control ignore patterns for Android Studio files

- [x] 2.0 Implement core audio recording service with background operation
  - [x] 2.1 Create `RecordingService.kt` as a foreground service extending `Service`
  - [x] 2.2 Implement service notification with recording status (required for foreground service)
  - [x] 2.3 Create `AudioRecorder.kt` class using `MediaRecorder` API ~~for MP3~~ for AAC/M4A recording
  - [x] 2.4 Implement recording state machine (IDLE, RECORDING, PAUSED, STOPPED)
  - [x] 2.5 Add start recording functionality with quality settings (64/128/256 kbps)
  - [x] 2.6 Implement pause/resume recording functionality
  - [x] 2.7 Implement stop recording and finalize file
  - [x] 2.8 Create `ChunkManager.kt` to handle automatic chunking (30-minute default)
  - [x] 2.9 Implement file naming convention with timestamp and timezone (`ucap-YYYYMMDD-HHMMSS-TZ-NNN.m4a`)
  - [x] 2.10 Add wake lock management to prevent system from stopping recording
  - [x] 2.11 Handle doze mode and battery optimization exemptions
  - [x] 2.12 Integrate metadata collectors to associate GPS and calendar data with chunks
  - [x] 2.13 Add service lifecycle management (start, bind, unbind)
  - [x] 2.14 Register service in AndroidManifest.xml with foreground service type

- [x] 3.0 Implement metadata collection services (location and calendar)
  - [x] 3.1 Create `MetadataCollector.kt` interface with `collectMetadata()` and `isAvailable()` methods
  - [x] 3.2 Create `LocationSample.kt` data class with latitude, longitude, altitude, accuracy, timestamp, provider
  - [x] 3.3 Create `CalendarEvent.kt` data class with title, description, start/end times, location, attendees, event ID
  - [x] 3.4 Implement `LocationMetadataCollector.kt` using Fused Location Provider
  - [x] 3.5 Configure location requests with PRIORITY_BALANCED_POWER_ACCURACY
  - [x] 3.6 Implement periodic location sampling (default 1 minute interval, code-configurable)
  - [ ] 3.7 Add adaptive sampling logic based on movement detection (future optimization)
  - [x] 3.8 Handle location permissions gracefully (continue without location if denied)
  - [x] 3.9 Implement `CalendarMetadataCollector.kt` using Android Calendar Provider API
  - [x] 3.10 Query calendar for events overlapping with recording time
  - [x] 3.11 Extract event title, description, times, location, attendees from calendar
  - [x] 3.12 Handle calendar permissions gracefully (continue without calendar if denied)
  - [x] 3.13 Cache calendar queries to avoid repeated lookups (once per chunk)
  - [x] 3.14 Store metadata in Room database with foreign keys to recordings

- [x] 4.0 Implement local storage and data management
  - [x] 4.1 Create Room entities: `RecordingEntity`, `LocationSampleEntity`, `CalendarEventEntity`
  - [x] 4.2 Define relationships between recordings and their metadata (`RecordingWithMetadata`)
  - [x] 4.3 Create `AppDatabase.kt` with version 1 and all entities
  - [x] 4.4 Create `RecordingDao.kt` with CRUD operations and queries
  - [x] 4.5 Create `LocationSampleDao.kt` for location sample operations
  - [x] 4.6 Create `CalendarEventDao.kt` for calendar event operations
  - [x] 4.7 Create `RecordingRepository.kt` to abstract database operations
  - [x] 4.8 Create `MetadataRepository.kt` for metadata CRUD
  - [x] 4.9 Implement `FileManager.kt` for file system operations (including metadata sidecar generation)
  - [ ] 4.10 Add function to calculate available storage space
  - [ ] 4.11 Add function to calculate app storage usage
  - [ ] 4.12 Implement storage space monitoring with configurable thresholds
  - [x] 4.13 Create `HashUtil.kt` with MD5 hash generation for files
  - [x] 4.14 Create `RetentionManager.kt` to handle local file retention policy
  - [x] 4.15 Implement retention logic: keep files for user-configured duration (default: 30 minutes)
  - [x] 4.16 Add cleanup logic to delete files after retention period expires
  - [x] 4.17 Create `RecordingMetadata.kt` class to aggregate all metadata for JSON export
  - [x] 4.18 Implement JSON sidecar files uploaded alongside audio (metadata embedded as JSON, not ID3)

- [x] 5.0 Implement cloud storage integration (Google Drive)
  - [x] 5.1 Create `CloudStorageProvider.kt` interface with authenticate, upload, verifyUpload, delete methods
  - [x] 5.2 Add Google Drive API dependencies to build.gradle
  - [x] 5.3 Configure OAuth 2.0 credentials (CredentialManager + AuthorizationClient)
  - [x] 5.4 Implement `GoogleDriveStorage.kt` implementing CloudStorageProvider
  - [x] 5.5 Add Google Sign-In via CredentialManager for Drive authentication
  - [x] 5.6 Store credentials securely using `SecureTokenStorage` (EncryptedSharedPreferences)
  - [x] 5.7 Implement folder selection UI for user to choose Drive destination
  - [x] 5.8 Create upload function for audio files with metadata JSON sidecar
  - [x] 5.9 Implement MD5 verification after upload (compare local hash with Drive file hash)
  - [x] 5.10 Create `UploadWorker.kt` extending Worker for background uploads
  - [x] 5.11 Configure WorkManager constraints (network required)
  - [x] 5.12 Implement upload queue management (queue when offline, upload when online)
  - [x] 5.13 Add retry logic with exponential backoff for failed uploads
  - [x] 5.14 Implement upload status tracking (PENDING→UPLOADING→UPLOADED/FAILED)
  - [ ] 5.15 Add notification for upload progress and completion
  - [x] 5.16 Handle upload failures with retry (`RetryFailedUploadsWorker` hourly)
  - [x] 5.17 Design abstraction to support future GCS migration (CloudStorageProvider interface)
  - [x] 5.18 *(Added)* Silent token refresh (ensureFreshToken with 45-min threshold, retry on 401)
  - [x] 5.19 *(Added)* HTTP error classification (401→NotAuthenticated, 403→QuotaExceeded, 404→NoTargetFolder)
  - [x] 5.20 *(Added)* Flush pending uploads on app startup (`UCaptureApplication.schedulePendingUploads`)

- [x] 6.0 Implement user interface (recording controls, timeline, settings)
  - [x] 6.1 Set up Jetpack Compose navigation with NavHost (`AppNavigation.kt`)
  - [x] 6.2 Create `MainActivity.kt` with Hilt integration
  - [x] 6.3 Create `RecordingScreen.kt` as the main screen
  - [x] 6.4 Create `RecordingViewModel.kt` with StateFlow for UI state
  - [x] 6.5 Implement recording controls UI: start, pause, resume, stop buttons
  - [x] 6.6 Add visual feedback for recording state (recording indicator, pulsing animation)
  - [x] 6.7 Display current recording duration and estimated file size
  - [x] 6.8 Add persistent notification showing recording status
  - [x] 6.9 Create `TimelineScreen.kt` for audio replay
  - [x] 6.10 Create `TimelineViewModel.kt` to manage retained recordings
  - [x] 6.11 Implement vertically scrolling LazyColumn for timeline items
  - [x] 6.12 Create `TimelineItem.kt` composable showing timestamp and duration
  - [x] 6.13 Display recordings with most recent at top
  - [x] 6.14 Format timestamps with timezone (e.g., "Today 2:30 PM PST")
  - [ ] 6.15 Add placeholder for future transcription text snippets
  - [ ] 6.16 Create `AudioPlayer.kt` for local audio playback
  - [ ] 6.17 Implement audio playback controls (play, pause, seek)
  - [ ] 6.18 Add timeline scrubbing functionality (tap to jump, drag to seek)
  - [ ] 6.19 Show visual playback progress indicator
  - [x] 6.20 Create `SettingsScreen.kt` with user preferences
  - [x] 6.21 Create `SettingsViewModel.kt` (uses GoogleDriveAuthManager directly, not DataStore)
  - [ ] 6.22 Add audio quality setting (Low/Medium/High - 64/128/256 kbps)
  - [ ] 6.23 Add retention period setting (e.g., 30 min, 1 hour, 24 hours)
  - [ ] 6.24 Add maximum storage limit setting
  - [ ] 6.25 Add low storage warning threshold setting
  - [x] 6.26 Add Google Drive folder selection
  - [ ] 6.27 Display current storage usage statistics
  - [x] 6.28 Use Material Design 3 components throughout
  - [x] 6.29 Implement dark/light theme support (Color.kt, Theme.kt, Type.kt)

- [ ] 7.0 Implement permissions management and error handling
  - [ ] 7.1 Create `PermissionManager.kt` utility class
  - [x] 7.2 Implement microphone permission request with rationale
  - [x] 7.3 Implement location permission request (fine and coarse)
  - [x] 7.4 Implement calendar permission request (read calendar)
  - [x] 7.5 Implement notification permission request (Android 13+)
  - [x] 7.6 Request foreground service permission
  - [x] 7.7 Implement battery optimization exemption request (PowerUtils.kt)
  - [x] 7.8 Handle permission denial gracefully (graceful degradation for location/calendar)
  - [ ] 7.9 Create permission flow during first launch onboarding
  - [x] 7.10 Add runtime permission checks before each operation
  - [x] 7.11 Implement error handling for "no internet connection" (WorkManager queues, NetworkError classification)
  - [ ] 7.12 Implement error handling for "storage full"
  - [ ] 7.13 Implement error handling for "microphone in use by another app"
  - [x] 7.14 Implement error handling for "upload failures" (retry logic, RetryFailedUploadsWorker)
  - [x] 7.15 Implement error handling for "Google Drive authentication failures" (401→refresh→retry)
  - [ ] 7.16 Create user-friendly error messages and notifications
  - [x] 7.17 Add retry mechanisms for recoverable errors (exponential backoff, hourly retry worker)
  - [x] 7.18 Implement logging for debugging (non-sensitive data only, debug logs cleaned up)
  - [ ] 7.19 Add crash reporting setup (optional: Firebase Crashlytics)

- [ ] 8.0 Testing and documentation
  - [x] 8.1 Write unit tests for `RecordingViewModel` (RecordingViewModelTest.kt)
  - [x] 8.2 Write unit tests for `TimelineViewModel` (TimelineViewModelTest.kt)
  - [x] 8.3 Write unit tests for `SettingsViewModel` (SettingsViewModelTest.kt)
  - [ ] 8.4 Write unit tests for `RecordingRepository`
  - [ ] 8.5 Write unit tests for `MetadataRepository`
  - [ ] 8.6 Write unit tests for `HashUtil`
  - [ ] 8.7 Write unit tests for `RetentionManager`
  - [x] 8.8 Write unit tests for `ChunkManager` (ChunkManagerTest.kt)
  - [ ] 8.9 Write instrumented tests for `AppDatabase`
  - [ ] 8.10 Write instrumented tests for `RecordingService`
  - [ ] 8.11 Write instrumented tests for upload verification
  - [x] 8.12 Manual test: Record audio for 5 minutes and verify chunking
  - [x] 8.13 Manual test: Recording with screen off and phone locked
  - [x] 8.14 Manual test: Pause/resume functionality
  - [x] 8.15 Manual test: Upload to Google Drive and verify MD5
  - [ ] 8.16 Manual test: Timeline playback with scrubbing
  - [ ] 8.17 Manual test: Retention policy (files deleted after period expires)
  - [ ] 8.18 Manual test: Location metadata collection (indoor and outdoor)
  - [ ] 8.19 Manual test: Calendar metadata collection with overlapping events
  - [ ] 8.20 Manual test: All error scenarios (no internet, storage full, permissions denied)
  - [ ] 8.21 Manual test: Battery impact over 8-hour recording session
  - [ ] 8.22 Manual test: Recording across DST transition
  - [ ] 8.23 Create README.md with project overview and setup instructions
  - [ ] 8.24 Document code with KDoc comments for public APIs
  - [x] 8.25 Create developer guide for architecture and key components (ARCHITECTURE.md)
  - [ ] 8.26 Document privacy considerations for location and calendar data
  - [x] 8.27 *(Added)* Write unit tests for `AudioRecorder` (AudioRecorderTest.kt)
  - [x] 8.28 *(Added)* Write unit tests for `GoogleDriveStorage` (GoogleDriveStorageTest.kt)
  - [x] 8.29 *(Added)* Write unit tests for `UploadWorker` (UploadWorkerTest.kt)
  - [x] 8.30 *(Added)* Write unit tests for `CalendarMetadataCollector` (CalendarMetadataCollectorTest.kt)
  - [x] 8.31 *(Added)* Write unit tests for `LocationMetadataCollector` (LocationMetadataCollectorTest.kt)
  - [x] 8.32 *(Added)* Write unit tests for `TimelineItem` (TimelineItemTest.kt)

---

**Status:** 107 unit tests passing. Tasks 1-6 substantially complete. Key remaining work: audio playback (6.16-6.19), settings UI (6.22-6.25, 6.27), storage monitoring (4.10-4.12), permission onboarding (7.1, 7.9), and additional testing/documentation.

**PRD Deviations:**
- **Audio format**: AAC/M4A instead of MP3 (Android can't encode MP3 natively) — PRD FR-5 updated in practice
- **Metadata format**: JSON sidecar files instead of ID3 tags — PRD FR-32/TC-15f sidecar fallback path taken
- **Auth**: CredentialManager + AuthorizationClient instead of traditional Google Sign-In — modern Android approach
- **Token storage**: EncryptedSharedPreferences via SecureTokenStorage (not raw Android Keystore)

**Updated:** 2026-02-07
