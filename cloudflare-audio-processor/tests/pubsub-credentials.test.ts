import { describe, it, expect, vi, beforeEach } from 'vitest';
import app from '../src/index.ts';
import type { Env } from '../src/env.d.ts';

const TEST_USER_ID = '107234567890';
const BROKER_URL = 'mqtts://broker.example.com:8883';

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

/** Creates a mock Env with all required bindings. */
function createMockEnv(): Env {
  return {
    TOKEN_CACHE: createMockKV(),
    R2_BUCKET: {} as R2Bucket,
    DB: {} as D1Database,
    PROCESSING_QUEUE: {} as Queue,
    PROCESSING_QUEUE_PRIORITY: {} as Queue,
    R2_ACCOUNT_ID: 'test-account-id',
    R2_ACCESS_KEY_ID: 'test-access-key',
    R2_SECRET_ACCESS_KEY: 'test-secret-key',
    R2_BUCKET_NAME: 'test-bucket',
    INTERNAL_SECRET: 'test-secret',
    PUBSUB_NAMESPACE: { publish: vi.fn(async () => {}) },
    PUBSUB_BROKER_URL: BROKER_URL,
  };
}

/** Stubs the Google tokeninfo endpoint to return a valid user. */
function stubValidGoogleToken(userId = TEST_USER_ID): void {
  vi.stubGlobal('fetch', vi.fn().mockResolvedValue({
    ok: true,
    json: async () => ({ sub: userId, email: 'test@example.com', exp: '9999999999' }),
  }));
}

describe('GET /v1/pubsub/credentials', () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  it('returns stable client ID ucapture-{user_sub} for authenticated user', async () => {
    const env = createMockEnv();
    stubValidGoogleToken();

    const res = await app.request('/v1/pubsub/credentials', {
      method: 'GET',
      headers: { Authorization: 'Bearer valid-token' },
    }, env);

    expect(res.status).toBe(200);
    const body = await res.json();
    expect(body.client_id).toBe(`ucapture-${TEST_USER_ID}`);
  });

  it('returns MQTT broker URL from environment', async () => {
    const env = createMockEnv();
    stubValidGoogleToken();

    const res = await app.request('/v1/pubsub/credentials', {
      method: 'GET',
      headers: { Authorization: 'Bearer valid-token' },
    }, env);

    expect(res.status).toBe(200);
    const body = await res.json();
    expect(body.broker_url).toBe(BROKER_URL);
  });

  it('returns topic pattern matching batch-completions/{user_id}', async () => {
    const env = createMockEnv();
    stubValidGoogleToken();

    const res = await app.request('/v1/pubsub/credentials', {
      method: 'GET',
      headers: { Authorization: 'Bearer valid-token' },
    }, env);

    expect(res.status).toBe(200);
    const body = await res.json();
    expect(body.topic_pattern).toBe(`batch-completions/${TEST_USER_ID}`);
  });

  it('returns session config hints with clean_session false and qos 1', async () => {
    const env = createMockEnv();
    stubValidGoogleToken();

    const res = await app.request('/v1/pubsub/credentials', {
      method: 'GET',
      headers: { Authorization: 'Bearer valid-token' },
    }, env);

    expect(res.status).toBe(200);
    const body = await res.json();
    expect(body.session_config.clean_session).toBe(false);
    expect(body.session_config.qos).toBe(1);
  });

  it('returns 401 without valid OAuth token', async () => {
    const env = createMockEnv();

    const res = await app.request('/v1/pubsub/credentials', {
      method: 'GET',
    }, env);

    expect(res.status).toBe(401);
  });
});
