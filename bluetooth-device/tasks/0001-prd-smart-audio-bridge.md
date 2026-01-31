# PRD: Smart Audio Bridge v1.0

## 1. Introduction / Overview

The Smart Audio Bridge is a portable, battery-powered device built on a Raspberry Pi Zero 2W. It sits between a smartphone and the user's wired audio equipment, acting as a Bluetooth Hands-Free Profile (HFP) headset. The device continuously records local audio from an omnidirectional microphone and, when a phone call is active, simultaneously captures the remote caller's audio via Bluetooth. Recordings are stored locally and automatically synced to a configurable workstation for AI transcription.

A companion mobile app on the paired smartphone provides GPS location data and serves as an alternative configuration interface for the device.

Recordings are synced with rich metadata (timestamps, call info, GPS location). On the workstation, a post-processing pipeline runs AI transcription and enriches recordings with calendar data, contact lookups, and speaker diarization.

The core value proposition: a privacy-first, open-workflow recording system that captures both sides of phone conversations (plus ambient audio) with no cloud dependency and no manual file management.

## 2. Goals

- **Continuous local capture**: Record ambient audio from an omnidirectional mic whenever the device is powered on.
- **Transparent call recording**: Automatically capture both sides of phone calls via Bluetooth HFP, with the user communicating through a dedicated cardioid mic and wired earpiece.
- **Automated sync**: Push recordings to one or more configurable workstations over SSH/rsync without user intervention.
- **Smart file management**: Chunk recordings based on speech/silence detection, manage storage with a configurable retention policy influenced by available capacity.
- **Rich metadata**: Capture GPS location (via companion app), call metadata (via HFP), and device state alongside every recording chunk.
- **Post-processing enrichment**: On the workstation, augment recordings with calendar data, contact lookups, transcription, and speaker diarization.
- **Power efficiency**: Minimize battery drain during idle periods and low-activity recording.
- **Simple initial setup**: Provide a companion app and web UI for device configuration.

## 3. User Stories

- **US-1**: As a user, I want the device to start recording ambient audio automatically when I power it on, so I never miss capturing something because I forgot to press a button.
- **US-2**: As a user, I want to answer a phone call and have both sides of the conversation recorded into the same file (as separate channels), so I can get accurate transcriptions later.
- **US-3**: As a user, I want to hear the caller through my wired earpiece with minimal latency, so the conversation feels natural.
- **US-4**: As a user, I want the caller to hear me through a high-quality cardioid mic, so my voice is clear on their end.
- **US-5**: As a user, I want recordings to sync to my workstation automatically when the Pi can reach it over the network, so I don't have to manually transfer files.
- **US-6**: As a user, I want old recordings to be cleaned up automatically based on storage capacity and age, so the device doesn't fill up.
- **US-7**: As a user, I want to configure Wi-Fi, sync targets, recording settings, and retention policy through a web browser, so I don't have to edit config files over SSH.
- **US-8**: As a user, I want LED and log-based feedback on device state (recording, syncing, error, low storage), so I know what's happening at a glance.
- **US-9**: As a user, I want the device to shut down gracefully when battery power is low, so I don't lose recordings to a sudden power cut.
- **US-10**: As a user, I want to check device status from a simple web endpoint, so I can verify it's working without physically inspecting it.
- **US-11**: As a user, I want GPS coordinates attached to my recordings, so I can later see where a conversation took place.
- **US-12**: As a user, I want to configure the device from my phone (via a companion app), so I don't have to open a browser and navigate to the Pi's IP.
- **US-13**: As a user, I want the workstation to automatically match recordings against my calendar events, so transcriptions are tagged with meeting context.
- **US-14**: As a user, I want phone numbers from calls to be matched to contact names during post-processing, so I know who was on each call without listening.

## 4. Functional Requirements

### 4.1 Bluetooth HFP Emulation

- **FR-1**: The device must advertise itself as a Bluetooth HFP/HSP sink (headset) using BlueZ and oFono.
- **FR-2**: The device must automatically reconnect to the last paired phone on power-up.
- **FR-3**: The device must accept incoming and outgoing call audio from the paired phone.

