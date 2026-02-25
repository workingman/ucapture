import { describe, it, expect, vi, beforeEach } from 'vitest';
import app from '../src/index.ts';
import type { Env } from '../src/env.d.ts';
import type { BatchRow, BatchImageRow } from '../src/storage/d1.ts';

const TEST_USER_ID = '107234567890';
const OTHER_USER_ID = 'other-user-999';
const TEST_BATCH_ID = '20260222-143027-GMT-a1b2c3d4-e5f6-7890-abcd-ef1234567890';

/** Creates a complete BatchRow fixture. */
function makeBatchRow(overrides?: Partial<BatchRow>): BatchRow {
  return {
    id: TEST_BATCH_ID,
    user_id: TEST_USER_ID,
    status: 'completed',
    priority: 'normal',
    raw_audio_path: `${TEST_USER_ID}/${TEST_BATCH_ID}/raw-audio/recording.m4a`,
    metadata_path: `${TEST_USER_ID}/${TEST_BATCH_ID}/metadata/metadata.json`,
    cleaned_audio_path: `${TEST_USER_ID}/${TEST_BATCH_ID}/cleaned-audio/cleaned.wav`,
    transcript_formatted_path: `${TEST_USER_ID}/${TEST_BATCH_ID}/transcript/formatted.json`,
    transcript_raw_path: `${TEST_USER_ID}/${TEST_BATCH_ID}/transcript/raw.json`,
    transcript_emotion_path: null,
    recording_started_at: '2026-02-22T14:30:27Z',
    recording_ended_at: '2026-02-22T15:00:00Z',
    recording_duration_seconds: 1773,
    uploaded_at: '2026-02-22T14:31:00Z',
    processing_started_at: '2026-02-22T14:32:00Z',
    processing_completed_at: '2026-02-22T14:45:00Z',
    processing_wall_time_seconds: 780,
    queue_wait_time_seconds: 60,
    raw_audio_size_bytes: 5242880,
    raw_audio_duration_seconds: 1773,
    speech_duration_seconds: 1500,
    speech_ratio: 0.85,
    cleaned_audio_size_bytes: 3000000,
    speechmatics_job_id: 'sm-job-123',
    speechmatics_cost_estimate: 0.12,
    emotion_provider: null,
    emotion_analyzed_at: null,
    retry_count: 0,
    error_message: null,
    error_stage: null,
    ...overrides,
  };
}

