# SESSION_NOTES: ubiq-capture

**Updated:** 2026-02-03
**Purpose:** Ubiquitous capture system for recording and archiving the data ocean of daily life

---

## Project Overview

ubiq-capture is a multi-component system for comprehensive data capture across different modalities (audio, phone calls, financial records). Each subdirectory is an independent project targeting a specific capture domain, unified by the philosophy of automated, metadata-rich, cloud-synced archival.

---

## Components

### 1. android-recorder/ (Production-ready)

**What:** Android app (uCapture) for continuous background audio recording with contextual metadata.

**Stack:** Kotlin, Jetpack Compose, Hilt DI, Room DB, WorkManager, Google Drive API

**Status:** All 6 core tasks complete (project setup, recording service, metadata collection, local storage, Google Drive sync, UI). ~5,100 lines production code, ~2,050 lines test code across 12 test files.

**Working features:**
- Foreground recording service with wake locks and 30-min chunk rotation
- GPS location sampling (60s intervals) and calendar event association
- Google Sign-In with token persistence (EncryptedSharedPreferences)
- Auto-upload to Google Drive with hourly retry for failures
- JSON metadata sidecars alongside audio files
- Compose UI: recording control, timeline browser, settings

**Known issues:**
- Chunk duration still set to 1 minute (testing value, needs restoration to 30 min)
- Access token expiration handling incomplete (tokens expire after 1 hour)
- Verbose debug logging in GoogleDriveAuthManager needs cleanup
- Some stale tests in SettingsViewModelTest referencing removed methods

---

### 2. bluetooth-device/ (Planning phase)

**What:** Raspberry Pi Zero 2W-based Bluetooth HFP audio bridge for recording phone calls with dual-channel audio (caller on left, user on right).

**Stack (planned):** Raspberry Pi OS Lite, BlueZ + oFono, PipeWire + WirePlumber, FFmpeg, Bash/Python

**Status:** PRD v1.0 complete (`device-prd.md`). No implementation code yet.

**Planned features:**
- Bluetooth HFP/HSP headset emulation (phone pairs to Pi as headset)
- Audio passthrough to wired headset via USB audio adapter (target latency <= 30ms)
- Dual-channel stereo WAV recording at 16kHz (optimized for Whisper transcription)
- Rsync-based file offloading to workstation
- 256GB MicroSD local storage

**Roadmap:**
- v1.0: USB audio interface (current spec)
- v2.0: GPIO I2S audio for lower latency and smaller footprint

---

### 3. expensify-interface/ (Complete)

**What:** One-time data migration that backs up all Expensify financial data to Cloudflare D1 (structured data) and R2 (receipt images) before account decommission.

**Stack:** Bash scripts, Cloudflare Wrangler CLI, rclone, Expensify Integration API

**Status:** Complete and audited as of 2026-01-18.

**Results:**
- 33 reports, 1,068 expenses, 1,063 receipt images backed up
- All audit checks passed (report totals, receipt existence, spot checks)
- D1 database: ~1.2 MB; R2 receipts: ~112 MB

**Remaining (optional):**
- Clean up BACKUP_UNREPORTED report in Expensify
- Delete local export files
- Decommission Expensify account

---

## Recent Session (2026-02-03)

### Research: Google Recorder API

Investigated whether Google Recorder (Pixel app) has an API or triggers for when recordings complete.

**Findings:**
- No public API or SDK
- No broadcast intents for third-party apps to listen to
- Files stored in protected `/data/data/com.google.android.apps.recorder/` (requires root)
- No webhook support at recorder.google.com
- Recordings sync to Google Account but no programmatic access

**Workaround options considered:**
1. ContentObserver on MediaStore (limited - Recorder uses private storage)
2. Google Drive sync + Drive API polling (viable but indirect)
3. Build custom recorder (chosen - gives full lifecycle control)

**Decision:** Continue building custom recorder in `android-recorder/` since it provides direct control over recording completion events.

---

## Cross-cutting Themes

- **Local-first with sync:** All components store data locally, then sync to cloud/remote when connectivity allows
- **Metadata enrichment:** Audio gets GPS + calendar; calls get dual-channel separation; expenses get receipt images
- **AI transcription pipeline:** Both audio components target Whisper for downstream transcription
- **Cloud storage:** Google Drive (Android), Cloudflare R2 (Expensify), workstation rsync (Bluetooth device)

## Git Status

The repo root has deleted files from an earlier android/ directory (content moved to android-recorder/). The three active subdirectories are android-recorder/, bluetooth-device/, and expensify-interface/. The root also has a stale CLAUDE.md that was deleted from the index.

## Next Steps

1. **android-recorder:** Fix token expiration handling, restore 30-min chunk duration, clean up debug logging
2. **bluetooth-device:** Begin implementation (systemd units, PipeWire config, BlueZ pairing scripts)
3. **expensify-interface:** Optional cleanup (decommission Expensify account)
4. **Root project:** Consider adding a top-level CLAUDE.md and cleaning up deleted files from git index
