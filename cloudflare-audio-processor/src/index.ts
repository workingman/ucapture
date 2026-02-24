import { Hono } from 'hono';
import type { Env } from './env.d.ts';
import { authMiddleware } from './auth/middleware.ts';

const app = new Hono<{ Bindings: Env; Variables: { user_id: string; email: string } }>();

/** Apply auth middleware to all /v1/* routes. */
app.use('/v1/*', authMiddleware);

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
