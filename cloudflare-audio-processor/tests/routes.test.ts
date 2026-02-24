import { describe, it, expect, vi, beforeEach } from 'vitest';
import app from '../src/index.ts';
import type { Env } from '../src/env.d.ts';

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

/** Creates a minimal mock Env. */
function createMockEnv(): Env {
  return {
    TOKEN_CACHE: createMockKV(),
    R2_BUCKET: {} as R2Bucket,
    DB: {} as D1Database,
    PROCESSING_QUEUE: {} as Queue,
    PROCESSING_QUEUE_PRIORITY: {} as Queue,
    R2_ACCOUNT_ID: 'fake-account',
    R2_ACCESS_KEY_ID: 'fake-key',
    R2_SECRET_ACCESS_KEY: 'fake-secret',
    R2_BUCKET_NAME: 'fake-bucket',
  };
}

describe('Query route auth enforcement', () => {
  let env: Env;

  beforeEach(() => {
    vi.restoreAllMocks();
    env = createMockEnv();
  });

  it('GET /v1/status/:batch_id without auth returns 401', async () => {
    const res = await app.request('/v1/status/test-batch-123', {
      method: 'GET',
    }, env);
    expect(res.status).toBe(401);
    const body = await res.json();
    expect(body.error).toBeDefined();
  });

  it('GET /v1/batches without auth returns 401', async () => {
    const res = await app.request('/v1/batches', {
      method: 'GET',
    }, env);
    expect(res.status).toBe(401);
    const body = await res.json();
    expect(body.error).toBeDefined();
  });

  it('GET /v1/download/:batch_id/:artifact_type without auth returns 401', async () => {
    const res = await app.request('/v1/download/test-batch-123/raw_audio', {
      method: 'GET',
    }, env);
    expect(res.status).toBe(401);
    const body = await res.json();
    expect(body.error).toBeDefined();
  });

  it('routes dispatch to correct handlers when authenticated', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({ sub: '107234567890', email: 'test@example.com', exp: '9999999999' }),
    }));

    // Status route: dispatches to handler (fails on mock DB, but proves routing works)
    const statusRes = await app.request('/v1/status/test-batch', {
      method: 'GET',
      headers: { Authorization: 'Bearer valid-token' },
    }, env);
    // Not 401 and not 501 -- handler is wired
    expect(statusRes.status).not.toBe(401);
    expect(statusRes.status).not.toBe(501);

    // Batches route: dispatches to handler
    const batchesRes = await app.request('/v1/batches', {
      method: 'GET',
      headers: { Authorization: 'Bearer valid-token' },
    }, env);
    expect(batchesRes.status).not.toBe(401);
    expect(batchesRes.status).not.toBe(501);

    // Download route: dispatches to handler (400 for invalid type proves routing)
    const downloadRes = await app.request('/v1/download/test-batch/invalid_type', {
      method: 'GET',
      headers: { Authorization: 'Bearer valid-token' },
    }, env);
    expect(downloadRes.status).toBe(400);
  });

  it('response interfaces are importable from types/api.ts (compile-time check)', async () => {
    // TypeScript interfaces are erased at runtime, so we verify the module loads
    // and that the types compile correctly by importing them above.
    // The actual type-level verification is done by `pnpm tsc --noEmit`.
    const apiModule = await import('../src/types/api.ts');
    expect(apiModule).toBeDefined();
  });
});
