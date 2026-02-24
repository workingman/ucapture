import { describe, it, expect, vi, beforeEach } from 'vitest';
import app from '../src/index.ts';
import type { Env } from '../src/env.d.ts';
import type { BatchRow } from '../src/storage/d1.ts';

const INTERNAL_SECRET = 'test-internal-secret-abc123';
const TEST_BATCH_ID = '20260222-143027-GMT-a1b2c3d4-e5f6-7890-abcd-ef1234567890';
const TEST_USER_ID = '107234567890';

/** Creates a complete BatchRow fixture. */
function makeBatchRow(overrides?: Partial<BatchRow>): BatchRow {
  return {
    id: TEST_BATCH_ID,
    user_id: TEST_USER_ID,
    status: 'failed',
    priority: 'normal',
    raw_audio_path: `${TEST_USER_ID}/${TEST_BATCH_ID}/raw-audio/recording.m4a`,
    metadata_path: `${TEST_USER_ID}/${TEST_BATCH_ID}/metadata/metadata.json`,
    cleaned_audio_path: null,
    transcript_formatted_path: null,
    transcript_raw_path: null,
    transcript_emotion_path: null,
    recording_started_at: '2026-02-22T14:30:27Z',
    recording_ended_at: '2026-02-22T15:00:00Z',
    recording_duration_seconds: 1773,
    uploaded_at: '2026-02-22T14:31:00Z',
    processing_started_at: '2026-02-22T14:32:00Z',
    processing_completed_at: null,
    processing_wall_time_seconds: null,
    queue_wait_time_seconds: 60,
    raw_audio_size_bytes: 5242880,
    raw_audio_duration_seconds: 1773,
    speech_duration_seconds: null,
    speech_ratio: null,
    cleaned_audio_size_bytes: null,
    speechmatics_job_id: null,
    speechmatics_cost_estimate: null,
    emotion_provider: null,
    emotion_analyzed_at: null,
    retry_count: 2,
    error_message: 'Speechmatics API timeout',
    error_stage: 'transcription',
    ...overrides,
  };
}

/** Creates a mock D1Database that returns the given batch row. */
function createMockD1(batchRow: BatchRow | null): D1Database {
  const runFn = vi.fn(async () => ({ success: true, meta: {} }));

  return {
    prepare(_sql: string) {
      return {
        bind(..._args: unknown[]) {
          return this;
        },
        async first<T>(): Promise<T | null> {
          return (batchRow as T) ?? null;
        },
        async all() {
          return { results: [] };
        },
        run: runFn,
      };
    },
    async batch(statements: unknown[]) {
      return statements.map(() => ({ success: true, results: [], meta: {} }));
    },
    async dump() {
      return new ArrayBuffer(0);
    },
    async exec(_sql: string) {
      return { count: 0, duration: 0 };
    },
    _runFn: runFn,
  } as unknown as D1Database;
}

/** Creates a mock R2Bucket that returns a head result or null. */
function createMockR2(headResult: object | null): R2Bucket {
  return {
    head: vi.fn(async () => headResult),
    get: vi.fn(),
    put: vi.fn(),
    delete: vi.fn(),
    list: vi.fn(),
    createMultipartUpload: vi.fn(),
    resumeMultipartUpload: vi.fn(),
  } as unknown as R2Bucket;
}

/** Creates a mock Env with all required bindings. */
function createMockEnv(db: D1Database, r2: R2Bucket): Env {
  return {
    TOKEN_CACHE: {
      get: vi.fn(async () => null),
      put: vi.fn(),
      delete: vi.fn(),
      list: vi.fn(),
      getWithMetadata: vi.fn(),
    } as unknown as KVNamespace,
    R2_BUCKET: r2,
    DB: db,
    PROCESSING_QUEUE: { send: vi.fn(async () => {}) } as unknown as Queue,
    PROCESSING_QUEUE_PRIORITY: { send: vi.fn(async () => {}) } as unknown as Queue,
    R2_ACCOUNT_ID: 'test-account-id',
    R2_ACCESS_KEY_ID: 'test-access-key',
    R2_SECRET_ACCESS_KEY: 'test-secret-key',
    R2_BUCKET_NAME: 'test-bucket',
    INTERNAL_SECRET,
    PUBSUB_NAMESPACE: { publish: vi.fn(async () => {}) },
    PUBSUB_BROKER_URL: 'mqtts://broker.example.com:8883',
  };
}

