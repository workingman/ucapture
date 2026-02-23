import { Hono } from 'hono';
import type { Env } from './env.d.ts';

const app = new Hono<{ Bindings: Env }>();

/** POST /v1/upload -- multipart upload (audio + metadata + images + notes) */
app.post('/v1/upload', (c) => {
  return c.json({ error: 'Not implemented', code: 'NOT_IMPLEMENTED' }, 501);
});

/** GET /v1/status/:batch_id -- batch status query (user-scoped) */
app.get('/v1/status/:batch_id', (c) => {
  return c.json({ error: 'Not implemented', code: 'NOT_IMPLEMENTED' }, 501);
});

/** GET /v1/batches -- list batches (paginated, filterable) */
app.get('/v1/batches', (c) => {
  return c.json({ error: 'Not implemented', code: 'NOT_IMPLEMENTED' }, 501);
});

/** GET /v1/download/:batch_id/:artifact_type -- presigned R2 URL redirect */
app.get('/v1/download/:batch_id/:artifact_type', (c) => {
  return c.json({ error: 'Not implemented', code: 'NOT_IMPLEMENTED' }, 501);
});

export default app;
