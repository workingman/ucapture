import { describe, it, expect, vi, beforeEach } from 'vitest';
import app from '../src/index.ts';
import type { Env } from '../src/env.d.ts';

/** Valid metadata JSON for building multipart uploads. */
const VALID_METADATA = {
  recording: {
    started_at: '2026-02-22T14:30:00Z',
    ended_at: '2026-02-22T14:45:00Z',
    duration_seconds: 900,
    audio_format: 'aac',
    sample_rate: 44100,
    channels: 1,
    bitrate: 128000,
    file_size_bytes: 1024000,
  },
  device: {
    model: 'Pixel 7',
    os_version: 'Android 14',
    app_version: '1.0.0',
  },
};

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

/** Creates a mock R2 bucket that succeeds by default. */
function createMockR2Bucket(): R2Bucket {
  return {
    put: vi.fn(async () => ({}) as R2Object),
    get: vi.fn(),
    head: vi.fn(),
    delete: vi.fn(),
    list: vi.fn(),
    createMultipartUpload: vi.fn(),
    resumeMultipartUpload: vi.fn(),
  } as unknown as R2Bucket;
}

/** Creates a mock D1 database that succeeds by default. */
function createMockD1(): D1Database {
  const createStatement = () => ({
    bind: vi.fn().mockReturnThis(),
    run: vi.fn(async () => ({ success: true, meta: {} })),
    first: vi.fn(async () => null),
    all: vi.fn(async () => ({ results: [] })),
  });

  return {
    prepare: vi.fn(() => createStatement()),
    batch: vi.fn(async (stmts: unknown[]) =>
      stmts.map(() => ({ success: true, results: [], meta: {} })),
    ),
    dump: vi.fn(),
    exec: vi.fn(),
  } as unknown as D1Database;
}

/** Creates a mock Queue that succeeds by default. */
function createMockQueue(): Queue {
  return { send: vi.fn() } as unknown as Queue;
}

/** Stubs Google token validation to return a valid user. */
function stubValidGoogleToken(): void {
  vi.stubGlobal('fetch', vi.fn().mockResolvedValue({
    ok: true,
    json: async () => ({ sub: '107234567890', email: 'test@example.com', exp: '9999999999' }),
  }));
}

/** Builds a valid multipart FormData for upload. */
function buildValidFormData(): FormData {
  const form = new FormData();
  form.append('audio', new File(['audio-content'], 'recording.m4a', { type: 'audio/mp4' }));
  form.append('metadata', new File([JSON.stringify(VALID_METADATA)], 'metadata.json', { type: 'application/json' }));
  return form;
}

/** Creates a full mock Env with configurable overrides. */
function createMockEnv(overrides: Partial<Env> = {}): Env {
  return {
    TOKEN_CACHE: createMockKV(),
    R2_BUCKET: createMockR2Bucket(),
    DB: createMockD1(),
    PROCESSING_QUEUE: createMockQueue(),
    PROCESSING_QUEUE_PRIORITY: createMockQueue(),
    ...overrides,
  };
}