### 4.2 Audio Routing

- **FR-4**: The device must route incoming phone audio (Bluetooth) to the wired earpiece via the USB audio adapter.
- **FR-5**: The device must route the cardioid microphone input (USB audio adapter) to the phone via Bluetooth, so the remote caller hears the user.
- **FR-6**: Audio monitoring latency (phone audio to earpiece) must be at or below 30ms.
- **FR-7**: Audio routing must be managed by PipeWire and WirePlumber.

### 4.3 Dual Microphone Support

- **FR-8**: The device must support two USB audio inputs: one cardioid mic (for call uplink and speech capture) and one omnidirectional mic (for ambient capture).
- **FR-9**: Each mic connects via a separate USB audio adapter. A USB hub is acceptable if needed for the Pi Zero 2W's single data port.
- **FR-10**: When no call is active, only the omnidirectional mic is used for the local channel. When a call is active, the cardioid mic feeds the call uplink and the local recording channel.

### 4.4 Recording

- **FR-11**: The device must record continuously whenever powered on.
- **FR-12**: Recordings must be stereo WAV files. Left channel = local mic (omni when idle, cardioid during calls). Right channel = Bluetooth call audio (silence when no call is active).
- **FR-13**: Default sample rate must be 44.1 kHz. Sample rate must be configurable (at minimum: 16 kHz, 44.1 kHz, 48 kHz).
- **FR-14**: Recording must be managed by FFmpeg (or SoX), capturing from PipeWire monitor ports.

### 4.5 Smart Chunking

- **FR-15**: The recording process must split output into chunks based on two criteria, whichever comes first:
  - (a) A configurable maximum file duration/size is reached.
  - (b) A period of silence (no detected speech) exceeds a configurable threshold.
- **FR-16**: Speech vs. silence detection should use a lightweight Voice Activity Detection (VAD) library (e.g., WebRTC VAD or Silero VAD). If VAD imposes too much CPU load on the Pi Zero 2W, fall back to energy-threshold-based silence detection (configurable dBFS threshold).
- **FR-17**: Chunk boundaries must not lose audio. The system must ensure seamless transitions between chunks (no gaps, no dropped samples).
- **FR-18**: Each chunk file must be named with a timestamp: `rec_YYYYMMDD_HHMMSS.wav`.

### 4.6 Companion App (Mobile)

- **FR-40**: A companion app on the paired smartphone must send GPS location data to the Pi at regular intervals (configurable, default: every 60 seconds).
- **FR-41**: Communication between the app and Pi should use Bluetooth Serial Port Profile (SPP) or BLE, piggy-backing on the existing Bluetooth connection. If that proves unreliable, fall back to local Wi-Fi (when both devices are on the same network).
- **FR-42**: The companion app must provide a configuration interface for the device, equivalent to the web UI (FR-26). This serves as the primary setup method for most users.
- **FR-43**: The companion app must display real-time device status (same data as the `/status` endpoint, FR-31).
- **FR-44**: The companion app should be cross-platform (iOS and Android). A React Native or Flutter approach is acceptable.
- **FR-45**: The app must handle GPS permissions gracefully, including background location access. It must clearly explain to the user why location is needed.

### 4.7 On-Device Metadata

- **FR-46**: For each recording chunk, the device must generate a sidecar JSON metadata file with the same base name (e.g., `rec_20250130_143022.json` alongside `rec_20250130_143022.wav`).
- **FR-47**: The sidecar JSON must include:
  - `chunk_id`: Unique identifier (UUID).
  - `filename`: The WAV filename.
  - `timestamp_start`: ISO 8601 timestamp when the chunk started.
  - `timestamp_end`: ISO 8601 timestamp when the chunk ended.
  - `duration_seconds`: Chunk duration.
  - `sample_rate`: Recording sample rate.
  - `channels`: Channel layout description (e.g., `{"left": "omni_mic", "right": "bt_call"}`).
  - `call_segments`: Array of call events within this chunk, each with: `start_offset_seconds`, `end_offset_seconds`, `phone_number` (if available via HFP), `direction` (incoming/outgoing/unknown).
  - `gps_samples`: Array of location fixes received during this chunk, each with: `timestamp`, `latitude`, `longitude`, `accuracy_meters`, `source` (companion_app).
  - `device_state`: Snapshot of battery level, storage usage, and active mic configuration.
  - `recording_settings`: Sample rate, VAD mode, chunk settings active at time of recording.
