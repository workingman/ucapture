# Cost Decisions: Audio Pipeline Components (2026-02-23)

Decision record for VAD, noise suppression, and ASR technology choices.

---

## 1. Picovoice (Cobra VAD + Koala Denoise) — DROPPED

**Reason:** Server license ~$899/month. Unacceptable for a ~10 user system.

Picovoice bundles Cobra (VAD) and Koala (noise suppression) under a single
server license. The free tier is device-only; server/Linux deployment requires
a paid license starting at ~$899/month regardless of usage volume.

---

## 2. VAD Replacement: Silero VAD v6 — SELECTED

### Why Silero

| Criterion        | Silero VAD v6               | Runner-up: WebRTC VAD       |
| :--------------- | :-------------------------- | :-------------------------- |
| Accuracy         | ROC-AUC 0.94-0.98           | ROC-AUC 0.62-0.86           |
| License          | MIT                         | MIT                         |
| Cost             | $0                          | $0                          |
| 30 min on CPU    | ~8 seconds                  | <1 second                   |
| Dependencies     | onnxruntime (~80 MB) + 2 MB model | C extension (~100 KB)  |
| Maintenance      | Active (v6.2, Dec 2025), 8.2k stars | Inactive, 2.4k stars  |
| Python install   | `pip install silero-vad`    | `pip install webrtcvad`     |

### Candidates eliminated

| Candidate       | Reason                                                       |
| :-------------- | :----------------------------------------------------------- |
| pyannote-audio  | 15-30 min to process 30 min audio on CPU. Needs GPU.         |
| NVIDIA NeMo     | 3+ GB Docker image. Custom NVIDIA license. Overkill for VAD. |
| SpeechBrain     | 60-120 min for 30 min audio on CPU. Needs GPU.               |

### Cloudflare Workers option investigated

Silero VAD in Workers (via ONNX Runtime WASM) is technically possible but
requires a custom minimal ONNX Runtime build to fit the 10 MiB Worker bundle
limit. Not worth the engineering effort because GCP is still needed for ffmpeg
transcoding (AAC → PCM). WebRTC VAD fits trivially in Workers (~20 KB WASM)
but its accuracy is insufficient for production use.

---

## 3. Noise Suppression — REMOVED FROM PIPELINE

### Why no denoising

A December 2024 paper ["When De-noising Hurts"](https://arxiv.org/pdf/2512.17562)
found that speech enhancement preprocessing **degraded ASR performance** across
all noise conditions and models tested:

- WER degradation ranged from 1.1% to 46.6% absolute increase
- DeepFilterNet specifically degraded Whisper transcription by ~20% WER
- Modern ASR engines (Whisper, Speechmatics) are trained on hundreds of
  thousands of hours of noisy audio and have learned internal noise robustness
- Enhancement artifacts (spectral smearing, temporal discontinuities) are
  more harmful to ASR than the original noise

Speechmatics also provides its own built-in
[audio filtering](https://docs.speechmatics.com/speech-to-text/features/audio-filtering)
tuned to work with their models.

### If denoising is ever needed

Run an A/B test first: send raw post-VAD audio vs. denoised audio to
Speechmatics and compare WER on 20-30 representative samples. Only add
denoising if it measurably improves transcription for your noise profile.

| Candidate                  | PESQ | License    | CPU speed         | 16kHz native | Dependencies          |
| :------------------------- | :--- | :--------- | :---------------- | :----------- | :-------------------- |
| **DTLN** (operational fav) | 3.04 | MIT        | Seconds for 30min | Yes          | ONNX Runtime (~500MB) |
| **ClearerVoice**           | 3.57 | Apache 2.0 | Uncharacterized   | Yes          | PyTorch (~2-3 GB)     |
| DeepFilterNet3             | 3.17 | MIT        | ~15 min for 30min | No (48kHz)   | PyTorch (~2-3 GB)     |

Eliminated: RNNoise (dated quality, 48kHz only), Demucs (CC-BY-NC, no
commercial use), CleanUNet (abandoned), PercepNet (no official implementation).

---

## 4. ASR: Speechmatics — KEPT

### Per-user cost model (speculative upper bound)

Assumes 6 hours of speech per user per day (post-VAD). This is entirely
speculative but represents a reasonable upper bound.

| Metric                            | Value     |
| :-------------------------------- | :-------- |
| Speech per user per day           | 6 hours   |
| Speech per user per month         | 180 hours |
| Speechmatics Pro ($0.24/hr)       | $43.20    |
| With volume discount (20% >500h)  | ~$34.56   |

At 10 users (1,800 hrs/month):

| Service                | 10 users/month | Per user |
| :--------------------- | :------------- | :------- |
| AssemblyAI ($0.17/hr)  | $306           | $30.60   |
| Speechmatics (volume)  | ~$370          | ~$37.00  |
| Google Chirp 3 (batch) | ~$432          | ~$43.20  |
| Deepgram Nova-3 Growth | $702           | $70.20   |
| AWS Transcribe         | $2,592         | $259.20  |

### Why Speechmatics over cheaper alternatives

1. **Already implemented** — `SpeechmaticsEngine` class exists behind
   `ASREngine` ABC. Switching costs are non-zero even with the pluggable
   interface.
2. **Cost difference is small** — $7/month per user vs. AssemblyAI at
   current scale. Not worth switching for.
3. **Diarization included** — no add-on fee (AssemblyAI charges +$0.02/hr
   for diarization).
4. **Quality** — high accuracy, word timestamps, speaker labels in one
   API call.

### When to reconsider

- If user count grows significantly and cost pressure increases
- If AssemblyAI or another provider demonstrates clearly better diarization
  quality for our audio profile
- If Speechmatics changes pricing

The `ASREngine` ABC makes switching straightforward — implement a new
engine class and update the registry.

### Self-hosting not viable at current scale

Self-hosted WhisperX on GCP Cloud Run (L4 GPU) costs ~$15-30/month for
100 hrs but adds ~$50/month in operational overhead (monitoring, model
updates, debugging). Breaks even vs. Speechmatics at ~500 hrs/month
(~50 users). At 10 users, hosted APIs win on total cost of ownership.

---

## Summary

| Component         | Before                | After             | Monthly cost change |
| :---------------- | :-------------------- | :---------------- | :------------------ |
| VAD               | Picovoice Cobra       | Silero VAD v6     | ~$899 → $0          |
| Noise suppression | Picovoice Koala       | Removed           | (bundled above)     |
| ASR               | Speechmatics          | Speechmatics      | No change           |
| **Net savings**   |                       |                   | **~$899/month**     |
