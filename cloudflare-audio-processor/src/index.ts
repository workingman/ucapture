import { Hono } from 'hono';
import type { Env } from './env.d.ts';
import { authMiddleware } from './auth/middleware.ts';
import { parseUpload, storeArtifacts } from './handlers/upload.ts';
import { createBatch, insertBatchImages, insertBatchNotes } from './storage/d1.ts';
import { enqueueProcessingJob, buildProcessingJob } from './queue/publisher.ts';
import type { UploadResponse } from './types/api.ts';
import type { BatchImageInput, BatchNoteInput } from './storage/d1.ts';

const app = new Hono<{ Bindings: Env; Variables: { user_id: string; email: string } }>();

/** Apply auth middleware to all /v1/* routes. */
app.use('/v1/*', authMiddleware);

/** POST /v1/upload -- multipart upload (audio + metadata + images + notes) */
app.post('/v1/upload', async (c) => {
  const userId = c.get('user_id');

  // Phase 1: Parse and validate multipart form data
  const parsed = await parseUpload(c);

  // Phase 2: Store artifacts in R2
  const stored = await storeArtifacts(c.env.R2_BUCKET, userId, parsed);

  // Phase 3: Create D1 batch record
  await createBatch(c.env.DB, {
    id: stored.batchId,
    user_id: userId,
    status: 'uploaded',
    priority: parsed.priority,
    raw_audio_path: stored.audioPath,
    metadata_path: stored.metadataPath,
    recording_started_at: parsed.metadata.recording.started_at,
    recording_ended_at: parsed.metadata.recording.ended_at,
    recording_duration_seconds: parsed.metadata.recording.duration_seconds,
    raw_audio_size_bytes: parsed.metadata.recording.file_size_bytes,
  });

  // Phase 3b: Insert images into D1 if present
  if (stored.imagePaths.length > 0 && parsed.metadata.images) {
    const imageInputs: BatchImageInput[] = parsed.metadata.images.map((img, i) => ({
      r2_path: stored.imagePaths[i],
      captured_at: img.captured_at,
      size_bytes: img.size_bytes,
    }));
    await insertBatchImages(c.env.DB, stored.batchId, imageInputs);
  }

  // Phase 3c: Insert notes into D1 if present
  if (parsed.metadata.notes && parsed.metadata.notes.length > 0) {
    const noteInputs: BatchNoteInput[] = parsed.metadata.notes.map((note) => ({
      note_text: note.text,
      created_at: note.created_at,
    }));
    await insertBatchNotes(c.env.DB, stored.batchId, noteInputs);
  }

  // Phase 4: Enqueue processing job
  const job = buildProcessingJob(stored.batchId, userId, parsed.priority);
  await enqueueProcessingJob(
    c.env.PROCESSING_QUEUE,
    c.env.PROCESSING_QUEUE_PRIORITY,
    job,
  );

  // Phase 5: Return 202 Accepted
  const response: UploadResponse = {
    batch_id: stored.batchId,
    status: 'uploaded',
    uploaded_at: new Date().toISOString(),
  };

  return c.json(response, 202);
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
