# PRD: Audio Recording Android App (ubiq-capture)

## 1. Introduction/Overview

The ubiq-capture Android app is the first component of a three-part audio capture and processing system. This app enables users to record continuous audio from their device's microphone throughout the day, automatically chunking recordings into manageable file sizes and uploading them to cloud storage for later processing.

**Problem Statement:** Users need a reliable, hands-free way to capture audio throughout their day without worrying about storage management, manual uploads, or file organization. The recordings will be processed by a separate backend system to generate transcripts and metadata, accessible via a web frontend.

**System Architecture Overview:**
- **Part 1 (This PRD):** Android recording app - Captures and uploads audio
- **Part 2 (Future):** Backend processing service - Transcription and metadata generation
- **Part 3 (Future):** Web frontend - Access recordings and derived data

## 2. Goals

1. Enable continuous, reliable audio recording on Android devices with minimal user intervention, operating reliably in background with screen off or phone locked
2. Automatically manage local storage by uploading recordings and verifying successful transfer, while retaining recent audio for local replay
3. Provide configurable audio quality settings to balance file size and recording fidelity
4. Chunk long recordings into manageable file sizes for efficient upload and processing
5. Capture rich contextual metadata (GPS location, calendar meetings) to enhance AI processing and transcription accuracy
6. Create a foundation that supports future migration from Google Drive to Google Cloud Storage
7. Handle all common error scenarios gracefully (no internet, permissions, storage limits)

## 3. User Stories

**US-1:** As a user, I want to start recording with a single tap so that I can quickly capture audio without complex setup.

**US-2:** As a user, I want the app to automatically chunk my recordings into smaller files so that uploads are manageable and I don't lose entire day's recording if something goes wrong.

**US-3:** As a user, I want to configure where my recordings are uploaded in Google Drive so that I can organize them according to my preferences.

**US-4:** As a user, I want to adjust audio quality settings so that I can balance storage/bandwidth needs with recording fidelity.

**US-5:** As a user, I want the app to automatically delete local files after successful upload (while retaining recent recordings for replay) so that my device storage doesn't fill up.

**US-6:** As a user, I want to replay recent recordings on a vertically scrolling timeline (showing timestamps, and eventually transcribed text snippets) so that I can quickly find and reference parts of conversations.

**US-7:** As a user, I want the app to pause and resume recording so that I can temporarily stop capturing audio without ending the session.

**US-8:** As a user, I want clear error notifications when recording or upload fails so that I can take corrective action.

**US-9:** As a user, I want my recordings to automatically capture location data so that I can remember where conversations took place and provide context for AI processing.

**US-10:** As a user, I want my recordings to automatically link to calendar meeting information so that the transcription and AI processing can understand the meeting context.

## 4. Functional Requirements

### 4.1 Core Recording Features

**FR-1:** The app must request and handle the following permissions appropriately, explaining why each is needed:
   - Microphone (for audio recording)
   - Location (for contextual metadata and meeting location tracking)
   - Calendar read access (for meeting metadata association)
   - Foreground service permission (for background recording)
   - Notification permission (for persistent recording notification)
   - Battery optimization exemption (to prevent system from stopping recording)

**FR-2:** The app must provide clear recording controls: start, pause, resume, and stop.

**FR-3:** The app must support continuous recording that can span an entire day (24+ hours), continuing to operate when the screen is off or the phone is locked.

**FR-4:** The app must automatically chunk recordings into files of reasonable size (starting with 30-60 minute chunks, to be determined through empirical testing). Architecture must support future dynamic chunking strategies (e.g., meeting-aware chunking, silence trimming).

**FR-5:** The app must record audio in medium quality (MP3, 128kbps) by default.

**FR-6:** The app must save recordings to local device storage temporarily until upload is complete.

**FR-7:** The app must use a consistent file naming convention that includes timestamp with timezone (e.g., `ubiq-YYYYMMDD-HHMMSS-PDT-[chunk-number].mp3`). Metadata must include precise clock measurements (Unix timestamp with milliseconds) for recording start, recording end, and each GPS sample.

### 4.2 Settings & Configuration

