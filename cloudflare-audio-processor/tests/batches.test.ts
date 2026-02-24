import { describe, it, expect, vi, beforeEach } from 'vitest';
import app from '../src/index.ts';
import type { Env } from '../src/env.d.ts';
import type { BatchRow } from '../src/storage/d1.ts';

const TEST_USER_ID = '107234567890';

/** Creates a BatchRow fixture. */
function makeBatchRow(overrides?: Partial<BatchRow>): BatchRow {
  return {
    id: '20260222-143027-GMT-a1b2c3d4-e5f6-7890-abcd-ef1234567890',
    user_id: TEST_USER_ID,
    status: 'completed',
    priority: 'normal',
    raw_audio_path: 'user/batch/raw-audio/recording.m4a',
    metadata_path: 'user/batch/metadata/metadata.json',
    cleaned_audio_path: null,
    transcript_formatted_path: null,
    transcript_raw_path: null,
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

/**
 * Creates a mock D1Database for batch list queries.
 * Alternates between all() (list query) and first() (count query) calls.
 */
function createMockD1(options?: {
  listResults?: BatchRow[];
  countResult?: number;
}): D1Database {
  const listResults = options?.listResults ?? [];
  const countResult = options?.countResult ?? listResults.length;

  return {
    prepare(_sql: string) {
      return {
        bind(..._args: unknown[]) {
          return this;
        },
        async first<T>(): Promise<T | null> {
          return { count: countResult } as T;
        },
        async all() {
          return { results: listResults };
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

function createMockEnv(db: D1Database): Env {
  return {
    TOKEN_CACHE: createMockKV(),
    R2_BUCKET: {} as R2Bucket,
    DB: db,
    PROCESSING_QUEUE: {} as Queue,
    PROCESSING_QUEUE_PRIORITY: {} as Queue,
  };
}

function stubValidGoogleToken(): void {
  vi.stubGlobal('fetch', vi.fn().mockResolvedValue({
    ok: true,
    json: async () => ({ sub: TEST_USER_ID, email: 'test@example.com', exp: '9999999999' }),
  }));
}

describe('GET /v1/batches', () => {
  beforeEach(() => {
    vi.restoreAllMocks();
    stubValidGoogleToken();
  });

  it('returns up to 50 batches with default pagination when no params given', async () => {
    const batches = [makeBatchRow(), makeBatchRow({ id: 'batch-2' })];
    const db = createMockD1({ listResults: batches, countResult: 2 });
    const env = createMockEnv(db);

    const res = await app.request('/v1/batches', {
      method: 'GET',
      headers: { Authorization: 'Bearer valid-token' },
    }, env);

    expect(res.status).toBe(200);
    const body = await res.json();
    expect(body.batches).toHaveLength(2);
    expect(body.pagination).toEqual({ limit: 50, offset: 0, total: 2 });
  });

  it('filters by status when ?status=completed is provided', async () => {
    const db = createMockD1({ listResults: [makeBatchRow()], countResult: 1 });
    const env = createMockEnv(db);

    const res = await app.request('/v1/batches?status=completed', {
      method: 'GET',
      headers: { Authorization: 'Bearer valid-token' },
    }, env);

    expect(res.status).toBe(200);
    const body = await res.json();
    expect(body.batches).toHaveLength(1);
    expect(body.batches[0].status).toBe('completed');
  });

  it('returns 400 for invalid status value', async () => {
    const db = createMockD1();
    const env = createMockEnv(db);

    const res = await app.request('/v1/batches?status=invalid', {
      method: 'GET',
      headers: { Authorization: 'Bearer valid-token' },
    }, env);

    expect(res.status).toBe(400);
    const body = await res.json();
    expect(body.error).toContain('Invalid query parameters');
  });

  it('returns 400 when limit exceeds 100', async () => {
    const db = createMockD1();
    const env = createMockEnv(db);

    const res = await app.request('/v1/batches?limit=200', {
      method: 'GET',
      headers: { Authorization: 'Bearer valid-token' },
    }, env);

    expect(res.status).toBe(400);
    const body = await res.json();
    expect(body.error).toContain('Invalid query parameters');
  });

  it('applies custom limit and offset', async () => {
    const db = createMockD1({ listResults: [], countResult: 50 });
    const env = createMockEnv(db);

    const res = await app.request('/v1/batches?limit=10&offset=20', {
      method: 'GET',
      headers: { Authorization: 'Bearer valid-token' },
    }, env);

    expect(res.status).toBe(200);
    const body = await res.json();
    expect(body.pagination).toEqual({ limit: 10, offset: 20, total: 50 });
  });

  it('returns empty batches array when no batches exist', async () => {
    const db = createMockD1({ listResults: [], countResult: 0 });
    const env = createMockEnv(db);

    const res = await app.request('/v1/batches', {
      method: 'GET',
      headers: { Authorization: 'Bearer valid-token' },
    }, env);

    expect(res.status).toBe(200);
    const body = await res.json();
    expect(body.batches).toEqual([]);
    expect(body.pagination).toEqual({ limit: 50, offset: 0, total: 0 });
  });

  it('accepts date range filters', async () => {
    const db = createMockD1({ listResults: [makeBatchRow()], countResult: 1 });
    const env = createMockEnv(db);

    const res = await app.request(
      '/v1/batches?start_date=2026-02-01T00:00:00Z&end_date=2026-02-28T23:59:59Z',
      {
        method: 'GET',
        headers: { Authorization: 'Bearer valid-token' },
      },
      env,
    );

    expect(res.status).toBe(200);
    const body = await res.json();
    expect(body.batches).toHaveLength(1);
  });
});
