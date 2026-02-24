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
  };
}

/** Valid token response for mocking Google tokeninfo. */
function stubValidGoogleToken(): void {
  vi.stubGlobal('fetch', vi.fn().mockResolvedValue({
    ok: true,
    json: async () => ({ sub: '107234567890', email: 'test@example.com', exp: '9999999999' }),
  }));
}

describe('Hono route skeleton', () => {
  let env: Env;

  beforeEach(() => {
    vi.restoreAllMocks();
    env = createMockEnv();
    stubValidGoogleToken();
  });

  it('POST /v1/upload returns 400 when no multipart data is provided', async () => {
    const res = await app.request('/v1/upload', {
      method: 'POST',
      headers: { Authorization: 'Bearer valid-token' },
    }, env);
    expect(res.status).toBe(400);
    const body = await res.json();
    expect(body.error).toBeDefined();
  });

  it('GET /v1/status/:batch_id returns 501 Not Implemented when authenticated', async () => {
    const res = await app.request('/v1/status/test-batch-123', {
      method: 'GET',
      headers: { Authorization: 'Bearer valid-token' },
    }, env);
    expect(res.status).toBe(501);
    const body = await res.json();
    expect(body).toEqual({ error: 'Not implemented', code: 'NOT_IMPLEMENTED' });
  });

  it('GET /v1/batches returns 501 Not Implemented when authenticated', async () => {
    const res = await app.request('/v1/batches', {
      method: 'GET',
      headers: { Authorization: 'Bearer valid-token' },
    }, env);
    expect(res.status).toBe(501);
    const body = await res.json();
    expect(body).toEqual({ error: 'Not implemented', code: 'NOT_IMPLEMENTED' });
  });

  it('GET /v1/download/:batch_id/:artifact_type returns 501 Not Implemented when authenticated', async () => {
    const res = await app.request('/v1/download/test-batch-123/raw-audio', {
      method: 'GET',
      headers: { Authorization: 'Bearer valid-token' },
    }, env);
    expect(res.status).toBe(501);
    const body = await res.json();
    expect(body).toEqual({ error: 'Not implemented', code: 'NOT_IMPLEMENTED' });
  });

  it('GET /unknown-route returns 404', async () => {
    const res = await app.request('/unknown-route', { method: 'GET' }, env);
    expect(res.status).toBe(404);
  });

  it('all error responses have correct JSON content type', async () => {
    const res = await app.request('/v1/status/test-batch-123', {
      method: 'GET',
      headers: { Authorization: 'Bearer valid-token' },
    }, env);
    expect(res.headers.get('content-type')).toContain('application/json');
  });
});
