# Product Requirements Document (PRD): Smart Audio Bridge v1.0

## 1. Executive Summary
The **Smart Audio Bridge** is a portable device that acts as a "man-in-the-middle" between a primary smartphone and a user's wired headset. It emulates a Bluetooth Hands-Free Profile (HFP) headset to record both sides of a phone conversation while allowing the user to communicate through a wired high-quality cardioid microphone and earpiece. Recorded data is stored locally and automatically uploaded to a primary computer for AI transcription via a local **OpenAI Whisper** model.

## 2. Product Objectives
*   **Privacy-First Recording:** Ensure all data remains local until moved to the user's primary workstation.
*   **Open Workflow Integration:** Provide a system that allows developers to access raw audio via standard protocols (SSH/SFTP), bypassing closed proprietary ecosystems.
*   **High-Fidelity Capture:** Use professional-grade wired microphones to ensure the highest possible transcription accuracy.
*   **Automated Offloading:** Create a "set and forget" experience where the device syncs files whenever the primary computer's network is reachable.

## 3. Scope & Phases
*   **v1.0 (Current):** USB-C audio interface for input/output. Focus on software routing and automated syncing.
*   **v2.0 (Future):** GPIO-based I2S audio input/output to achieve near-zero latency and a smaller physical footprint.

## 4. Hardware Specifications (v1.0)

| Component | Specification |
| :--- | :--- |
| **Microcontroller** | Raspberry Pi Zero 2 W |
| **Bluetooth** | Integrated 2.4 GHz (Broadcom BCM43438) |
| **Storage** | 256GB MicroSD (Class 10/U3 for reliability) |
| **Audio Interface** | USB 2.0 Audio Adapter (3.5mm Mic In, 3.5mm Headphone Out) |
| **Connectivity** | 802.11 b/g/n Wireless LAN |
| **Power** | 5V/2.5A Micro-USB (Portable Battery Bank) |

## 5. Functional Requirements

### 5.1 Bluetooth Role Emulation
*   The device must appear as a **Bluetooth HFP/HSP sink** (Headset) to the primary smartphone.
*   It must automatically reconnect to the paired phone upon power-up.

### 5.2 Audio Routing & Mixing
*   **Input Routing:** Microphone audio (USB) -> Phone (Bluetooth).
*   **Output Routing:** Phone audio (Bluetooth) -> Earpiece (USB).
*   **Monitoring:** The user must hear the phone audio in real-time with latency <= 30ms.
*   **Recording:** Both channels (Local Mic and Remote Phone) must be recorded into a dual-channel (stereo) WAV file.

### 5.3 Automated Syncing
*   The device must run a background service (Systemd) to detect when the primary workstation's network is available.
*   Upon detection, it should use `rsync` or `SCP` to move files from the "Storage Bucket" to the workstation.
*   Successfully transferred files should be deleted from the Pi to preserve storage space.

## 6. Software Stack
*   **Operating System:** Raspberry Pi OS Lite (64-bit).
*   **Audio Engine:** PipeWire & WirePlumber for low-latency routing.
*   **Bluetooth Management:** BlueZ with oFono for HFP support.
*   **Recording CLI:** FFmpeg or SoX for background audio capture.
*   **Transcription (Workstation):** Whisper.cpp for fast, local ARM/Mac-based AI transcription.

## 7. User Scenarios
1.  **Incoming Call:** The user answers a call on their phone. The phone transmits audio to the Pi via Bluetooth. The Pi routes the audio to the user's wired earpiece and starts a recording script.
2.  **Recording Session:** The user speaks into a high-quality wired lavalier mic. This audio is sent back to the phone so the caller can hear them, and it is simultaneously recorded to the SD card.
3.  **End of Call:** The script detects the Bluetooth disconnect and closes the WAV file.
4.  **Auto-Offload:** When the user returns to their home/office, the Pi detects the Wi-Fi. It pushes the WAV file to the desktop computer, which then runs Whisper to produce a text summary for the user's CRM/workflow.



# Technical Architecture & Setup Guide: Smart Audio Bridge v1.0

## 1. Project Overview
The Smart Audio Bridge turns a Raspberry Pi Zero 2W into a programmable Bluetooth headset. It intercepts bi-directional phone audio, routes it to a local wired headset for the user, and taps the digital stream to record high-fidelity WAV files for local AI transcription.

## 2. System Architecture