/** Creates a mock D1Database that returns preconfigured batch and image results. */
function createMockD1(options?: {
  batchRow?: BatchRow | null;
  imageRows?: BatchImageRow[];
}): D1Database {
  const batchRow = options?.batchRow ?? null;
  const imageRows = options?.imageRows ?? [];
  let queryCount = 0;

  return {
    prepare(sql: string) {
      return {
        bind(..._args: unknown[]) {
          return this;
        },
        async first<T>(): Promise<T | null> {
          // First query is findBatchById (SELECT * FROM batches WHERE id = ?)
          return (batchRow as T) ?? null;
        },
        async all() {
          // Second query is getBatchImages
          return { results: imageRows };
        },
        async run() {
          return { success: true, meta: {} };
        },
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
  } as unknown as D1Database;
}

/** Creates a mock KV namespace. */
function createMockKV(): KVNamespace {
  return {
    get: vi.fn(async () => null),
    put: vi.fn(),
    delete: vi.fn(),
    list: vi.fn(),
    getWithMetadata: vi.fn(),
  } as unknown as KVNamespace;
}

/** Creates a mock Env with the given D1 mock. */
function createMockEnv(db: D1Database): Env {
  return {
    TOKEN_CACHE: createMockKV(),
    R2_BUCKET: {} as R2Bucket,
    DB: db,
    PROCESSING_QUEUE: {} as Queue,
    PROCESSING_QUEUE_PRIORITY: {} as Queue,
  };
}

/** Stubs the Google tokeninfo endpoint to return a valid user. */
function stubValidGoogleToken(userId = TEST_USER_ID): void {
  vi.stubGlobal('fetch', vi.fn().mockResolvedValue({
    ok: true,
    json: async () => ({ sub: userId, email: 'test@example.com', exp: '9999999999' }),
  }));
}

describe('GET /v1/status/:batch_id', () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  it('returns 200 with full record for completed batch including artifacts and metrics', async () => {
    const batch = makeBatchRow();
    const images: BatchImageRow[] = [
      { id: 1, batch_id: TEST_BATCH_ID, r2_path: `${TEST_USER_ID}/${TEST_BATCH_ID}/images/0-photo.jpg`, captured_at: '2026-02-22T14:35:00Z', size_bytes: 102400 },
    ];
    const db = createMockD1({ batchRow: batch, imageRows: images });
    const env = createMockEnv(db);
    stubValidGoogleToken();

    const res = await app.request(`/v1/status/${TEST_BATCH_ID}`, {
      method: 'GET',
      headers: { Authorization: 'Bearer valid-token' },
    }, env);

    expect(res.status).toBe(200);
    const body = await res.json();
    expect(body.batch_id).toBe(TEST_BATCH_ID);
    expect(body.user_id).toBe(TEST_USER_ID);
    expect(body.status).toBe('completed');
    expect(body.artifacts.raw_audio).toBe(batch.raw_audio_path);
    expect(body.artifacts.metadata).toBe(batch.metadata_path);
    expect(body.artifacts.cleaned_audio).toBe(batch.cleaned_audio_path);
    expect(body.artifacts.transcript_formatted).toBe(batch.transcript_formatted_path);
    expect(body.artifacts.transcript_raw).toBe(batch.transcript_raw_path);
    expect(body.artifacts.transcript_emotion).toBeUndefined();
    expect(body.artifacts.images).toEqual([images[0].r2_path]);
    expect(body.metrics.speech_duration_seconds).toBe(1500);
    expect(body.metrics.speech_ratio).toBe(0.85);
    expect(body.metrics.speechmatics_cost_estimate).toBe(0.12);
  });

  it('returns 200 with error details for failed batch', async () => {
    const batch = makeBatchRow({
      status: 'failed',
      error_message: 'Speechmatics API timeout',
      error_stage: 'transcription',
      retry_count: 2,
    });
    const db = createMockD1({ batchRow: batch });
    const env = createMockEnv(db);
    stubValidGoogleToken();

    const res = await app.request(`/v1/status/${TEST_BATCH_ID}`, {
      method: 'GET',
      headers: { Authorization: 'Bearer valid-token' },
    }, env);

    expect(res.status).toBe(200);
    const body = await res.json();
    expect(body.status).toBe('failed');
    expect(body.error_message).toBe('Speechmatics API timeout');
    expect(body.error_stage).toBe('transcription');
    expect(body.retry_count).toBe(2);
  });

  it('returns 403 when batch belongs to different user', async () => {
    const batch = makeBatchRow({ user_id: OTHER_USER_ID });
    const db = createMockD1({ batchRow: batch });
    const env = createMockEnv(db);
    stubValidGoogleToken(TEST_USER_ID);

    const res = await app.request(`/v1/status/${TEST_BATCH_ID}`, {
      method: 'GET',
      headers: { Authorization: 'Bearer valid-token' },
    }, env);

    expect(res.status).toBe(403);
    const body = await res.json();
    expect(body.error).toBe('Forbidden');
  });

  it('returns 404 when batch_id does not exist', async () => {
    const db = createMockD1({ batchRow: null });
    const env = createMockEnv(db);
    stubValidGoogleToken();

    const res = await app.request('/v1/status/nonexistent-batch', {
      method: 'GET',
      headers: { Authorization: 'Bearer valid-token' },
    }, env);

    expect(res.status).toBe(404);
    const body = await res.json();
    expect(body.error).toBe('Batch not found');
  });

  it('omits NULL artifact paths from artifacts map', async () => {
    const batch = makeBatchRow({
      cleaned_audio_path: null,
      transcript_formatted_path: null,
      transcript_raw_path: null,
      transcript_emotion_path: null,
    });
    const db = createMockD1({ batchRow: batch });
    const env = createMockEnv(db);
    stubValidGoogleToken();

    const res = await app.request(`/v1/status/${TEST_BATCH_ID}`, {
      method: 'GET',
      headers: { Authorization: 'Bearer valid-token' },
    }, env);

    expect(res.status).toBe(200);
    const body = await res.json();
    expect(body.artifacts.raw_audio).toBeDefined();
    expect(body.artifacts.metadata).toBeDefined();
    expect(body.artifacts.cleaned_audio).toBeUndefined();
    expect(body.artifacts.transcript_formatted).toBeUndefined();
    expect(body.artifacts.transcript_raw).toBeUndefined();
    expect(body.artifacts.transcript_emotion).toBeUndefined();
  });

  it('includes images array from batch_images join', async () => {
    const batch = makeBatchRow();
    const images: BatchImageRow[] = [
      { id: 1, batch_id: TEST_BATCH_ID, r2_path: 'user/batch/images/0-photo1.jpg', captured_at: '2026-02-22T14:35:00Z', size_bytes: 102400 },
      { id: 2, batch_id: TEST_BATCH_ID, r2_path: 'user/batch/images/1-photo2.jpg', captured_at: '2026-02-22T14:40:00Z', size_bytes: 204800 },
    ];
    const db = createMockD1({ batchRow: batch, imageRows: images });
    const env = createMockEnv(db);
    stubValidGoogleToken();

    const res = await app.request(`/v1/status/${TEST_BATCH_ID}`, {
      method: 'GET',
      headers: { Authorization: 'Bearer valid-token' },
    }, env);

    expect(res.status).toBe(200);
    const body = await res.json();
    expect(body.artifacts.images).toEqual([
      'user/batch/images/0-photo1.jpg',
      'user/batch/images/1-photo2.jpg',
    ]);
  });

  it('omits images from artifacts when no images exist', async () => {
    const batch = makeBatchRow();
    const db = createMockD1({ batchRow: batch, imageRows: [] });
    const env = createMockEnv(db);
    stubValidGoogleToken();

    const res = await app.request(`/v1/status/${TEST_BATCH_ID}`, {
      method: 'GET',
      headers: { Authorization: 'Bearer valid-token' },
    }, env);

    expect(res.status).toBe(200);
    const body = await res.json();
    expect(body.artifacts.images).toBeUndefined();
  });
});
