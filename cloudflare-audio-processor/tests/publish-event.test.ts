import { describe, it, expect, vi, beforeEach } from 'vitest';
import app from '../src/index.ts';
import type { Env } from '../src/env.d.ts';
import type { CompletionEvent } from '../src/types/events.ts';

const INTERNAL_SECRET = 'test-internal-secret-abc123';

/** Creates a valid CompletionEvent fixture. */
function makeCompletionEvent(overrides?: Partial<CompletionEvent>): CompletionEvent {
  return {
    batch_id: '20260222-143027-GMT-a1b2c3d4-e5f6-7890-abcd-ef1234567890',
    user_id: '107234567890',
    status: 'completed',
    recording_started_at: '2026-02-22T14:30:27Z',
    artifact_paths: {
      raw_audio: '107234567890/batch-id/raw-audio/recording.m4a',
      cleaned_audio: '107234567890/batch-id/cleaned-audio/cleaned.wav',
      transcript_formatted: '107234567890/batch-id/transcript/formatted.json',
      transcript_raw: '107234567890/batch-id/transcript/raw.json',
    },
    published_at: '2026-02-22T14:45:00Z',
    ...overrides,
  };
}

/** Creates a mock Env with Pub/Sub namespace and internal secret. */
function createMockEnv(): Env {
  return {
    TOKEN_CACHE: {
      get: vi.fn(async () => null),
      put: vi.fn(),
      delete: vi.fn(),
      list: vi.fn(),
      getWithMetadata: vi.fn(),
    } as unknown as KVNamespace,
    R2_BUCKET: {} as R2Bucket,
    DB: {} as D1Database,
    PROCESSING_QUEUE: {} as Queue,
    PROCESSING_QUEUE_PRIORITY: {} as Queue,
    R2_ACCOUNT_ID: 'test-account-id',
    R2_ACCESS_KEY_ID: 'test-access-key',
    R2_SECRET_ACCESS_KEY: 'test-secret-key',
    R2_BUCKET_NAME: 'test-bucket',
    INTERNAL_SECRET,
    PUBSUB_NAMESPACE: {
      publish: vi.fn(async () => {}),
    },
    PUBSUB_BROKER_URL: 'mqtts://broker.example.com:8883',
  };
}

describe('POST /internal/publish-event', () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  it('publishes a completed event to the correct user-scoped topic', async () => {
    const env = createMockEnv();
    const event = makeCompletionEvent();

    const res = await app.request('/internal/publish-event', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'X-Internal-Secret': INTERNAL_SECRET,
      },
      body: JSON.stringify(event),
    }, env);

    expect(res.status).toBe(200);
    const body = await res.json();
    expect(body.success).toBe(true);

    expect(env.PUBSUB_NAMESPACE.publish).toHaveBeenCalledOnce();
    expect(env.PUBSUB_NAMESPACE.publish).toHaveBeenCalledWith(
      `batch-completions/${event.user_id}`,
      JSON.stringify(event),
    );
  });

  it('publishes a failed event with error_message in payload', async () => {
    const env = createMockEnv();
    const event = makeCompletionEvent({
      status: 'failed',
      error_message: 'Speechmatics API timeout at transcription stage',
    });

    const res = await app.request('/internal/publish-event', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'X-Internal-Secret': INTERNAL_SECRET,
      },
      body: JSON.stringify(event),
    }, env);

    expect(res.status).toBe(200);

    const publishedPayload = JSON.parse(
      (env.PUBSUB_NAMESPACE.publish as ReturnType<typeof vi.fn>).mock.calls[0][1],
    );
    expect(publishedPayload.status).toBe('failed');
    expect(publishedPayload.error_message).toBe('Speechmatics API timeout at transcription stage');
  });

  it('returns 403 when X-Internal-Secret header is missing', async () => {
    const env = createMockEnv();
    const event = makeCompletionEvent();

    const res = await app.request('/internal/publish-event', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(event),
    }, env);

    expect(res.status).toBe(403);
    const body = await res.json();
    expect(body.error).toBe('Forbidden');
    expect(env.PUBSUB_NAMESPACE.publish).not.toHaveBeenCalled();
  });

  it('returns 403 when X-Internal-Secret header has wrong value', async () => {
    const env = createMockEnv();
    const event = makeCompletionEvent();

    const res = await app.request('/internal/publish-event', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'X-Internal-Secret': 'wrong-secret',
      },
      body: JSON.stringify(event),
    }, env);

    expect(res.status).toBe(403);
    const body = await res.json();
    expect(body.error).toBe('Forbidden');
    expect(env.PUBSUB_NAMESPACE.publish).not.toHaveBeenCalled();
  });

  it('returns 400 for invalid JSON body', async () => {
    const env = createMockEnv();

    const res = await app.request('/internal/publish-event', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'X-Internal-Secret': INTERNAL_SECRET,
      },
      body: 'not-valid-json{{{',
    }, env);

    expect(res.status).toBe(400);
    const body = await res.json();
    expect(body.error).toBe('Invalid JSON body');
  });

  it('returns 400 when required fields are missing', async () => {
    const env = createMockEnv();
    const incomplete = { batch_id: 'some-id' };

    const res = await app.request('/internal/publish-event', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'X-Internal-Secret': INTERNAL_SECRET,
      },
      body: JSON.stringify(incomplete),
    }, env);

    expect(res.status).toBe(400);
    const body = await res.json();
    expect(body.error).toBe('Invalid completion event payload');
    expect(env.PUBSUB_NAMESPACE.publish).not.toHaveBeenCalled();
  });

  it('returns 400 when status is invalid', async () => {
    const env = createMockEnv();
    const event = makeCompletionEvent();
    const badEvent = { ...event, status: 'in-progress' };

    const res = await app.request('/internal/publish-event', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'X-Internal-Secret': INTERNAL_SECRET,
      },
      body: JSON.stringify(badEvent),
    }, env);

    expect(res.status).toBe(400);
    const body = await res.json();
    expect(body.error).toBe('Invalid completion event payload');
  });

  it('returns 400 when failed event is missing error_message', async () => {
    const env = createMockEnv();
    const event = makeCompletionEvent({ status: 'failed' });
    // Remove error_message for this test
    const { error_message, ...eventWithoutError } = event as CompletionEvent & { error_message?: string };

    const res = await app.request('/internal/publish-event', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'X-Internal-Secret': INTERNAL_SECRET,
      },
      body: JSON.stringify(eventWithoutError),
    }, env);

    expect(res.status).toBe(400);
    const body = await res.json();
    expect(body.error).toBe('Invalid completion event payload');
  });
});
