# QA State — Audio Pipeline (cloudflare-audio-processor)

## Tech Stack (derived from TDD)
- Build command(s): `pnpm tsc --noEmit` (Worker), `ruff check audio_processor/` (GCP)
- Dev server: `pnpm wrangler dev` (Worker), `python -m audio_processor.main` (GCP)
- Test command: `pnpm vitest run` (Worker), `pytest` (GCP)
- Compilers/bundlers: TypeScript, Wrangler (Worker); Python 3.11+, Docker (GCP)
- Linter(s): ESLint + Prettier (Worker); Ruff + Black (GCP)

## Current Position
Layer: GCP-DEPLOY
Step: pending
Cycle: 1

## Layer Status
| Layer    | Status       | Issues Filed | Issues Open | Notes                                |
|----------|--------------|-------------|-------------|--------------------------------------|
| BUILD    | PASS         | —           | —           | Typecheck clean, ruff clean, 301 tests |
| BOOT     | PASS (Worker only) | —     | —           | Worker verified on :8787. GCP booted locally during dev but never deployed to Cloud Run. |
| RENDER   | PASS (Worker only) | #49,#50,#51,#52,#53 | — | All 5 issues resolved against deployed Worker. GCP pipeline untested on real infra. |
| FUNCTION | PASS (Worker only) | F-007 (#61) | #61   | Track A: 310/310 tests. Track B: 11/11 Worker curl tests pass. GCP pipeline never triggered end-to-end. |
| POLISH   | CODE DONE    | #54,#55,#56,#57,#58,#59,#60 | — | All 7 fixes committed. Unverified in prod — GCP not yet deployed. |
| GCP-DEPLOY | PENDING    | —           | —           | Deploy to Cloud Run, run end-to-end pipeline test (upload → queue → GCP → ASR → transcript). |

## Layer Summaries (wisdom — persists across context boundaries)

### BUILD
Zero issues. TypeScript typecheck clean, ruff clean, all 301 tests (117 Vitest + 184 pytest) passing.
No substantive or cosmetic warnings. Clean first pass.

### BOOT
Zero issues. Worker responds on :8787 with correct 401/403 for unauthenticated requests.
GCP health endpoint returns 200 on :8080. Queue consumer polls. SIGTERM triggers graceful shutdown.

### RENDER
6 findings across 5 root-cause clusters. Two blocking: R2 path mismatch between Worker
(`/raw-audio/`) and GCP (`/audio/`) would have failed every pipeline run; CompletionEvent
missing `recording_started_at` would have failed Worker validation on every event publish.
Two substantive: StatusResponse metrics were flat instead of nested; batch list over-returned
full records instead of summaries. Pattern: GCP pipeline was developed with slightly different
path/field assumptions than the Worker — integration contracts need review during implementation.

### FUNCTION
Track A (automated): 310/310 tests passing (118 Vitest + 192 pytest). Track B (manual curl against
deployed Worker at audio-processor.geoff-ec6.workers.dev): 11/11 executed tests pass, 1 skipped
(cross-user isolation — no TOKEN2). Upload, status, download (presigned R2 URLs), batch list, filters,
auth rejection, and Pub/Sub credentials all verified on live Cloudflare infrastructure. One integration
finding: F-007 — Android app metadata format doesn't match Worker upload API schema (blocking for
end-to-end, not blocking for Worker correctness).

### POLISH
10 findings across 7 root-cause clusters. All in GCP processor (Worker passed clean). Four substantive:
retry logic retries permanent failures (wasting 7s on unrecoverable errors); VAD threshold not
configurable and partial frames discarded; graceful shutdown has no timeout vs Cloud Run's 30s SIGKILL;
ffmpeg hangs 120s on corrupt audio. Three cosmetic: retry/error logging gaps, D1Client connection
reuse, test coverage gaps for edge cases. Pattern: resilience and edge-case handling was secondary
during implementation — happy path is solid but failure modes need hardening.

## Active Context
Worker QA complete and deployed. GCP QA incomplete — code is written and unit-tested but GCP
has never been deployed to Cloud Run or run against real infrastructure. All POLISH findings
were GCP-side fixes; none have been smoke-tested in production.

Next steps:
1. Deploy GCP processor to Cloud Run
2. Run end-to-end pipeline: upload audio → Worker → CF Queue → GCP → Speechmatics → transcript
3. Verify POLISH fixes hold under real load (retry, shutdown, VAD, ffprobe)
4. Mark GCP-DEPLOY PASS once end-to-end produces a transcript

F-007 (#61): fix-F-007.md written for Android dev. Blocking end-to-end from Android but
not blocking GCP deployment test (can use curl to upload directly).

## POLISH Layer — Session Prompt

Paste this into a new Claude Code session to resume:

```
Resume QA POLISH layer for cloudflare-audio-processor.

## Context Recovery
1. Read `qa-state.md` and `qa-findings.md` in project root
2. Read `process/first-run-qa.md` for POLISH layer definition
3. Read `.claude/CLAUDE.md` for agent rules

## Current State
- BUILD: PASS, BOOT: PASS, RENDER: PASS, FUNCTION: PASS
- POLISH: ACTIVE
- Worker deployed at https://audio-processor.geoff-ec6.workers.dev
- CF resources: D1, R2, KV, 2 Queues — all live
- 310 tests (118 Vitest + 192 pytest), all passing
- F-007 open: Android metadata format mismatch (needs issue filed on GitHub)

## What To Do
1. Read process/first-run-qa.md to understand POLISH layer scope
2. File GitHub issue for F-007 (Android metadata format mismatch)
3. Review edge cases, error handling, security hardening
4. Check: upload size limits, token expiry handling, R2 presigned URL expiry
5. Check: queue retry behavior, error propagation, graceful degradation
6. Follow process/first-run-qa.md strictly — document findings, file issues
7. If zero new findings: mark POLISH PASS, update qa-state.md

## Key Files
- qa-state.md — layer status and summaries
- qa-findings.md — all findings (F-001 through F-007)
- FUNCTION_PREP.md — deployment details and curl test reference
- .env — credentials (gitignored)
```

## Human Feedback Log
{No entries yet}
