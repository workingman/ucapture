# FUNCTION Layer — Prep & Session Prompt

## Status

- **Track A (automated tests): PASS** — 310/310 tests passing (118 Vitest + 192 pytest)
- **Track B (manual curl tests): READY** — scripts written, need deployment + token + test data

---

## Prerequisites Checklist

### 1. jq (JSON parser for curl scripts)

Already installed: `jq-1.7.1-apple` at `/usr/bin/jq`.

### 2. Google OAuth Bearer Token

The Worker validates tokens via Google's `tokeninfo` endpoint and extracts the
`sub` claim as `user_id`. Any valid Google access token works — scopes don't
matter.

**Recommended: gcloud CLI** (simplest for repeated use)

```bash
# One-time setup (opens browser)
gcloud auth login

# Get a token (valid ~1 hour, re-run when expired)
TOKEN=$(gcloud auth print-access-token)
```

**Alternative: OAuth Playground** (no install, browser only)

1. Open https://developers.google.com/oauthplayground/
2. Select any scope (e.g. `openid`) — scope doesn't matter
3. Click "Authorize APIs" → sign in → allow
4. Click "Exchange authorization code for tokens"
5. Copy the **Access Token** (valid ~1 hour)

**For cross-user isolation test (optional):** get a second token from a
different Google account and set `TOKEN2`.

### 3. Deploy Worker to Cloudflare

The curl tests target a **deployed Worker**, not local dev. Local dev
(`wrangler dev`) uses placeholder binding IDs and won't have real D1/R2.

**Resources to create (Cloudflare dashboard or CLI):**

| Resource | Type | Name |
|----------|------|------|
| D1 Database | D1 | `audio-processor-db` |
| R2 Bucket | R2 | `audio-uploads` |
| KV Namespace | KV | (for token cache) |
| Queue | Queue | `audio-processing` |
| Queue | Queue | `audio-processing-priority` |

**After creating resources, update `wrangler.toml`:**
- Replace `placeholder-id` for D1 `database_id` with the real ID
- Replace `placeholder-id` for KV `id` with the real ID

**Secrets to set:**

```bash
wrangler secret put INTERNAL_SECRET        # shared secret for GCP→Worker auth
wrangler secret put R2_ACCESS_KEY_ID       # S3-compat key for presigned URLs
wrangler secret put R2_SECRET_ACCESS_KEY   # S3-compat secret for presigned URLs
wrangler secret put R2_ACCOUNT_ID          # your Cloudflare account ID
wrangler secret put R2_BUCKET_NAME         # "audio-uploads"
wrangler secret put PUBSUB_BROKER_URL      # MQTT broker URL (Pub/Sub is beta)
```

**Deploy:**

```bash
pnpm wrangler deploy
```

Worker URL will be: `https://audio-processor.<subdomain>.workers.dev`

**Run D1 migrations:**

```bash
wrangler d1 migrations apply audio-processor-db --remote
```

### 4. Test Data

Place files in `test-data/` (gitignored):

| File | Purpose |
|------|---------|
| `*.m4a` | Audio recordings (AAC, 44.1kHz, mono) |
| `*.json` | Metadata sidecars (matching basename, e.g. `meeting.m4a` + `meeting.json`) |
| `metadata-template.json` | Fallback metadata for .m4a files without a matching .json |

The curl script auto-discovers all `.m4a` files and pairs each with its
`.json` sidecar (falls back to `metadata-template.json` if none exists).

### 5. Configure the Script

Edit `test-data/curl-tests.sh`:

```bash
BASE_URL="https://audio-processor.YOUR-SUBDOMAIN.workers.dev"
```

Or pass as environment variable:

```bash
TOKEN=$(gcloud auth print-access-token) \
BASE_URL="https://audio-processor.xxx.workers.dev" \
  bash test-data/curl-tests.sh
```

---

## What the Tests Cover

| # | Test | Endpoint | Expected |
|---|------|----------|----------|
| G1 | Health check | `GET /` | 200 |
| G2 | Auth rejection | `POST /v1/upload` (no token) | 401 |
| G3 | Nonexistent batch | `GET /v1/status/fake-id` | 404 |
| G4 | Pub/Sub credentials | `GET /v1/pubsub/credentials` | 200 |
| P1 | Upload (per file) | `POST /v1/upload` | 202 |
| P2 | Status query | `GET /v1/status/:batch_id` | 200 |
| P3 | Download audio | `GET /v1/download/:batch_id/raw_audio` | 302 |
| P4 | Download metadata | `GET /v1/download/:batch_id/metadata` | 302 |
| P5 | Invalid artifact | `GET /v1/download/:batch_id/nonexistent` | 400 |
| A1 | Batch list | `GET /v1/batches` | 200, all batch_ids present |
| A2 | Filtered list | `GET /v1/batches?status=uploaded&limit=10` | 200 |
| A3 | Cross-user isolation | `GET /v1/status/:batch_id` (TOKEN2) | 403 |

G = global (once), P = per-file, A = after-all-uploads

---

## Session Prompt

Paste this into a new Claude Code session to resume:

```
Resume QA FUNCTION layer for cloudflare-audio-processor.

## Context Recovery
1. Read `qa-state.md` and `qa-findings.md` in project root
2. Read `FUNCTION_PREP.md` in project root
3. Read `.claude/CLAUDE.md` for agent rules

## Current State
- BUILD: PASS, BOOT: PASS, RENDER: PASS (5 issues filed and fixed)
- FUNCTION: ACTIVE
  - Track A (automated): PASS — 310/310 tests (118 Vitest + 192 pytest)
  - Track B (manual curl): scripts ready in test-data/curl-tests.sh

## What To Do
1. Verify the Worker is deployed and accessible at the BASE_URL
2. Run `bash test-data/curl-tests.sh` and capture results
3. Parse failures into findings in qa-findings.md
4. Triage findings by root cause, file issues per the QA process
5. If zero findings: mark FUNCTION layer PASS, update qa-state.md
6. Follow process/first-run-qa.md strictly — never fix inline

## Prerequisites Confirmed
- jq installed (v1.7.1)
- Test data in test-data/ (m4a + json files)
- TOKEN set via `gcloud auth print-access-token`
- BASE_URL set to deployed Worker URL
```

---

## Not Needed for Track B

- **Speechmatics API key** — curl tests only hit the Worker, not GCP
- **GCP credentials** — the processor is a separate deployment
- **Pub/Sub setup** — the credentials endpoint returns config, doesn't need a real broker
- **Docker** — no containers involved in Worker testing
