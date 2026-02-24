import { describe, it, expect, vi, beforeEach } from 'vitest';
import { validateGoogleToken } from '../src/auth/google.ts';
import { Hono } from 'hono';
import { authMiddleware } from '../src/auth/middleware.ts';
import type { Env } from '../src/env.d.ts';

/** Creates a mock KV namespace with get/put methods. */
function createMockKV(store: Record<string, string> = {}): KVNamespace {
  return {
    get: vi.fn(async (key: string) => {
      const value = store[key];
      return value ? JSON.parse(value) : null;
    }),
    put: vi.fn(async (key: string, value: string) => {
      store[key] = value;
    }),
    delete: vi.fn(),
    list: vi.fn(),
    getWithMetadata: vi.fn(),
  } as unknown as KVNamespace;
}

/** Creates a minimal mock Env for auth testing. */
function createMockEnv(kvStore: Record<string, string> = {}): Env {
  return {
    TOKEN_CACHE: createMockKV(kvStore),
    R2_BUCKET: {} as R2Bucket,
    DB: {} as D1Database,
    PROCESSING_QUEUE: {} as Queue,
    PROCESSING_QUEUE_PRIORITY: {} as Queue,
  };
}

describe('validateGoogleToken', () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  it('returns sub and email for a valid Google token', async () => {
    const mockResponse = { sub: '107234567890', email: 'user@example.com', exp: '1234567890' };
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({
      ok: true,
      json: async () => mockResponse,
    }));

    const cache = createMockKV();
    const result = await validateGoogleToken('valid-token-123', cache);

    expect(result).toEqual({ sub: '107234567890', email: 'user@example.com' });
    expect(cache.put).toHaveBeenCalledWith(
      'token:valid-token-123',
      JSON.stringify({ sub: '107234567890', email: 'user@example.com' }),
      { expirationTtl: 3600 },
    );
  });

  it('returns cached claims without calling Google API', async () => {
    const cachedClaims = { sub: '107234567890', email: 'cached@example.com' };
    const kvStore: Record<string, string> = {
      'token:cached-token': JSON.stringify(cachedClaims),
    };
    const cache = createMockKV(kvStore);
    const fetchMock = vi.fn();
    vi.stubGlobal('fetch', fetchMock);

    const result = await validateGoogleToken('cached-token', cache);

    expect(result).toEqual(cachedClaims);
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it('throws AuthenticationError when Google returns non-2xx', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({
      ok: false,
      status: 400,
      json: async () => ({ error_description: 'Invalid Value' }),
    }));

    const cache = createMockKV();

    await expect(validateGoogleToken('invalid-token', cache)).rejects.toThrow(
      'Invalid or expired access token',
    );
  });

  it('throws AuthenticationError when Google response missing sub or email', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({ exp: '1234567890' }),
    }));

    const cache = createMockKV();

    await expect(validateGoogleToken('no-claims-token', cache)).rejects.toThrow(
      'Token missing required claims (sub, email)',
    );
  });
});

describe('authMiddleware', () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  it('returns 401 when Authorization header is missing', async () => {
    const env = createMockEnv();
    const app = new Hono<{ Bindings: Env; Variables: { user_id: string; email: string } }>();
    app.use('/v1/*', authMiddleware);
    app.get('/v1/test', (c) => c.json({ ok: true }));

    const res = await app.request('/v1/test', { method: 'GET' }, env);

    expect(res.status).toBe(401);
    const body = await res.json();
    expect(body).toEqual({ error: 'Missing Authorization header' });
  });
});
