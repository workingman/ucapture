# Session Notes for ubiq-capture Project

## Project Overview

**ubiq-capture** is a three-part audio capture and processing system:
1. **Part 1 (Current):** Android recording app - Captures audio with GPS/calendar metadata, uploads to cloud
2. **Part 2 (Future):** Backend processing service - Transcription, AI processing, metadata generation
3. **Part 3 (Future):** Web frontend - Access recordings and derived data

**Current Focus:** Part 1 - Android app (MVP)

## Key Documents

### Primary Documents
1. **`0001-prd-audio-recording-app.md`** - Complete Product Requirements Document
   - All functional requirements (FR-1 through FR-43)
   - User stories, goals, technical considerations
   - Resolved decisions (D-1 through D-13)
   - Future enhancements (FE-1 through FE-6)

2. **`tasks-0001-prd-audio-recording-app.md`** - Implementation task list
   - 8 parent tasks, 150+ sub-tasks
   - Complete file structure (~50 files)
   - Testing strategy

### Process Documents
3. **`create-prd.md`** - How to create PRDs (for future PRDs for Parts 2 & 3)
4. **`generate-tasks.md`** - How to generate task lists from PRDs
5. **`process-task-list.md`** - How to work through task lists
6. **`prd-prompt1.md`** - Initial prompt template used for this PRD

## Important Architectural Decisions

### Technology Stack
- **Language:** Kotlin (chosen for modern Android best practices, null safety, coroutines)
- **Architecture:** MVVM (Model-View-ViewModel)
- **UI:** Jetpack Compose (modern declarative UI)
- **Database:** Room (local metadata storage)
- **DI:** Hilt/Dagger
- **Background:** WorkManager (uploads) + Foreground Service (recording)
- **Min SDK:** API 26 (Android 8.0)
- **Target SDK:** Latest stable

### Key Features
- Continuous audio recording with screen off/phone locked
- Pause/resume capability
- Auto-chunking (30-60 min, configurable)
- GPS location tracking (1-min intervals, adaptive)
- Calendar event metadata collection
- Local retention for replay (user-configurable)
- Google Drive upload with MD5 verification
- Vertically scrolling timeline UI for replay

### Critical Requirements
- **Background Operation:** Must work with screen off and phone locked
- **Retention Policy:** Keep files locally for X minutes after upload (user-configurable)
- **Timeline UI:** Vertical scroll, timestamps only (MVP), transcription snippets later
- **Metadata:** Embedded in MP3 (ID3 tags preferred) or JSON sidecar
- **Timestamps:** Include timezone (PDT/PST) to handle DST transitions
- **Precision:** Unix timestamps with milliseconds for all events

## User Feedback Pattern

During PRD development, user provided feedback in format: `(GR: notes here)`

All GR notes have been incorporated and removed from final PRD. Key feedback included:
- Timeline UI should be vertical scrolling, not file list
- Add pause/resume functionality
- Require background operation with screen off
- Local audio retention for replay
- Precise timestamps with timezone
- All permissions including background/battery optimization

## Future Phases

### Phase 2 Enhancements (Post-MVP)
- Smart recording detection ("worth recording" algorithm)
- Quick voice notes (timestamp annotations)
- On-device transcription preview (Whisper)
- Transcription text in timeline view
- Dynamic chunking (meeting-aware, silence trimming)
- Adaptive GPS sampling based on movement

### Phase 3 (Separate PRD Needed)
- Backend processing service for transcription and AI
- Web frontend for accessing recordings

## Git Repository Status

**Current Branch:** main

**Commits:**
- `785462c` - Initial project setup with PRD
- `fa27ced` - Update PRD with user feedback and timeline UI
- `4233653` - Add comprehensive task list

**Clean working tree:** Yes (as of last session)

## Session 2 Summary (2025-11-03)

### Completed: Development Environment & Project Setup

**Development Environment:**
- Installed Java JDK 17 (Temurin) - for Android builds
- Installed Java JDK 25 (Temurin) - available for other uses
- Configured Gradle to use Java 17 via `gradle.properties`
- Installed Android Studio 2025.2.1.7
- Installed Android SDK: API 29, 35, 36 with Build Tools 36.1.0
- Created Pixel 9 emulator (API 35)
- Updated `~/.zshrc` with JAVA_HOME and ANDROID_HOME environment variables

**Project Naming Decision:**
- Changed from "ubiq-capture" to **"uCapture"** (cleaner, easier to say)
- Package name: `ca.dgbi.ucapture` (using dgbi.ca domain)
- File prefix: `ucap-YYYYMMDD-HHMMSS-PDT-001.mp3`

**Android SDK Versions (Updated from PRD):**
- **Min SDK:** API 29 (Android 10) - for security, modern APIs, 98% coverage
- **Target SDK:** API 35 (Android 15) - Google Play requirement
- **Compile SDK:** API 36 (Android 16) - latest available
- ~~Original: API 26~~ (rejected - too old, security concerns)