### 2.1 Hardware Signal Path
*   **Downlink:** Phone (BT) -> Pi (BlueZ/HFP) -> PipeWire Sink -> USB Audio Out -> Earpiece.
*   **Uplink:** Cardioid Mic -> USB Audio In -> PipeWire Source -> Pi (BlueZ/HFP) -> Phone (BT).
*   **Tapping:** PipeWire "Monitor" ports for both Uplink and Downlink -> FFmpeg Multiplexer -> SD Card (.wav).

### 2.2 Software Stack
- **OS:** Raspberry Pi OS Lite (64-bit) based on Debian Bookworm.
- **Audio:** PipeWire + WirePlumber (Replacement for PulseAudio).
- **BT Stack:** BlueZ 5.xx + oFono (required for HFP/Hands-Free profile).
- **Recorder:** FFmpeg (handling dual-stream capture).
- **Automation:** Systemd units for connection monitoring; Rsync for offloading.

---

## 3. Initial Environment Setup

### 3.1 OS Preparation
```bash
# Update and install core dependencies
sudo apt update && sudo apt upgrade -y
sudo apt install -y pipewire wireplumber pipewire-audio-client-libraries \
bluez oFono ffmpeg rsync





# 10.0 Other Technical Information
3.2 Enabling Bluetooth HFP (The "Headset" Role)
BlueZ needs to be configured to allow the Pi to act as an audio sink rather than a master.
1. Edit /etc/bluetooth/main.conf:
ini
[General]
Class = 0x200404 # Sets device class to Audio/Video, Headset
Enable = Source,Sink,Media,Socket


2. Enable oFono (to handle the telephony handshake):
bash
sudo systemctl enable --now ofono


3. Restart Bluetooth:
bash
sudo systemctl restart bluetooth


________________


4. Audio Routing Logic (PipeWire)
PipeWire handles the virtual "patch bay." You will use pw-link to connect the Bluetooth source (the phone) to the USB output (the earpiece).
4.1 Identifying Nodes


bash
# List all audio inputs and outputs
pw-link -io


4.2 Scripting the Routing (The "Bridge")
A simple bash script or Python wrapper should monitor for the phone's MAC address and trigger:
bash
# Example: Route Phone to Headphones
pw-link "bluez_input.XX_XX_XX_XX_XX_XX.mono" "alsa_output.usb-adapter.analog-stereo:playback_FL"
pw-link "bluez_input.XX_XX_XX_XX_XX_XX.mono" "alsa_output.usb-adapter.analog-stereo:playback_FR"


# Example: Route Cardioid Mic to Phone
pw-link "alsa_input.usb-adapter.analog-stereo:capture_FL" "bluez_output.XX_XX_XX_XX_XX_XX.mono"


________________


5. Recording & Offloading
5.1 The FFmpeg Capture Command
To record both sides into a stereo file (Left = Caller, Right = You):
bash
ffmpeg -f pulse -i "bluez_input.XX_XX_XX_XX_XX_XX.monitor" \
       -f pulse -i "alsa_input.usb-adapter.analog-stereo.monitor" \
       -filter_complex "[0:a][1:a]join=inputs=2:channel_layout=stereo[a]" \
       -map "[a]" -acodec pcm_s16le -ar 16000 /home/pi/recordings/call_$(date +%Y%m%d_%H%M%S).wav


Note: 16kHz is the optimal sample rate for Whisper.cpp.
5.2 The Offload Script (Rsync)
Run via a Systemd timer or Cron job:
bash
#!/bin/bash
# Check for Wi-Fi/Target availability
if ping -c 1 192.168.1.100 &> /dev/null; then
  rsync -avz --remove-source-files /home/pi/recordings/ user@192.168.1.100:/home/user/whisper_input/
fi


________________


6. Workstation Processing (Whisper.cpp)
Once the file arrives on the workstation, trigger the local model:
bash
./main -m models/ggml-base.en.bin -f ~/whisper_input/call_recorded.wav -otxt


________________


7. Known Latency Optimizations
* PipeWire Buffer: Adjust default.clock.quantum in pipewire.conf to 128 or 256 for lower latency.
* v2.0 Path: Transition from USB adapter to I2S (GPIO) using a ReSpeaker Hat to eliminate USB bus overhead.


Would you like the **Systemd unit file templates** next so that this software automatically starts every time the Pi powers on?