- **FR-48**: Metadata files must be synced alongside their corresponding WAV files. They must be treated as a pair (both synced, both retained, both deleted together).

### 4.8 Workstation Post-Processing Pipeline

- **FR-49**: The workstation must run a post-processing pipeline that watches for newly synced WAV+JSON pairs and processes them automatically.
- **FR-50**: The pipeline must perform the following enrichment steps:
  1. **Transcription**: Run Whisper (whisper.cpp or equivalent) on the WAV file. Output per-channel transcriptions.
  2. **Speaker diarization**: Identify and label distinct speakers within each channel (especially useful for the ambient omni mic capturing multi-person conversations).
  3. **Calendar matching**: Query the user's calendar API (Google Calendar, Outlook, CalDAV, etc.) for events overlapping the chunk's time range. Attach matching event titles, attendees, and descriptions.
  4. **Contact lookup**: Match phone numbers from `call_segments` against a contacts source (CardDAV, Google Contacts, local vCard, CSV, etc.) to resolve names.
  5. **Output**: Produce an enriched JSON file (e.g., `rec_20250130_143022.enriched.json`) containing the original metadata plus all enrichment results.
- **FR-51**: The post-processing pipeline must be modular. Each enrichment step (transcription, diarization, calendar, contacts) should be independently configurable and skippable.
- **FR-52**: The pipeline must be idempotent. Re-running on an already-processed file should not duplicate data.
- **FR-53**: Calendar and contacts integration must support configurable data sources. At minimum: Google Calendar/Contacts (OAuth) and local file-based sources (iCal, vCard/CSV).

### 4.9 Automated Syncing

- **FR-19**: A background service (systemd) must periodically check whether any configured sync target is reachable.
- **FR-20**: Sync targets are defined in a configuration file (or via the web UI). Each target specifies: hostname/IP, SSH user, destination path, and SSH key path. Multiple targets are supported.
- **FR-21**: File transfer must use `rsync` over SSH.
- **FR-22**: Only completed (closed) chunk files should be synced. The file currently being recorded must not be transferred.
- **FR-54**: Sidecar JSON metadata files must be synced alongside their WAV files. Both files must transfer successfully for the sync to be considered complete.

### 4.10 Retention & Storage Management

- **FR-23**: The device must implement a configurable retention policy with the following parameters:
  - Maximum age of synced files (default: 7 days). Synced files older than this are deleted.
  - Maximum age of unsynced files (default: 30 days). Unsynced files older than this are deleted (data loss accepted).
  - Storage capacity threshold (default: 80%). When SD card usage exceeds this percentage, the oldest synced files are deleted first, then oldest unsynced files.
- **FR-24**: Retention checks must run periodically (configurable interval, default: every hour).

### 4.11 Web UI (Configuration)

- **FR-25**: The device must serve a web UI on a configurable port (default: 80).
- **FR-26**: The web UI must allow configuration of:
  - Wi-Fi networks (SSID, password)
  - Sync targets (add, edit, remove)
  - Recording settings (sample rate, chunk max size/duration)
  - Silence/VAD detection settings (threshold, silence duration for chunking)
  - Retention policy settings
- **FR-27**: Configuration changes must be applied without requiring a full device reboot where possible. (Service restarts are acceptable.)
- **FR-28**: No authentication is required for v1.0. The web UI assumes a trusted local network.

### 4.12 Status & Monitoring

