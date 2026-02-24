import { describe, it, expect, vi, beforeEach } from 'vitest';
import app from '../src/index.ts';
import type { Env } from '../src/env.d.ts';
import type { BatchRow } from '../src/storage/d1.ts';

const TEST_USER_ID = '107234567890';
const OTHER_USER_ID = 'other-user-999';
const TEST_BATCH_ID = '20260222-143027-GMT-a1b2c3d4-e5f6-7890-abcd-ef1234567890';
/** Creates a BatchRow fixture with configurable artifact paths. */
function makeBatchRow(overrides?: Partial<BatchRow>): BatchRow {
  return {
    id: TEST_BATCH_ID,
    user_id: TEST_USER_ID,
    status: 'completed',
    priority: 'normal',
    raw_audio_path: `${TEST_USER_ID}/${TEST_BATCH_ID}/raw-audio/recording.m4a`,
    metadata_path: `${TEST_USER_ID}/${TEST_BATCH_ID}/metadata/metadata.json`,
    cleaned_audio_path: null,
    transcript_formatted_path: `${TEST_USER_ID}/${TEST_BATCH_ID}/transcript/formatted.json`,
    transcript_raw_path: `${TEST_USER_ID}/${TEST_BATCH_ID}/transcript/raw.json`,
    transcript_emotion_path: null,
    recording_started_at: '2026-02-22T14:30:27Z',
    recording_ended_at: '2026-02-22T15:00:00Z',
    recording_duration_seconds: 1773,
    uploaded_at: '2026-02-22T14:31:00Z',
    processing_started_at: null,
    processing_completed_at: null,
    processing_wall_time_seconds: null,
    queue_wait_time_seconds: null,
    raw_audio_size_bytes: 5242880,
    raw_audio_duration_seconds: 1773,
    speech_duration_seconds: null,
    speech_ratio: null,
    cleaned_audio_size_bytes: null,
    speechmatics_job_id: null,
    speechmatics_cost_estimate: null,
    emotion_provider: null,
    emotion_analyzed_at: null,
    retry_count: 0,
    error_message: null,
    error_stage: null,
    ...overrides,
  };
}

/** Creates a mock D1Database that returns a given batch row for findBatchById. */
function createMockD1(batchRow: BatchRow | null): D1Database {
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

function createMockKV(): KVNamespace {
  return {
    get: vi.fn(async () => null),
    put: vi.fn(),
    delete: vi.fn(),
    list: vi.fn(),
    getWithMetadata: vi.fn(),
  } as unknown as KVNamespace;
}

function createMockEnv(db: D1Database): Env {
  return {
    TOKEN_CACHE: createMockKV(),
    R2_BUCKET: {} as R2Bucket,
    DB: db,
    PROCESSING_QUEUE: {} as Queue,
    PROCESSING_QUEUE_PRIORITY: {} as Queue,
    R2_ACCOUNT_ID: 'fake-account-id',
    R2_ACCESS_KEY_ID: 'fake-access-key',
    R2_SECRET_ACCESS_KEY: 'fake-secret-key',
    R2_BUCKET_NAME: 'fake-bucket',
  };
}

function stubValidGoogleToken(userId = TEST_USER_ID): void {
  vi.stubGlobal('fetch', vi.fn().mockResolvedValue({
    ok: true,
    json: async () => ({ sub: userId, email: 'test@example.com', exp: '9999999999' }),
  }));
}

/** Mock presigned URL returned by the mocked presigner. */
const MOCK_PRESIGNED_URL = 'https://fake-account.r2.cloudflarestorage.com/bucket/path?X-Amz-Signature=abc&X-Amz-Expires=900';

/** Mocks the R2 presigner to return a predictable URL. */
vi.mock('../src/storage/r2.ts', async (importOriginal) => {
  const actual = await importOriginal<typeof import('../src/storage/r2.ts')>();
  return {
    ...actual,
    generatePresignedUrl: vi.fn().mockResolvedValue(
      'https://fake-account.r2.cloudflarestorage.com/bucket/path?X-Amz-Signature=abc&X-Amz-Expires=900',
    ),
  };
});

describe('GET /v1/download/:batch_id/:artifact_type', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    stubValidGoogleToken();
  });

  it('returns 302 with presigned URL for raw_audio download', async () => {
    const batch = makeBatchRow();
    const db = createMockD1(batch);
    const env = createMockEnv(db);

    const res = await app.request(`/v1/download/${TEST_BATCH_ID}/raw_audio`, {
      method: 'GET',
      headers: { Authorization: 'Bearer valid-token' },
      redirect: 'manual',
    }, env);

    expect(res.status).toBe(302);
    expect(res.headers.get('Location')).toBe(MOCK_PRESIGNED_URL);
  });

  it('returns 302 for transcript_formatted download', async () => {
    const batch = makeBatchRow();
    const db = createMockD1(batch);
    const env = createMockEnv(db);

    const res = await app.request(`/v1/download/${TEST_BATCH_ID}/transcript_formatted`, {
      method: 'GET',
      headers: { Authorization: 'Bearer valid-token' },
      redirect: 'manual',
    }, env);

    expect(res.status).toBe(302);
    expect(res.headers.get('Location')).toBe(MOCK_PRESIGNED_URL);
  });

  it('returns 403 for wrong user', async () => {
    const batch = makeBatchRow({ user_id: OTHER_USER_ID });
    const db = createMockD1(batch);
    const env = createMockEnv(db);
    stubValidGoogleToken(TEST_USER_ID);

    const res = await app.request(`/v1/download/${TEST_BATCH_ID}/raw_audio`, {
      method: 'GET',
      headers: { Authorization: 'Bearer valid-token' },
    }, env);

    expect(res.status).toBe(403);
    const body = await res.json();
    expect(body.error).toBe('Forbidden');
  });

  it('returns 404 for non-existent batch', async () => {
    const db = createMockD1(null);
    const env = createMockEnv(db);

    const res = await app.request('/v1/download/nonexistent-batch/raw_audio', {
      method: 'GET',
      headers: { Authorization: 'Bearer valid-token' },
    }, env);

    expect(res.status).toBe(404);
    const body = await res.json();
    expect(body.error).toBe('Batch not found');
  });

  it('returns 404 "Artifact not available" when artifact path is NULL', async () => {
    const batch = makeBatchRow({ cleaned_audio_path: null });
    const db = createMockD1(batch);
    const env = createMockEnv(db);

    const res = await app.request(`/v1/download/${TEST_BATCH_ID}/cleaned_audio`, {
      method: 'GET',
      headers: { Authorization: 'Bearer valid-token' },
    }, env);

    expect(res.status).toBe(404);
    const body = await res.json();
    expect(body.error).toBe('Artifact not available');
  });

  it('returns 400 for invalid artifact type', async () => {
    const batch = makeBatchRow();
    const db = createMockD1(batch);
    const env = createMockEnv(db);

    const res = await app.request(`/v1/download/${TEST_BATCH_ID}/invalid_type`, {
      method: 'GET',
      headers: { Authorization: 'Bearer valid-token' },
    }, env);

    expect(res.status).toBe(400);
    const body = await res.json();
    expect(body.error).toContain('Invalid artifact type');
  });
});