describe('upload error handling', () => {
  beforeEach(() => {
    vi.restoreAllMocks();
    stubValidGoogleToken();
  });

  it('returns 500 when R2 write fails', async () => {
    const failingBucket = createMockR2Bucket();
    (failingBucket.put as ReturnType<typeof vi.fn>).mockRejectedValue(
      new Error('R2 write failed: network timeout'),
    );
    const env = createMockEnv({ R2_BUCKET: failingBucket });

    const res = await app.request('/v1/upload', {
      method: 'POST',
      headers: { Authorization: 'Bearer valid-token' },
      body: buildValidFormData(),
    }, env);

    expect(res.status).toBe(500);
    const body = await res.json();
    expect(body.error).toBeDefined();
  });

  it('returns 500 and logs orphan paths when D1 fails after R2 success', async () => {
    const consoleSpy = vi.spyOn(console, 'error').mockImplementation(() => {});
    const failingDb = createMockD1();
    (failingDb.prepare as ReturnType<typeof vi.fn>).mockReturnValue({
      bind: vi.fn().mockReturnThis(),
      run: vi.fn().mockRejectedValue(new Error('D1 constraint violation')),
      first: vi.fn(),
      all: vi.fn(),
    });
    const env = createMockEnv({ DB: failingDb });

    const res = await app.request('/v1/upload', {
      method: 'POST',
      headers: { Authorization: 'Bearer valid-token' },
      body: buildValidFormData(),
    }, env);

    expect(res.status).toBe(500);
    const body = await res.json();
    expect(body.error).toBeDefined();

    // Verify orphan logging occurred with structured JSON
    const orphanLog = consoleSpy.mock.calls.find((call) => {
      const msg = String(call[0]);
      return msg.includes('orphaned_r2_artifacts');
    });
    expect(orphanLog).toBeDefined();
    const logData = JSON.parse(String(orphanLog![0]));
    expect(logData.event).toBe('orphaned_r2_artifacts');
    expect(logData.batch_id).toBeDefined();
    expect(logData.r2_paths).toBeInstanceOf(Array);
    expect(logData.r2_paths.length).toBeGreaterThanOrEqual(2); // audio + metadata at minimum

    consoleSpy.mockRestore();
  });

  it('returns 500 and logs unqueued batch when queue fails after D1 success', async () => {
    const consoleSpy = vi.spyOn(console, 'error').mockImplementation(() => {});
    const failingQueue = createMockQueue();
    (failingQueue.send as ReturnType<typeof vi.fn>).mockRejectedValue(
      new Error('Queue unavailable'),
    );
    const env = createMockEnv({
      PROCESSING_QUEUE: failingQueue,
      PROCESSING_QUEUE_PRIORITY: failingQueue,
    });

    const res = await app.request('/v1/upload', {
      method: 'POST',
      headers: { Authorization: 'Bearer valid-token' },
      body: buildValidFormData(),
    }, env);

    expect(res.status).toBe(500);
    const body = await res.json();
    expect(body.error).toBeDefined();

    // Verify unqueued batch logging
    const unqueuedLog = consoleSpy.mock.calls.find((call) => {
      const msg = String(call[0]);
      return msg.includes('unqueued_batch');
    });
    expect(unqueuedLog).toBeDefined();
    const logData = JSON.parse(String(unqueuedLog![0]));
    expect(logData.event).toBe('unqueued_batch');
    expect(logData.batch_id).toBeDefined();

    consoleSpy.mockRestore();
  });

  it('returns 413 when Content-Length exceeds 100MB', async () => {
    const env = createMockEnv();
    const oversizeLength = String(101 * 1024 * 1024);

    const res = await app.request('/v1/upload', {
      method: 'POST',
      headers: {
        Authorization: 'Bearer valid-token',
        'Content-Length': oversizeLength,
      },
      body: buildValidFormData(),
    }, env);

    expect(res.status).toBe(413);
    const body = await res.json();
    expect(body.error).toContain('100MB');
  });

  it('all error responses use { error: "..." } shape', async () => {
    const env = createMockEnv();

    // 400: missing multipart data
    const res400 = await app.request('/v1/upload', {
      method: 'POST',
      headers: { Authorization: 'Bearer valid-token' },
    }, env);
    expect(res400.status).toBe(400);
    const body400 = await res400.json();
    expect(typeof body400.error).toBe('string');

    // 413: payload too large
    const res413 = await app.request('/v1/upload', {
      method: 'POST',
      headers: {
        Authorization: 'Bearer valid-token',
        'Content-Length': String(200 * 1024 * 1024),
      },
      body: buildValidFormData(),
    }, env);
    expect(res413.status).toBe(413);
    const body413 = await res413.json();
    expect(typeof body413.error).toBe('string');

    // 500: R2 failure
    const failingBucket = createMockR2Bucket();
    (failingBucket.put as ReturnType<typeof vi.fn>).mockRejectedValue(new Error('boom'));
    const envR2Fail = createMockEnv({ R2_BUCKET: failingBucket });
    const res500 = await app.request('/v1/upload', {
      method: 'POST',
      headers: { Authorization: 'Bearer valid-token' },
      body: buildValidFormData(),
    }, envR2Fail);
    expect(res500.status).toBe(500);
    const body500 = await res500.json();
    expect(typeof body500.error).toBe('string');
  });
});