- **FR-29**: The device must provide visual status via an LED connected to a GPIO pin. States to indicate:
  - Idle / powered on (slow blink)
  - Recording, no call (solid on)
  - Recording, call active (fast blink)
  - Syncing (double blink pattern)
  - Error (rapid flash)
  - Low battery (distinct pattern, e.g., fade or triple flash)
- **FR-30**: The device must log operational events (recording start/stop, chunk creation, sync attempts/results, errors, battery warnings) to log files with rotation.
- **FR-31**: The device must expose a status endpoint (`GET /status`) returning JSON with: current state (idle/recording/call/syncing), storage usage, last sync time, battery status (if detectable), uptime, and active configuration summary.

### 4.13 Power Management

- **FR-32**: The device must monitor power input status via USB power detection or GPIO (depending on battery bank capabilities).
- **FR-33**: When low battery is detected, the device must:
  1. Close the current recording file cleanly.
  2. Attempt a final sync if a target is reachable.
  3. Initiate a clean shutdown.
- **FR-34**: The system must be designed for power efficiency:
  - PipeWire and recording processes should use efficient buffer sizes.
  - Network sync should batch transfers rather than syncing file-by-file.
  - Wi-Fi power management should be enabled when not actively syncing.
  - CPU governor should favor power-saving modes when not under recording/processing load.

### 4.14 System Services

- **FR-35**: All core functions (Bluetooth management, audio routing, recording, syncing, retention, web UI, status endpoint) must run as systemd services that start automatically on boot.
- **FR-36**: Services must implement watchdog patterns: if the recording process crashes, systemd should restart it automatically.

## 5. Non-Goals (Out of Scope for v1.0)