describe('POST /internal/reprocess/:batch_id', () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  it('transitions a failed batch to uploaded and re-enqueues the job', async () => {
    const batch = makeBatchRow();
    const db = createMockD1(batch);
    const r2 = createMockR2({ size: 5242880 });
    const env = createMockEnv(db, r2);

    const res = await app.request(`/internal/reprocess/${TEST_BATCH_ID}`, {
      method: 'POST',
      headers: { 'X-Internal-Secret': INTERNAL_SECRET },
    }, env);

    expect(res.status).toBe(200);
    const body = await res.json();
    expect(body.batch_id).toBe(TEST_BATCH_ID);
    expect(body.status).toBe('uploaded');
    expect(body.requeued_at).toBeDefined();

    // Verify the job was enqueued to the normal queue
    expect((env.PROCESSING_QUEUE as unknown as { send: ReturnType<typeof vi.fn> }).send).toHaveBeenCalledOnce();
  });

  it('returns 403 when X-Internal-Secret is missing', async () => {
    const db = createMockD1(makeBatchRow());
    const r2 = createMockR2({ size: 5242880 });
    const env = createMockEnv(db, r2);

    const res = await app.request(`/internal/reprocess/${TEST_BATCH_ID}`, {
      method: 'POST',
    }, env);

    expect(res.status).toBe(403);
    const body = await res.json();
    expect(body.error).toBe('Forbidden');
  });

  it('returns 403 when X-Internal-Secret is wrong', async () => {
    const db = createMockD1(makeBatchRow());
    const r2 = createMockR2({ size: 5242880 });
    const env = createMockEnv(db, r2);

    const res = await app.request(`/internal/reprocess/${TEST_BATCH_ID}`, {
      method: 'POST',
      headers: { 'X-Internal-Secret': 'wrong-secret' },
    }, env);

    expect(res.status).toBe(403);
  });

  it('returns 404 when batch does not exist', async () => {
    const db = createMockD1(null);
    const r2 = createMockR2(null);
    const env = createMockEnv(db, r2);

    const res = await app.request('/internal/reprocess/nonexistent-batch', {
      method: 'POST',
      headers: { 'X-Internal-Secret': INTERNAL_SECRET },
    }, env);

    expect(res.status).toBe(404);
    const body = await res.json();
    expect(body.error).toBe('Batch not found');
  });

  it('returns 409 when batch is not in failed state', async () => {
    const batch = makeBatchRow({ status: 'completed' });
    const db = createMockD1(batch);
    const r2 = createMockR2({ size: 5242880 });
    const env = createMockEnv(db, r2);

    const res = await app.request(`/internal/reprocess/${TEST_BATCH_ID}`, {
      method: 'POST',
      headers: { 'X-Internal-Secret': INTERNAL_SECRET },
    }, env);

    expect(res.status).toBe(409);
    const body = await res.json();
    expect(body.error).toContain('only "failed" batches can be reprocessed');
  });

  it('returns 409 when batch is in processing state', async () => {
    const batch = makeBatchRow({ status: 'processing' });
    const db = createMockD1(batch);
    const r2 = createMockR2({ size: 5242880 });
    const env = createMockEnv(db, r2);

    const res = await app.request(`/internal/reprocess/${TEST_BATCH_ID}`, {
      method: 'POST',
      headers: { 'X-Internal-Secret': INTERNAL_SECRET },
    }, env);

    expect(res.status).toBe(409);
  });

  it('returns 404 when raw audio path is null in batch record', async () => {
    const batch = makeBatchRow({ raw_audio_path: null });
    const db = createMockD1(batch);
    const r2 = createMockR2(null);
    const env = createMockEnv(db, r2);

    const res = await app.request(`/internal/reprocess/${TEST_BATCH_ID}`, {
      method: 'POST',
      headers: { 'X-Internal-Secret': INTERNAL_SECRET },
    }, env);

    expect(res.status).toBe(404);
    const body = await res.json();
    expect(body.error).toBe('Raw audio path not found in batch record');
  });

  it('returns 404 when raw audio file is missing from R2', async () => {
    const batch = makeBatchRow();
    const db = createMockD1(batch);
    const r2 = createMockR2(null);
    const env = createMockEnv(db, r2);

    const res = await app.request(`/internal/reprocess/${TEST_BATCH_ID}`, {
      method: 'POST',
      headers: { 'X-Internal-Secret': INTERNAL_SECRET },
    }, env);

    expect(res.status).toBe(404);
    const body = await res.json();
    expect(body.error).toBe('Raw audio file not found in storage');

    // Verify R2 head was called with the correct path
    expect(r2.head).toHaveBeenCalledWith(batch.raw_audio_path);
  });

  it('enqueues to priority queue when batch has immediate priority', async () => {
    const batch = makeBatchRow({ priority: 'immediate' });
    const db = createMockD1(batch);
    const r2 = createMockR2({ size: 5242880 });
    const env = createMockEnv(db, r2);

    const res = await app.request(`/internal/reprocess/${TEST_BATCH_ID}`, {
      method: 'POST',
      headers: { 'X-Internal-Secret': INTERNAL_SECRET },
    }, env);

    expect(res.status).toBe(200);

    // Should use priority queue for immediate priority batches
    expect((env.PROCESSING_QUEUE_PRIORITY as unknown as { send: ReturnType<typeof vi.fn> }).send).toHaveBeenCalledOnce();
    expect((env.PROCESSING_QUEUE as unknown as { send: ReturnType<typeof vi.fn> }).send).not.toHaveBeenCalled();
  });
});
