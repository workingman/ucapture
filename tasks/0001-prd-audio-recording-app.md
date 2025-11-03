# PRD: Audio Recording Android App (ubiq-capture)

## 1. Introduction/Overview

The ubiq-capture Android app is the first component of a three-part audio capture and processing system. This app enables users to record continuous audio from their device's microphone throughout the day, automatically chunking recordings into manageable file sizes and uploading them to cloud storage for later processing.

**Problem Statement:** Users need a reliable, hands-free way to capture audio throughout their day without worrying about storage management, manual uploads, or file organization. The recordings will be processed by a separate backend system to generate transcripts and metadata, accessible via a web frontend.

**System Architecture Overview:**
- **Part 1 (This PRD):** Android recording app - Captures and uploads audio
- **Part 2 (Future):** Backend processing service - Transcription and metadata generation
- **Part 3 (Future):** Web frontend - Access recordings and derived data

## 2. Goals

1. Enable continuous, reliable audio recording on Android devices with minimal user intervention
2. Automatically manage local storage by uploading recordings and verifying successful transfer
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

**US-5:** As a user, I want the app to automatically delete local files after successful upload so that my device storage doesn't fill up.

**US-6:** As a user, I want to see a list of my recordings with basic information (date, duration, size, upload status) so that I can verify the app is working correctly.
(GR: actually, I don't think we need to show the list of recordings, that will be part of the web-based system)

**US-7:** As a user, I want to preview/playback recordings locally before they're uploaded so that I can verify recording quality. (GR: and to replay parts of the conversation for reference).

**US-8:** As a user, I want clear error notifications when recording or upload fails so that I can take corrective action.

**US-9:** As a user, I want my recordings to automatically capture location data so that I can remember where conversations took place and provide context for AI processing.

**US-10:** As a user, I want my recordings to automatically link to calendar meeting information so that the transcription and AI processing can understand the meeting context.

## 4. Functional Requirements

### 4.1 Core Recording Features

**FR-1:** The app must request and handle the following permissions appropriately, explaining why each is needed:
   - Microphone (for audio recording)
   - Location (for contextual metadata and meeting location tracking)
   - Calendar read access (for meeting metadata association)

**FR-2:** The app must provide a clear start/stop recording control (button or toggle).

**FR-3:** The app must support continuous recording that can span an entire day (24+ hours).

**FR-4:** The app must automatically chunk recordings into files of reasonable size (exact size to be determined during testing based on empirical usage data, suggest starting with 30-60 minute chunks). (GR: we may try some dynamic chunking too so that meetings are contained in a single recording and long quiet periods can be trimmed, I see you noted that in NG-8; ensure the design can handle this after mvp)

**FR-5:** The app must record audio in medium quality (MP3, 128kbps) by default.

**FR-6:** The app must save recordings to local device storage temporarily until upload is complete.

**FR-7:** The app must use a consistent file naming convention that includes timestamp and metadata (e.g., `ubiq-YYYYMMDD-HHMMSS-[chunk-number].mp3`). (GR: the metadata should also include precise clock measurements for the start and end of the file and for each GPS sample)

### 4.2 Settings & Configuration

**FR-8:** The app must provide a settings screen where users can configure:
   - Audio quality (Low: 64kbps, Medium: 128kbps, High: 256kbps)
   - GPS sampling interval (code-configurable, default: 1 minute; future: user-configurable in web frontend)
   - Google Drive destination folder
   - Future: GCS bucket configuration (placeholder for post-MVP)

**FR-9:** The app must allow users to select/change their Google Drive upload destination folder.

**FR-10:** The app must persist user settings across app restarts.

### 4.3 Upload & Sync

**FR-11:** The app must authenticate with Google Drive using OAuth 2.0.

**FR-12:** The app must automatically upload completed recording chunks to the configured Google Drive folder.

**FR-13:** The app must verify successful upload by comparing MD5 hash of local file with uploaded file.

**FR-14:** The app must delete local files only after successful upload verification. (GR: let's keep the last X minutes on-device, configurable by the user.)

**FR-15:** The app must queue uploads when network is unavailable and retry when connectivity is restored.

**FR-16:** The app must upload recordings in the background (using WorkManager or similar) even if the app is not in foreground. (GR: good point, let's make sure tha whole app can function as a background app - update the PRD accordingly)

**FR-17:** The app must handle upload failures gracefully with retry logic (exponential backoff).

### 4.4 User Interface

**FR-18:** The app must display recording status (recording, stopped, paused).

**FR-19:** The app must show current recording duration and estimated file size.

**FR-20:** The app must display a list of recordings showing:
   - Date/time of recording
   - Duration
   - File size
   - Upload status (pending, uploading, uploaded, failed)
   (GR: I don't think we need to show the recording files, but we should show a timeline of available audio that the user can replay - retained as per FR-14)

**FR-21:** The app must provide basic audio playback for local recordings.

**FR-22:** The app must display clear error messages and notifications for all error scenarios.

### 4.5 Storage & File Management

**FR-23:** The app must monitor available local storage and warn users when space is low (< 500MB, (GR: configurable in user settings)).

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

(GR: add in the permissions to run in the background)

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

**NG-10:** Background recording with screen off (may require additional battery optimization work) (GR: ok, we can leave this out of the MVP but I definitely want recording to continue when the phone is locked/screen-off)

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

### 6.2 User Flow

1. **First Launch:**
   - Grant microphone permission
   - Authenticate with Google Drive
   - Configure Google Drive destination folder
   - Optional: Adjust audio quality settings
   
   (GR: may need microphone, location, and background permissions here too)

2. **Recording Session:**
   - Tap record button
   - App records continuously, auto-chunking
   - Chunks upload automatically in background
   - Local files deleted after verification (GR: with some retention for replay of the last X minutes, configurable)
   - User can stop recording anytime

3. **Viewing Recordings:**
   - Navigate to recordings list (GR: make this just the "replay the last X minutes stuff with a timeline rather than file list.)
   - View recording details
   - Play recording locally (if not yet uploaded/deleted)
   - Check upload status

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

**TC-12:** Consider using foreground service with notification to keep recording active

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

**TC-15f:** Include metadata in JSON format when uploading to cloud storage (separate .json file or embedded in audio file metadata)

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

## 9. Open Questions

**OQ-1:** What is the optimal chunk size for recordings? (Requires empirical testing with real usage)
   - Consider: Upload reliability, file size, processing efficiency
   - Suggested starting point: 30-60 minutes

   (GR: starting point is good.  as I said above, we may want some dynamic aspect of the chunk size depending on meetings - don't spread a meeting across 2 chunks unless it is longer than X minutes.  Also, there will be long quiet periods so maybe we can do something with that.  If there is no transcribe-able content then I don't want it uploaded... but that doesn't have to be mvp)

**OQ-2:** Should we implement pause/resume functionality, or is stop/start sufficient?
(GR: let's add pause.  good idea)

**OQ-3:** How should we handle recordings in progress when network becomes available - upload what we have so far, or wait for chunk to complete?
(GR: wait for chunks to complete naturally, upload any completed chunks)

**OQ-4:** Should there be a maximum storage limit for local recordings (e.g., stop recording if more than 5GB locally stored)?
(GR: make this configurable, ...so, yes :)

**OQ-5:** What level of compression quality provides acceptable balance between file size and transcription accuracy for the backend?
(GR: let's make this code-configurable and see how things work in practice)

**OQ-6:** Should we implement any local backup before deletion (e.g., keep for 24 hours even after upload)?
(GR: nah, after the MD5 comparison, I'm happy to get rid of the file... however, we should provide a bit of retention to give the user replay capabilities, user-configurable time for retention)

**OQ-7:** For smart recording detection (future): What algorithm/threshold should we use to detect "silence" vs "worth recording"?
(GR: let's answer in the future, but "worth recording" is the better choice.)

**OQ-8:** Should we add any user-facing metadata fields (tags, notes, location) or keep strictly automated?
(GR: a "quick-note" that gets added at the timestamp is a cool idea but not mvp - keep track of this though)

**OQ-9:** How should we handle DST (daylight saving time) transitions in file naming and metadata?
(GR: include "PDT" or "PST" in the timestamp to differentiate duplicate recording spans)

**OQ-10:** Should background recording continue when screen is off? What about battery optimization implications?
(GR: It's is very important that recording continues to operate while the screen is off or the phone is locked)

**OQ-11:** What is the optimal GPS sampling interval balancing context accuracy vs battery life and data volume?
   - 1 minute default may be too frequent for stationary users
   - Consider adaptive sampling based on movement detection
(GR: adaptive is a great idea.  I was thinking about making it a bit longer - say, 5 min - but for testing purposes it's nice to have finer granulaity.  in general use, we want to optimize for battery use over granularity of location data)

**OQ-12:** Should we implement geofencing to detect when user enters/exits meeting locations listed in calendar?
(GR: maybe later, not mvp, keep track of this but it's low priority)

**OQ-13:** How should we handle calendar events that span multiple recording chunks?
   - Include in metadata for all chunks?
   - Only in chunks where event starts?
(GR: all chunks.  )

**OQ-14:** Should we filter out certain calendar event types (e.g., personal, private, declined meetings)?
(GR: in the future, not mvp, keep track of this)

**OQ-15:** How precise should location data be? Current accuracy setting may reveal user location too precisely - privacy concern?
(GR: precise is fine.  I'm not too concerned about privacy, this app is for individual use - the data will not be avaialble to anyone else).

**OQ-16:** Should metadata be uploaded as a separate JSON file or embedded in the audio file (ID3 tags, etc.)?
(GR: I'm flexible here, I think i'd prefer it to be embedded?)

**OQ-17:** Should users be able to manually edit/redact location or calendar metadata before upload?
(GR: nah, maybe later)

**OQ-18:** For future backend: How will location/calendar metadata be used in AI processing? Understanding this may influence what we collect now.
(GR: to-do lists, promises made during meetings, action items, sentiment analysis of the attendees; for location, it's to help the user remember where particular conversations or personal notes occurred - personal notes may be a significant use case, BTW)

---

## Next Steps

1. Review and approve this PRD
2. Create task list using generate-tasks.md process
3. Set up Android project structure
4. Begin implementation starting with core recording functionality
5. Create PRD for backend processing system (Part 2)
6. Create PRD for web frontend (Part 3)
