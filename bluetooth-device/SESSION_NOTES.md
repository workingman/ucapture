# Smart Audio Bridge - PRD Creation Session
Created: 2026-01-30
Last modified: 2026-01-30

## Current Status

PRD v1.0 is drafted and saved to `tasks/0001-prd-smart-audio-bridge.md`. The user is reviewing it and will provide inline feedback in the next session.

No code has been written yet. This is a greenfield project.

## Recent Context

### What we did
Created a comprehensive PRD for the Smart Audio Bridge through an iterative Q&A process (questions A through U, plus follow-up on metadata/GPS). The PRD went through one major revision to add:
- Companion mobile app (GPS provider + configuration interface)
- On-device metadata framework (sidecar JSON per recording chunk)
- Workstation post-processing pipeline (transcription, diarization, calendar, contacts)

### Source documents reviewed
- `device-prd.md` - Original PRD and technical architecture (markdown)
- `background.rtfd/TXT.rtf` - Design conversation covering hardware choices, risks, software stack recommendations

### Key architectural decisions
- **Platform**: Pi Zero 2W (recorder/streamer only, no local transcription)
- **Audio**: Dual mic setup (cardioid lav for calls, omni for ambient) via two USB audio adapters + hub
- **Recording**: Continuous stereo WAV (L=local mic, R=BT call audio). Default 44.1kHz, configurable.
- **Chunking**: Speech/silence-aware (VAD preferred, energy-threshold fallback) + max file size
- **Output**: Wired earpiece only for v1.0. BT headset is future enhancement.
- **Config**: Companion app (primary), web UI (fallback). No auth for v1.0.
- **GPS**: Via companion app over BT SPP/BLE (preferred) or local Wi-Fi
- **Metadata**: Rich sidecar JSON per chunk (timestamps, call info, GPS, device state)
- **Sync**: rsync over SSH to multiple targets. Capacity-influenced retention policy.
- **Post-processing**: Workstation pipeline - Whisper, diarization, calendar matching, contact lookup
- **Power**: Graceful low-battery shutdown. Power efficiency throughout (Wi-Fi power mgmt, CPU governor, batch sync)

## Key Commands and Locations

### Project files
- PRD: `tasks/0001-prd-smart-audio-bridge.md`
- Original PRD/architecture: `device-prd.md`
- Background discussion: `background.rtfd/TXT.rtf`
- Memory log: `.claude/memory.jsonl`

### Project root
`/Users/gwr/Documents/dev/ubiq-capture/bluetooth-device/`

## Open Items

### PRD review (next session)
- User will provide inline feedback on the PRD
- Address feedback and update PRD accordingly

### Open questions requiring resolution (from PRD section 9)
- **OQ-1**: Battery monitoring solution (PiSugar? voltage divider?)
- **OQ-2**: PipeWire + 2 USB audio + BT on Pi Zero 2W - needs prototyping
- **OQ-3**: VAD CPU load on Pi Zero 2W (WebRTC vs Silero)
- **OQ-4**: oFono + BlueZ HFP reliability (HIGHEST RISK - validate early)
- **OQ-5**: Companion app BT protocol (SPP/BLE vs Wi-Fi)
- **OQ-6**: Web UI via USB gadget mode for first-boot setup
- **OQ-7**: Echo cancellation necessity
- **OQ-8**: Companion app platform priority (iOS/Android)
- **OQ-9**: Calendar/contacts API priority
- **OQ-10**: Post-processing trigger (daemon vs rsync hook)
- **OQ-11**: Diarization engine for Mac workstation
- **OQ-12**: GPS sampling interval during calls

### After PRD is finalized
- Generate implementation task breakdown from the PRD

## Session History

### 2026-01-30 - Initial PRD creation
- Reviewed source documents (device-prd.md, background.rtfd)
- Iterative Q&A to scope the PRD (22 questions across topics A-U)
- Generated PRD with 53+ functional requirements across 14 subsections
- Revised PRD to add companion app, metadata framework, and post-processing pipeline
- No skill candidates identified this session (no gotchas or workarounds needed)