**Task 1.0 Completed (7/9 subtasks):**
- ✅ 1.1 Created Android project with Empty Compose Activity
- ✅ 1.2 Configured project-level `build.gradle.kts` with version catalogs
- ✅ 1.3 Configured `app/build.gradle.kts` with all dependencies:
  - Hilt 2.52 (DI), Room 2.6.1 (DB), WorkManager 2.10.0
  - Compose BOM 2024.11.00, Navigation 2.8.4
  - Google Drive API, Play Services Location 21.3.0
  - Coroutines 1.9.0, DataStore 1.1.1
- ✅ 1.4 Set SDK versions (min 29, target 35, compile 36)
- ✅ 1.5 Added all permissions to AndroidManifest.xml:
  - Microphone, Location (fine/coarse), Calendar
  - Internet, Network State, Foreground Service
  - Notifications (API 13+), Wake Lock, Battery Optimization
- ✅ 1.6 Created `UCaptureApplication.kt` with `@HiltAndroidApp`
- ✅ 1.7 Created complete package structure:
  - `data/` (model, local, remote, repository, preferences)
  - `ui/` (recording, timeline, settings, components, navigation)
  - `service/metadata/`
  - `util/`, `di/`
- ⏸️ 1.8 ProGuard/R8 rules - TODO
- ⏸️ 1.9 .gitignore patterns - TODO

**Build Status:** ✅ BUILD SUCCESSFUL

**Key Technical Decisions:**
- Using Kotlin 2.0.21 with Compose plugin
- Java 17 for Android builds (Java 25 caused Kotlin compatibility issues)
- Fixed packaging conflicts with Google libraries (excluded META-INF files)
- Version catalogs in `libs.versions.toml` for dependency management

### Project Structure
```
ubiq-capture/
├── tasks/                          # Documentation (PRDs, tasks, session notes)
│   ├── 0001-prd-audio-recording-app.md
│   ├── tasks-0001-prd-audio-recording-app.md
│   └── SESSION-NOTES.md
└── android/                        # uCapture Android app
    ├── app/src/main/java/ca/dgbi/ucapture/
    │   ├── UCaptureApplication.kt  # Hilt application
    │   ├── MainActivity.kt         # @AndroidEntryPoint
    │   ├── data/
    │   ├── ui/
    │   ├── service/
    │   ├── util/
    │   └── di/
    ├── build.gradle.kts
    ├── app/build.gradle.kts
    └── gradle/libs.versions.toml
```

## Next Steps

**Remaining from Task 1.0:**
- 1.8 Configure ProGuard/R8 rules for production builds
- 1.9 Set up .gitignore patterns

**Task 2.0:** Implement core audio recording service
**Task 3.0:** Implement metadata collection (location & calendar)
**Task 4.0:** Implement local storage (Room database)
**Task 5.0:** Implement Google Drive integration
**Task 6.0:** Implement UI (recording, timeline, settings)

## Development Workflow

When working through tasks:
1. Reference PRD for requirements context
2. Follow task list sub-tasks sequentially
3. Create git commits for logical milestones
4. Run tests as components are completed
5. Update task list checkboxes as tasks complete

## Important Notes

### Storage & Cloud
- **MVP:** Google Drive with OAuth 2.0
- **Future:** Migrate to GCS (design supports this with CloudStorageProvider interface)
- MD5 verification required before local deletion

### Permissions Required
- Microphone (audio recording)
- Location (GPS metadata)
- Calendar (meeting metadata)
- Notifications (persistent notification)
- Foreground service (background recording)
- Battery optimization exemption (prevent system kills)

### Testing Priorities
- Background operation with screen off (critical)
- 8-hour battery impact test
- Location tracking (indoor/outdoor)
- Calendar metadata with overlapping events
- Upload verification with MD5
- Timeline replay and scrubbing
- DST transition handling

### Privacy Considerations
- This is an **individual-use app** (not multi-user)
- Location precision is intentional (not a privacy concern per user)
- Calendar data is sensitive (no logging, secure transmission)
- Audio recordings contain personal data (handle with care)

## User Preferences (from .claude/CLAUDE.md)

- `rm` and `mv` are aliased to interactive form with `-i` flag (use escaped commands: `\rm`, `\mv`)
- Questions should be answered without initiating work (imperative tense indicates work request)

## Project Structure Convention

```
ubiq-capture/
├── tasks/               # All documentation
│   ├── 0001-prd-*.md   # PRDs (numbered, zero-padded)
│   ├── tasks-*.md      # Task lists (matching PRD names)
│   ├── *.md            # Process/workflow docs
│   └── SESSION-NOTES.md # This file
└── [Android project]    # To be created
```

## Contact for Questions

If unclear during implementation:
- Check PRD first (most authoritative)
- Reference task list for step-by-step guidance
- Check SESSION-NOTES.md for architectural context
- Ask user for clarification if still unclear

## Success Metrics (From PRD)

- Recording reliability: 99%+ success rate
- Upload success: 95%+ within 24 hours
- MD5 verification: 100% before deletion
- Battery impact: < 20% over 8 hours (with location tracking)
- Crash rate: < 1%
- First recording completion: < 5 minutes from first launch

---

**Last Updated:** 2025-11-03 (Session 2: Dev environment setup & project initialization)
**Status:** Task 1.0 mostly complete (7/9), project building successfully, ready for feature implementation