- **On-device transcription**: The Pi Zero 2W does not have sufficient resources. Transcription is the workstation's responsibility.
- **Bluetooth headset output**: v1.0 uses wired earpiece only. Bluetooth headset output (via a second USB dongle) is a documented future enhancement.
- **Multi-mic configuration via UI**: v1.0 assumes a fixed two-mic hardware setup. Future versions may allow configurable mic count.
- **Full management web UI**: v1.0 web UI covers configuration only. File browsing, BT pairing management, and service control are future enhancements.
- **Web UI authentication**: v1.0 assumes trusted local network. Auth will be added in a future version.
- **Cloud sync**: All sync is to user-controlled machines over SSH. No cloud storage integration.
- **Real-time streaming**: The device records and syncs. It does not stream audio in real-time to other systems.
- **On-device calendar/contacts**: Calendar and contact enrichment happens during workstation post-processing, not on the Pi.
- **Echo cancellation**: If earpiece audio bleeds into the cardioid mic, echo cancellation (e.g., PipeWire's WebRTC module) may be needed. This is noted as a known risk but not a v1.0 deliverable unless testing reveals it's required.
- **Custom PCB / I2S audio**: v1.0 uses USB audio adapters. GPIO/I2S (ReSpeaker, HiFiBerry) is v2.0.

## 6. Design Considerations

### 6.1 Web UI & Companion App

- The web UI and companion app share the same configuration API on the Pi. The web UI is a thin HTML frontend; the companion app calls the same REST endpoints (or a BT-based equivalent).
- Lightweight: the Pi Zero 2W has limited resources. Use a minimal web framework (e.g., Flask, or a static page with a small API backend).
- Mobile-friendly: the user may configure the device from their phone's browser.
- No JavaScript frameworks. Plain HTML/CSS with minimal vanilla JS for form interactions.
- The companion app is the expected primary configuration method for most users. The web UI exists as a fallback and for advanced/debugging use.

### 6.2 LED Patterns

- A single LED on a GPIO pin is sufficient. Use PWM for fade/brightness effects if desired.
- LED patterns must be distinct enough to identify state at a glance.

### 6.3 Physical Form Factor

- The device will be carried in a pocket or clipped to a belt. All connections (USB audio adapters, power) should be considered for strain relief.
- A USB hub will likely be needed: one port for mic adapter 1, one for mic adapter 2, power input. Consider a compact powered hub.

## 7. Technical Considerations

### 7.1 Software Stack

| Component              | Technology                                           |
| :--------------------- | :--------------------------------------------------- |
| Operating System       | Raspberry Pi OS Lite (64-bit, Debian Bookworm)       |
| Audio Engine           | PipeWire + WirePlumber                               |
| Bluetooth              | BlueZ 5.x + oFono (HFP)                             |
| Recording              | FFmpeg (or SoX)                                      |
| VAD                    | WebRTC VAD or Silero VAD (with energy-threshold fallback) |
| Sync                   | rsync over SSH                                       |
| Web UI                 | Lightweight Python (Flask) or Go                     |
| Service Management     | systemd                                              |
| Status Endpoint        | Bundled with web UI server                           |
| Companion App          | React Native or Flutter (iOS + Android)              |
| Post-Processing        | Python pipeline on workstation                       |
| Transcription          | Whisper.cpp (workstation)                            |
| Diarization            | pyannote-audio or equivalent (workstation)           |
| Calendar Integration   | Google Calendar API, CalDAV                          |
| Contacts Integration   | Google Contacts API, CardDAV, local vCard/CSV        |

### 7.2 Hardware

| Component              | Specification                                        |
| :--------------------- | :--------------------------------------------------- |
| Board                  | Raspberry Pi Zero 2W                                 |
| Bluetooth              | Integrated BCM43438 (2.4 GHz)                        |
| Storage                | 256 GB MicroSD (Class 10 / U3)                       |
| Audio Interface (call) | USB audio adapter #1 (3.5mm mic in + headphone out)  |
| Audio Interface (ambient) | USB audio adapter #2 (3.5mm mic in)               |
| Cardioid Mic           | Wired lavalier (3.5mm, via adapter #1)               |
| Omnidirectional Mic    | Wired omni (3.5mm, via adapter #2)                   |
| Earpiece               | Wired (3.5mm, via adapter #1 headphone out)          |
| USB Hub                | Compact USB 2.0 hub (for Pi Zero 2W single port)     |
| Power                  | 5V portable battery bank (Micro-USB)                 |
| LED                    | Single LED on GPIO pin (with resistor)               |

### 7.3 Dependencies & Constraints

- The Pi Zero 2W has a single Micro-USB data port. A USB OTG adapter + hub is required for two audio adapters.
- The Pi Zero 2W has 512 MB RAM. All software must be memory-conscious. No heavy frameworks.
- HFP via BlueZ requires oFono. Getting this working reliably is the highest-risk technical item.
- PipeWire on Pi Zero 2W with Bluetooth + two USB audio devices simultaneously is non-trivial. Buffer tuning will be needed.
- Battery monitoring on Pi Zero 2W is not natively supported. This may require a UPS HAT (e.g., PiSugar) or GPIO-based voltage divider to detect low battery.

### 7.4 Signal Path Diagram

```
+---------------------+         Bluetooth HFP          +------------------+
|                     | <==============================> |                  |
|     Smartphone      |   (caller audio / mic uplink)    |   Pi Zero 2W    |
|                     |                                  |                  |
|  +---------------+  |     BT SPP / BLE / Wi-Fi         |                  |
|  | Companion App | -----(GPS coords, config)---------> |                  |
|  +---------------+  |                                  |                  |
+---------------------+                                  +--------+---------+
                                                                  |
                                         PipeWire Audio Graph     |
                                   +------------------------------+------+
                                   |                                     |
                           +-------+--------+                   +--------+-------+
                           | USB Adapter #1 |                   | USB Adapter #2 |
                           | (Call Audio)   |                   | (Ambient Audio)|
                           +---+-------+----+                   +-------+--------+
                               |       |                                |
                          Mic In   Headphone Out                   Mic In
                               |       |                                |
                        Cardioid    Earpiece                     Omnidirectional
                        Lavalier   (wired)                         Microphone
                          Mic

Recording output per chunk:
  rec_YYYYMMDD_HHMMSS.wav   (L=local mic, R=BT call audio)
  rec_YYYYMMDD_HHMMSS.json  (metadata: timestamps, call info, GPS, device state)
          |
          | rsync over SSH (when target reachable)
          v
  +------------------------------------------------------+
  |                    Workstation                        |
  |                                                      |
  |  +------------------+    +------------------------+  |
  |  |  Whisper.cpp     | -> | Post-Processing        |  |
  |  |  (transcription) |    | Pipeline               |  |
  |  +------------------+    |                        |  |
  |                          |  - Speaker diarization |  |
  |  +------------------+    |  - Calendar matching   |  |
  |  | Calendar API     | -> |  - Contact lookup      |  |
  |  +------------------+    |  - Enriched JSON out   |  |
  |                          |                        |  |
  |  +------------------+    +------------------------+  |
  |  | Contacts Source  | ->          |                   |
  |  +------------------+             v                   |
  |                     rec_YYYYMMDD_HHMMSS.enriched.json |
  +------------------------------------------------------+
```

## 8. Success Metrics

- **Latency**: Phone-to-earpiece audio delay is imperceptible (at or below 30ms).
- **Recording reliability**: Zero dropped recordings due to software crashes (systemd watchdog recovers within 5 seconds).
- **Sync automation**: Files sync to workstation within 2 minutes of network availability, with zero user intervention.
- **Chunk quality**: No audio gaps at chunk boundaries. VAD-based chunking produces files that start and end near speech boundaries.
- **Battery life**: The device runs for at least 4 hours of continuous recording on a standard 10,000 mAh battery bank.
- **Storage management**: The device never fills the SD card to 100% (retention policy prevents this).
- **Uptime**: The device operates unattended for days at a time, recovering automatically from transient errors.

## 9. Open Questions

- **OQ-1**: Which specific UPS HAT or battery monitoring solution works best with the Pi Zero 2W form factor? (PiSugar S2? Custom GPIO voltage divider?)
- **OQ-2**: Can PipeWire on the Pi Zero 2W handle two USB audio adapters + Bluetooth simultaneously without excessive CPU usage? Needs prototyping.
- **OQ-3**: What is the real-world CPU load of WebRTC VAD vs. Silero VAD on the Pi Zero 2W? This determines whether we can use VAD or must fall back to energy-threshold chunking.
- **OQ-4**: oFono + BlueZ HFP reliability on Pi Zero 2W: community reports are mixed. This is the highest technical risk and should be validated early.
- **OQ-5**: Companion app communication protocol: BT SPP, BLE GATT, or local Wi-Fi for GPS data and configuration? BT SPP/BLE is preferred (no Wi-Fi dependency), but adds complexity to the Pi's Bluetooth stack which is already handling HFP. Needs prototyping.
- **OQ-6**: Should the web UI be accessible over Wi-Fi only, or also via USB gadget mode (RNDIS) for initial setup when Wi-Fi isn't configured yet? (The companion app may make this less critical if it can configure Wi-Fi over Bluetooth.)
- **OQ-7**: Echo cancellation: if earpiece bleed into the cardioid mic is a problem in practice, should we add WebRTC AEC as a v1.0 requirement or handle it post-launch?
- **OQ-8**: Companion app platform priority: iOS first, Android first, or both simultaneously? This affects development timeline.
- **OQ-9**: Which calendar/contacts APIs to prioritize for the post-processing pipeline? Google Workspace is most common, but some users may need Outlook/Exchange or self-hosted CalDAV/CardDAV.
- **OQ-10**: Should the post-processing pipeline run as a daemon (watching for new files) or be triggered by the sync process (e.g., rsync post-transfer hook)?
- **OQ-11**: Speaker diarization quality: pyannote-audio is accurate but GPU-heavy. On a Mac workstation with Apple Silicon, is there a lighter alternative that still produces usable results?
- **OQ-12**: GPS sampling interval: 60 seconds is the default, but should the companion app increase frequency during calls (e.g., every 15 seconds) for better location tracking during mobile conversations?
