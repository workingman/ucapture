import { describe, it, expect } from 'vitest';
import app from '../src/index.ts';

describe('Hono route skeleton', () => {
  it('POST /v1/upload returns 501 Not Implemented', async () => {
    const res = await app.request('/v1/upload', { method: 'POST' });
    expect(res.status).toBe(501);
    const body = await res.json();
    expect(body).toEqual({ error: 'Not implemented', code: 'NOT_IMPLEMENTED' });
  });

  it('GET /v1/status/:batch_id returns 501 Not Implemented', async () => {
    const res = await app.request('/v1/status/test-batch-123', { method: 'GET' });
    expect(res.status).toBe(501);
    const body = await res.json();
    expect(body).toEqual({ error: 'Not implemented', code: 'NOT_IMPLEMENTED' });
  });

  it('GET /v1/batches returns 501 Not Implemented', async () => {
    const res = await app.request('/v1/batches', { method: 'GET' });
    expect(res.status).toBe(501);
    const body = await res.json();
    expect(body).toEqual({ error: 'Not implemented', code: 'NOT_IMPLEMENTED' });
  });

  it('GET /v1/download/:batch_id/:artifact_type returns 501 Not Implemented', async () => {
    const res = await app.request('/v1/download/test-batch-123/raw-audio', { method: 'GET' });
    expect(res.status).toBe(501);
    const body = await res.json();
    expect(body).toEqual({ error: 'Not implemented', code: 'NOT_IMPLEMENTED' });
  });

  it('GET /unknown-route returns 404', async () => {
    const res = await app.request('/unknown-route', { method: 'GET' });
    expect(res.status).toBe(404);
  });

  it('all 501 responses have correct JSON content type', async () => {
    const res = await app.request('/v1/upload', { method: 'POST' });
    expect(res.headers.get('content-type')).toContain('application/json');
  });
});
