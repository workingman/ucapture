import { describe, it, expect, vi, beforeEach } from 'vitest';
import { Hono } from 'hono';
import type { Env } from '../src/env.d.ts';
import { parseUpload } from '../src/handlers/upload.ts';

/** Valid metadata JSON matching MetadataSchema. */
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

/** Creates a mock Env for upload testing. */
function createMockEnv(): Env {
  return {
    TOKEN_CACHE: {} as KVNamespace,
    R2_BUCKET: {} as R2Bucket,
    DB: {} as D1Database,
    PROCESSING_QUEUE: {} as Queue,
    PROCESSING_QUEUE_PRIORITY: {} as Queue,
  };
}

/** Creates a Hono app with a test route that calls parseUpload. */
function createTestApp(): Hono<{ Bindings: Env; Variables: { user_id: string; email: string } }> {
  const app = new Hono<{ Bindings: Env; Variables: { user_id: string; email: string } }>();

  app.use('*', async (c, next) => {
    c.set('user_id', '107234567890');
    c.set('email', 'test@example.com');
    await next();
  });

  app.post('/v1/upload', async (c) => {
    const parsed = await parseUpload(c);
    return c.json({
      audioName: parsed.audio.name,
      audioSize: parsed.audio.size,
      metadataValid: !!parsed.metadata.recording,
      imageCount: parsed.images.length,
      priority: parsed.priority,
    });
  });

  return app;
}

/** Builds a multipart FormData with valid fields. */
function buildFormData(overrides: {
  audio?: File | null;
  metadata?: File | null;
  images?: File[];
  priority?: string;
  skipAudio?: boolean;
  skipMetadata?: boolean;
} = {}): FormData {
  const form = new FormData();

  if (!overrides.skipAudio) {
    const audio = overrides.audio ?? new File(['audio-content'], 'recording.m4a', { type: 'audio/mp4' });
    form.append('audio', audio);
  }

  if (!overrides.skipMetadata) {
    const metadataContent = JSON.stringify(VALID_METADATA);
    const metadata = overrides.metadata ?? new File([metadataContent], 'metadata.json', { type: 'application/json' });
    form.append('metadata', metadata);
  }

  if (overrides.images) {
    for (const img of overrides.images) {
      form.append('images', img);
    }
  }

  if (overrides.priority !== undefined) {
    form.append('priority', overrides.priority);
  }

  return form;
}

