# Problem Statement: Audio Capture & Transcription Pipeline

## Metadata

- **Author:** Geoff
- **Date:** 2026-02-22
- **Type:** CREATE (Greenfield)
- **Status:** Draft

---

## The Opportunity

Most of what matters in knowledge work happens in conversation — in meetings,
hallway exchanges, design reviews, customer calls, and the thinking-out-loud
that happens between people solving hard problems together. Almost none of it is
captured. People rely on fragmented notes taken under pressure, selective memory,
and the occasional recording that nobody ever goes back to listen to. The result
is that decisions get re-litigated, context gets lost between conversations, and
the same insights get rediscovered over and over. The cost is real, it's daily,
and it compounds.

Sense and Motion is building a platform to fix this. The vision is ubiquitous
capture — a background layer that is always listening, always recording, and
intelligent enough to turn the raw stream of conversation into structured,
searchable, actionable knowledge. Not a meeting tool. Not a note-taking app. A
persistent ambient intelligence that works the way human memory should but
doesn't.

## Where We Are

The first piece of that platform is in your pocket. uCapture is an Android
app that records continuously in the background, chunks audio into manageable
segments, attaches rich metadata — GPS location, calendar context, timestamps —
and uploads everything automatically. It's stable, tested, and running on real
hardware today. The recording problem is solved.

What we don't have yet is anywhere useful for those recordings to go. Right now,
chunks land in Google Drive as disconnected files. They sit there. Raw audio at
128 kbps, most of it ambient noise and silence, with no transcript, no
structure, and no way to query or act on any of it. The client-side investment
is real; the backend that makes it valuable does not exist.

## What This Project Builds

The audio processing pipeline is the layer that transforms inert recordings into
structured data. When uCapture uploads a chunk, the pipeline receives it,
validates and stores every artifact, strips the silence and background noise
using Picovoice's Cobra and Koala, submits the cleaned speech to Speechmatics
for transcription with speaker diarization, and writes the result back with a
completion event that the app can act on. The whole thing is asynchronous and
queue-driven — the phone gets a response immediately, and processing happens in
the background.

The architecture is deliberate. Cloudflare handles ingest, storage (R2), and
indexing (D1) — cheap, globally distributed, zero egress fees. GCP Cloud Run
handles the compute-intensive audio processing that Cloudflare Workers can't do.
The split is clean and the pattern is reusable. Every artifact is stored with a
naming scheme that encodes enough information to reconstruct the entire index
from storage alone — the system can survive a complete database loss and recover.
User data is isolated by design from day one, not bolted on later.

## Why It Matters

This pipeline is the foundation that everything downstream depends on. Action
items, follow-up extraction, decision logging, idea capture — none of that is
possible without clean, indexed, transcribed audio. The pipeline doesn't do any
of that; it does the thing that makes all of that possible. It's the difference
between a pile of raw recordings and a knowledge base that can be reasoned over.

The architecture also makes a deliberate bet: that the Cloudflare + GCP split,
the modular ASR interface, and the event-driven completion model are worth doing
right the first time, even at MVP scale. Because the cost of rebuilding the
foundation once downstream features exist is much higher than building it
correctly now.

## What Success Looks Like

Every conversation captured by uCapture surfaces as a searchable transcript,
attributed to speakers, timestamped, and available in the upload history within
minutes of the recording completing. No audio is ever lost — failures are
recoverable, not destructive. The pipeline is observable enough that we can see
exactly where time and money are going at every stage. And the completion event
it emits is the hook that every downstream feature — starting with the Android
transcript viewer and eventually extending to AI-powered extraction — will plug
into.

The recordings are already happening. This is what makes them worth keeping.