**FR-8:** The app must provide a settings screen where users can configure:
   - Audio quality (Low: 64kbps, Medium: 128kbps, High: 256kbps)
   - GPS sampling interval (code-configurable, default: 1 minute; future: user-configurable in web frontend)
   - Local audio retention period (how long to keep recordings on-device after upload for replay)
   - Maximum local storage limit for recordings (stop recording when limit reached)
   - Low storage warning threshold (default: 500MB)
   - Google Drive destination folder
   - Future: GCS bucket configuration (placeholder for post-MVP)

**FR-9:** The app must allow users to select/change their Google Drive upload destination folder.

**FR-10:** The app must persist user settings across app restarts.

### 4.3 Upload & Sync

**FR-11:** The app must authenticate with Google Drive using OAuth 2.0.

**FR-12:** The app must automatically upload completed recording chunks to the configured Google Drive folder.

**FR-13:** The app must verify successful upload by comparing MD5 hash of local file with uploaded file.

**FR-14:** The app must delete local files after successful upload verification, but retain recordings for a user-configurable period (e.g., last 30 minutes, 1 hour, 24 hours) to enable local replay functionality.

**FR-15:** The app must queue uploads when network is unavailable and retry when connectivity is restored. Wait for chunks to complete before uploading (don't upload partial chunks).

**FR-16:** The app must function as a background app, uploading recordings in the background (using WorkManager or similar) even when not in foreground, with screen off, or phone locked.

**FR-17:** The app must handle upload failures gracefully with retry logic (exponential backoff).

### 4.4 User Interface

**FR-18:** The app must display recording status (recording, stopped, paused).

**FR-19:** The app must show current recording duration and estimated file size.

**FR-20:** The app must display a vertically scrolling timeline view of retained local audio showing:
   - Timestamp for each recording segment
   - Recording duration indicators
   - Visual indication of current playback position
   - Future: Transcribed text snippets (when on-device transcription is implemented)

**FR-21:** The app must provide audio playback with the ability to:
   - Tap on timeline entries to jump to specific times
   - Scrub through audio within the timeline
   - Play/pause controls

**FR-22:** The app must display clear error messages and notifications for all error scenarios.

### 4.5 Storage & File Management

**FR-23:** The app must monitor available local storage and warn users when space is low (user-configurable threshold, default: 500MB).

**FR-24:** The app must prevent recording if insufficient storage is available.

**FR-25:** The app must calculate and display storage usage by the app.

### 4.6 Error Handling

**FR-26:** The app must handle "no internet connection" by queuing uploads and showing appropriate status.

**FR-27:** The app must handle "storage full" by stopping recording and notifying the user.

**FR-28:** The app must handle "microphone permissions denied" by showing clear instructions to grant permission.

**FR-29:** The app must handle "upload failures" with retry logic and user notification after max retries.

**FR-30:** The app must handle "Google Drive authentication failures" by prompting re-authentication.

**FR-30a:** The app must handle "location permissions denied" by continuing to record audio without location metadata and notifying the user that location context will not be available.

**FR-30b:** The app must handle "calendar permissions denied" by continuing to record audio without calendar metadata and notifying the user that meeting context will not be available.

**FR-30c:** The app must handle "battery optimization" and "background restrictions" by prompting the user to grant exemptions, explaining that these are required for reliable continuous recording.

### 4.7 Architecture for Future Integration

**FR-31:** The app must structure recording metadata in a format that can be easily consumed by backend processing (JSON or similar).

**FR-32:** Metadata should include:
   - Recording ID (UUID)
   - Start timestamp
   - End timestamp
   - Duration
   - File size
   - Audio format/quality
   - MD5 hash
   - Device identifier (anonymized)
   - Upload timestamp
   - Storage location (Drive path/GCS URI)
   - Location data (array of GPS samples):
     - Timestamp
     - Latitude
     - Longitude
     - Altitude
     - Accuracy
     - Provider
   - Calendar events (array of overlapping calendar entries):
     - Event title
     - Event description
     - Start time
     - End time
     - Location (from calendar)
     - Attendees
     - Event ID
     - Calendar name

**FR-33:** The app's storage abstraction layer must be designed to support easy migration from Google Drive to GCS in the future.

### 4.8 Location & Calendar Metadata

**FR-34:** The app must capture GPS location data during recording, sampled at a configurable interval (default: every 1 minute).

**FR-35:** Location samples must include:
   - Latitude
   - Longitude
   - Altitude (if available)
   - Accuracy estimate
   - Timestamp of GPS reading
   - Provider (GPS, Network, Fused)

**FR-36:** The app must query the device calendar for events that overlap with the recording time period.

**FR-37:** Calendar metadata must include for each overlapping event:
   - Event title
   - Event description
   - Start time
   - End time
   - Location (if specified in calendar)
   - Attendees list (if available)
   - Event ID (for reference)
   - Calendar name/account

**FR-38:** The app must associate calendar events with recording chunks based on time overlap.

**FR-39:** Location and calendar metadata must be stored alongside audio file metadata and uploaded with the recording.

**FR-40:** The app must gracefully handle denied location permissions by recording without location data (with appropriate logging/notification).

**FR-41:** The app must gracefully handle denied calendar permissions by recording without calendar metadata (with appropriate logging/notification).

**FR-42:** Location tracking should optimize for battery efficiency (use fused location provider, adjust accuracy based on context).

**FR-43:** Calendar queries should be efficient and not impact recording performance (query once per chunk, cache results).

## 5. Non-Goals (Out of Scope)

**NG-1:** Audio transcription and processing (handled by backend in Part 2)

**NG-2:** Web-based access to recordings and metadata (handled by web frontend in Part 3)

**NG-3:** Audio editing, trimming, or manipulation features

**NG-4:** Advanced audio features (noise reduction, enhancement, filters)

**NG-5:** Multi-user accounts or team sharing features

**NG-6:** Real-time streaming or live transcription

**NG-7:** iOS version (Android only for MVP)

**NG-8:** Smart recording detection (determining if there's something worth recording) - Future enhancement

**NG-9:** Integration with other cloud storage providers (Dropbox, OneDrive, etc.)

**NG-10:** Full on-device transcription using Whisper or similar models - Future enhancement (Phase 2)

## 6. Design Considerations

### 6.1 UI/UX Requirements

**DC-1:** Design should be minimal and functional, focusing on reliability over aesthetics for MVP.

**DC-2:** Primary screen should feature a prominent record/stop button with clear visual state.

**DC-3:** Use Material Design 3 components for consistency with Android platform.

**DC-4:** Recording status should be visible at a glance (use status bar notification when in background).

**DC-5:** Settings should be easily accessible but not cluttering the main interface.

**DC-6:** Use color coding for upload status:
   - Gray: Pending
   - Blue: Uploading (with progress)
   - Green: Uploaded successfully
   - Red: Failed (with retry option)

**DC-7:** Timeline view design:
   - Vertically scrolling list (most recent at top)
   - Each entry shows timestamp (e.g., "Today 2:30 PM PST")
   - Duration indicator for each segment
   - MVP: Timestamps only
   - Future: Include short transcribed text preview under each timestamp
   - Tappable entries to play audio from that point
   - Visual playback progress indicator

### 6.2 User Flow

1. **First Launch:**
   - Grant required permissions (microphone, location, calendar, notifications, foreground service, battery optimization exemption)
   - Authenticate with Google Drive
   - Configure Google Drive destination folder
   - Optional: Adjust audio quality, retention period, and other settings

2. **Recording Session:**
   - Tap record button
   - App records continuously in background, auto-chunking
   - Use pause/resume as needed
   - Chunks upload automatically in background
   - Local files retained per user-configured retention period, then deleted after upload verification
   - User can stop recording anytime

3. **Replay Recent Audio:**
   - Navigate to vertically scrolling timeline view
   - Browse recordings by timestamp (most recent at top)
   - Tap on timeline entry to play audio from that point
   - Scrub through audio within playback controls
   - Future: Search and browse by transcribed text snippets

## 7. Technical Considerations

### 7.1 Android Specifications

**TC-1:** Minimum SDK: Android 8.0 (API 26) or higher recommended

**TC-2:** Target SDK: Latest stable Android version

**TC-3:** Development language: Kotlin (chosen for modern Android development best practices, null safety, coroutines support, and official Google recommendation)

### 7.2 Architecture

**TC-4:** Follow MVVM (Model-View-ViewModel) architecture pattern

**TC-5:** Use Jetpack Compose for UI (modern Android UI toolkit)

**TC-6:** Use Room database for local metadata storage

**TC-7:** Use WorkManager for reliable background upload tasks

**TC-8:** Implement Repository pattern for data layer abstraction

**TC-9:** Use Hilt/Dagger for dependency injection

### 7.3 Audio Recording

**TC-10:** Use MediaRecorder or AudioRecord API for audio capture

**TC-11:** Record to MP3 format using appropriate encoder

**TC-12:** Use foreground service with persistent notification to keep recording active with screen off and phone locked. Handle wake locks and battery optimization exemptions properly.

### 7.4 Cloud Storage

**TC-13:** Use Google Drive Android API for initial implementation

**TC-14:** Design storage interface/abstraction to allow swapping Drive for GCS:
```kotlin
interface CloudStorageProvider {
    suspend fun authenticate()
    suspend fun upload(file: File, metadata: RecordingMetadata): Result<String>
    suspend fun verifyUpload(localHash: String, remoteId: String): Boolean
    suspend fun delete(remoteId: String): Result<Unit>
}
```

**TC-15:** Store GCS-compatible metadata even when using Drive (prepare for migration)

### 7.4.5 Location & Calendar Integration

**TC-15a:** Use Google Play Services Fused Location Provider for optimal battery efficiency and accuracy

**TC-15b:** Implement location updates with appropriate priority (PRIORITY_BALANCED_POWER_ACCURACY for background tracking)

**TC-15c:** Use Android Calendar Provider API to query calendar events

**TC-15d:** Design metadata collection as separate, modular services that can be enabled/disabled independently:
```kotlin
interface MetadataCollector {
    suspend fun collectMetadata(startTime: Long, endTime: Long): MetadataResult
    fun isAvailable(): Boolean
}

class LocationMetadataCollector : MetadataCollector { ... }
class CalendarMetadataCollector : MetadataCollector { ... }
```

**TC-15e:** Store location and calendar metadata in Room database alongside recording metadata

**TC-15f:** Prefer embedding metadata directly in audio file (using ID3 tags or similar). Fall back to separate JSON sidecar file if embedding is not feasible for MP3 format.

### 7.5 Performance & Battery

**TC-16:** Implement efficient battery usage strategies (doze mode handling)

**TC-17:** Use wake locks judiciously to prevent system from stopping recording

**TC-18:** Optimize upload scheduling to batch when on WiFi/charging if possible

**TC-18a:** Monitor battery impact of location tracking and adjust sampling frequency if battery is low

**TC-18b:** Pause location tracking when device is stationary for extended periods (geofencing optimization)

### 7.6 Security & Privacy

**TC-19:** Store Google Drive credentials securely using Android Keystore

**TC-20:** Do not log sensitive user data or recording content

**TC-21:** Use anonymized device identifiers in metadata (not personal info)

**TC-22:** Encrypt local recordings before upload (optional enhancement for post-MVP)

**TC-22a:** Location data is highly sensitive - ensure it's only used for intended purposes (meeting context, AI processing assistance)

**TC-22b:** Calendar data may contain confidential meeting information - handle with appropriate security:
   - Do not log calendar event details
   - Ensure metadata is transmitted securely
   - Consider allowing users to exclude specific calendars from metadata collection

**TC-22c:** Provide clear privacy policy explaining how location and calendar data will be used

**TC-22d:** Consider implementing user controls to disable location/calendar collection if privacy concerns arise

**TC-22e:** Store location and calendar metadata with same security level as audio recordings (encrypted if recordings are encrypted)

### 7.7 Testing Strategy

**TC-23:** Implement unit tests for business logic (ViewModel, Repository)

**TC-24:** Implement integration tests for upload verification

**TC-25:** Manual testing on multiple devices (different Android versions, manufacturers)

**TC-26:** Test with various recording durations (short, medium, 24+ hours)

**TC-27:** Test error scenarios thoroughly (airplane mode, storage full, etc.)

**TC-27a:** Test location metadata collection in various scenarios:
   - Indoor (GPS unavailable, network location only)
   - Outdoor (GPS available)
   - Moving vs stationary
   - Location permissions denied/granted

**TC-27b:** Test calendar metadata collection with:
   - Various calendar providers (Google, Exchange, local)
   - Overlapping events
   - All-day events
   - Events with/without attendees and locations
   - Calendar permissions denied/granted

**TC-27c:** Verify metadata accuracy by comparing collected location/calendar data with actual device state

## 8. Success Metrics

**SM-1:** Recording reliability: 99%+ successful recording sessions (no crashes, data loss)

**SM-2:** Upload success rate: 95%+ of chunks uploaded successfully within 24 hours

**SM-3:** Storage verification: 100% of uploaded files verified before local deletion

**SM-4:** App crashes: < 1% crash rate across all sessions

**SM-5:** Battery impact: < 15% battery drain over 8-hour recording session (target to measure empirically)

**SM-6:** User can successfully complete first recording and upload within 5 minutes of first launch

**SM-7:** Location metadata capture rate: 90%+ of expected GPS samples successfully collected (when permissions granted)

**SM-8:** Calendar metadata accuracy: 95%+ of actual calendar events during recording time correctly captured

**SM-9:** Battery impact with location tracking: < 20% battery drain over 8-hour recording session (5% increase from baseline)

## 9. Decisions & Future Enhancements

### Resolved Decisions

**D-1: Chunk Size**
- Start with 30-60 minute chunks for MVP
- Architecture must support future dynamic chunking (meeting-aware, silence detection)
- Post-MVP: Don't split meetings across chunks unless meeting exceeds threshold
- Post-MVP: Detect and skip non-transcribable content (long silence periods)

**D-2: Pause/Resume**
- **Decision:** Add pause/resume functionality to MVP

**D-3: Upload Timing**
- **Decision:** Wait for chunks to complete before uploading. Upload completed chunks when network is available.

**D-4: Storage Limits**
- **Decision:** Make maximum local storage limit user-configurable (with sensible defaults)

**D-5: Audio Quality**
- **Decision:** Make compression quality code-configurable, determine optimal settings through empirical testing

**D-6: Local Retention**
- **Decision:** Provide user-configurable retention period for local replay (not full backup). Delete after MD5 verification + retention period.

**D-7: DST Handling**
- **Decision:** Include timezone abbreviation (PDT/PST) in filename and full timezone info in metadata timestamps

**D-8: Background Recording**
- **Decision:** Critical requirement - must work with screen off and phone locked

**D-9: GPS Sampling Interval**
- **Decision:** Start with 1-minute sampling for testing/development
- Post-MVP: Implement adaptive sampling based on movement detection
- Goal: Optimize for battery over granularity in production

**D-10: Calendar Events Spanning Chunks**
- **Decision:** Include calendar event metadata in all chunks that overlap with the event

**D-11: Location Precision**
- **Decision:** Use precise location data. Privacy is not a concern for this individual-use app.

**D-12: Metadata Format**
- **Decision:** Prefer embedded metadata in audio files (ID3 tags). Fall back to JSON sidecar if needed.

**D-13: Metadata Usage in AI Processing**
- Location: Help user remember where conversations occurred, support personal note use cases
- Calendar: Extract to-do lists, promises, action items, meeting sentiment analysis

### Future Enhancements (Post-MVP)

**FE-1:** Smart recording detection - "worth recording" algorithm vs simple silence detection (see NG-8)

**FE-2:** Quick voice notes feature - timestamp-based note annotation during recording

**FE-3:** Geofencing for meeting location detection (low priority)

**FE-4:** Calendar event type filtering (personal, private, declined meetings)

**FE-5:** Manual metadata editing/redaction before upload

**FE-6:** On-device transcription preview using Whisper (Phase 2, see NG-10)
   - Display transcribed text snippets in timeline view
   - Enable text search within retained recordings
   - Provide quick preview before full cloud transcription

---

## Next Steps

1. Review and approve this PRD
2. Create task list using generate-tasks.md process
3. Set up Android project structure
4. Begin implementation starting with core recording functionality
5. Create PRD for backend processing system (Part 2)
6. Create PRD for web frontend (Part 3)