describe('parseUpload', () => {
  let app: ReturnType<typeof createTestApp>;
  let env: Env;

  beforeEach(() => {
    vi.restoreAllMocks();
    app = createTestApp();
    env = createMockEnv();
  });

  it('parses valid upload with audio and metadata', async () => {
    const form = buildFormData();

    const res = await app.request('/v1/upload', {
      method: 'POST',
      body: form,
    }, env);

    expect(res.status).toBe(200);
    const body = await res.json();
    expect(body.audioName).toBe('recording.m4a');
    expect(body.metadataValid).toBe(true);
    expect(body.imageCount).toBe(0);
    expect(body.priority).toBe('normal');
  });

  it('returns 400 when audio is missing', async () => {
    const errorApp = new Hono<{ Bindings: Env; Variables: { user_id: string; email: string } }>();
    errorApp.use('*', async (c, next) => {
      c.set('user_id', '107234567890');
      c.set('email', 'test@example.com');
      await next();
    });
    errorApp.post('/v1/upload', async (c) => {
      try {
        const parsed = await parseUpload(c);
        return c.json({ ok: true });
      } catch (err: unknown) {
        const error = err as { statusCode: number; message: string };
        return c.json({ error: error.message }, error.statusCode);
      }
    });

    const form = buildFormData({ skipAudio: true });

    const res = await errorApp.request('/v1/upload', {
      method: 'POST',
      body: form,
    }, env);

    expect(res.status).toBe(400);
    const body = await res.json();
    expect(body.error).toBe('Missing required field: audio');
  });

  it('returns 400 when metadata is missing', async () => {
    const errorApp = new Hono<{ Bindings: Env; Variables: { user_id: string; email: string } }>();
    errorApp.use('*', async (c, next) => {
      c.set('user_id', '107234567890');
      c.set('email', 'test@example.com');
      await next();
    });
    errorApp.post('/v1/upload', async (c) => {
      try {
        const parsed = await parseUpload(c);
        return c.json({ ok: true });
      } catch (err: unknown) {
        const error = err as { statusCode: number; message: string };
        return c.json({ error: error.message }, error.statusCode);
      }
    });

    const form = buildFormData({ skipMetadata: true });

    const res = await errorApp.request('/v1/upload', {
      method: 'POST',
      body: form,
    }, env);

    expect(res.status).toBe(400);
    const body = await res.json();
    expect(body.error).toBe('Missing required field: metadata');
  });

  it('returns 400 when metadata JSON is invalid', async () => {
    const errorApp = new Hono<{ Bindings: Env; Variables: { user_id: string; email: string } }>();
    errorApp.use('*', async (c, next) => {
      c.set('user_id', '107234567890');
      c.set('email', 'test@example.com');
      await next();
    });
    errorApp.post('/v1/upload', async (c) => {
      try {
        const parsed = await parseUpload(c);
        return c.json({ ok: true });
      } catch (err: unknown) {
        const error = err as { statusCode: number; message: string; details?: string };
        return c.json({ error: error.message, ...(error.details ? { details: error.details } : {}) }, error.statusCode);
      }
    });

    const invalidMetadata = new File(['{ invalid json'], 'metadata.json', { type: 'application/json' });
    const form = buildFormData({ metadata: invalidMetadata });

    const res = await errorApp.request('/v1/upload', {
      method: 'POST',
      body: form,
    }, env);

    expect(res.status).toBe(400);
    const body = await res.json();
    expect(body.error).toBe('Invalid metadata: not valid JSON');
  });

  it('returns 400 when metadata fails Zod validation', async () => {
    const errorApp = new Hono<{ Bindings: Env; Variables: { user_id: string; email: string } }>();
    errorApp.use('*', async (c, next) => {
      c.set('user_id', '107234567890');
      c.set('email', 'test@example.com');
      await next();
    });
    errorApp.post('/v1/upload', async (c) => {
      try {
        const parsed = await parseUpload(c);
        return c.json({ ok: true });
      } catch (err: unknown) {
        const error = err as { statusCode: number; message: string; details?: string };
        return c.json({ error: error.message, ...(error.details ? { details: error.details } : {}) }, error.statusCode);
      }
    });

    const incompleteMetadata = new File([JSON.stringify({ recording: {} })], 'metadata.json', { type: 'application/json' });
    const form = buildFormData({ metadata: incompleteMetadata });

    const res = await errorApp.request('/v1/upload', {
      method: 'POST',
      body: form,
    }, env);

    expect(res.status).toBe(400);
    const body = await res.json();
    expect(body.error).toBe('Invalid metadata');
    expect(body.details).toBeDefined();
  });

  it('returns 400 when more than 10 images are uploaded', async () => {
    const errorApp = new Hono<{ Bindings: Env; Variables: { user_id: string; email: string } }>();
    errorApp.use('*', async (c, next) => {
      c.set('user_id', '107234567890');
      c.set('email', 'test@example.com');
      await next();
    });
    errorApp.post('/v1/upload', async (c) => {
      try {
        const parsed = await parseUpload(c);
        return c.json({ ok: true });
      } catch (err: unknown) {
        const error = err as { statusCode: number; message: string };
        return c.json({ error: error.message }, error.statusCode);
      }
    });

    const images = Array.from({ length: 11 }, (_, i) =>
      new File(['img'], `photo-${i}.jpg`, { type: 'image/jpeg' }),
    );
    const form = buildFormData({ images });

    const res = await errorApp.request('/v1/upload', {
      method: 'POST',
      body: form,
    }, env);

    expect(res.status).toBe(400);
    const body = await res.json();
    expect(body.error).toContain('Too many images');
  });
});
