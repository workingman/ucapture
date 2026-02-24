import { Hono } from 'hono';
import type { Env } from './env.d.ts';
import { authMiddleware } from './auth/middleware.ts';
import { parseUpload, storeArtifacts, MAX_TOTAL_PAYLOAD_BYTES } from './handlers/upload.ts';
import type { StoredArtifacts } from './handlers/upload.ts';
import { createBatch, insertBatchImages, insertBatchNotes } from './storage/d1.ts';
import { enqueueProcessingJob, buildProcessingJob } from './queue/publisher.ts';
import type { UploadResponse } from './types/api.ts';
import type { BatchImageInput, BatchNoteInput } from './storage/d1.ts';
import { AppError, PayloadTooLargeError } from './utils/errors.ts';
import { handleGetStatus } from './handlers/status.ts';
import { handleGetBatches } from './handlers/batches.ts';

const app = new Hono<{ Bindings: Env; Variables: { user_id: string; email: string } }>();

/** Apply auth middleware to all /v1/* routes. */
app.use('/v1/*', authMiddleware);

/** POST /v1/upload -- multipart upload (audio + metadata + images + notes) */
app.post('/v1/upload', async (c) => {
  const userId = c.get('user_id');

  // Early Content-Length check for 413 before parsing body
  const contentLength = c.req.header('Content-Length');
  if (contentLength && parseInt(contentLength, 10) > MAX_TOTAL_PAYLOAD_BYTES) {
    throw new PayloadTooLargeError('Total payload exceeds 100MB limit');
  }

  // Phase 1: Parse and validate multipart form data
  const parsed = await parseUpload(c);

  // Phase 2: Store artifacts in R2
  const stored = await storeArtifacts(c.env.R2_BUCKET, userId, parsed);

  // Phase 3: Create D1 batch record (may orphan R2 artifacts on failure)
  try {
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
  } catch (error) {
    // FR-042: NEVER delete R2 objects on failure -- log orphaned artifacts for reconciliation
    logOrphanedR2Artifacts(stored, error);
    throw error;
  }

  // Phase 4: Enqueue processing job (may leave batch unqueued on failure)
  try {
    const job = buildProcessingJob(stored.batchId, userId, parsed.priority);
    await enqueueProcessingJob(
      c.env.PROCESSING_QUEUE,
      c.env.PROCESSING_QUEUE_PRIORITY,
      job,
    );
  } catch (error) {
    logUnqueuedBatch(stored.batchId, error);
    throw error;
  }

  // Phase 5: Return 202 Accepted
  const response: UploadResponse = {
    batch_id: stored.batchId,
    status: 'uploaded',
    uploaded_at: new Date().toISOString(),
  };

  return c.json(response, 202);
});

/**
 * Hono error handler -- catches all uncaught errors and returns structured JSON.
 *
 * AppError subclasses get their specific status code and toJSON().
 * Unknown errors become 500 with a generic message.
 */
app.onError((error, c) => {
  if (error instanceof AppError) {
    return c.json(error.toJSON(), error.statusCode as 400);
  }
  console.error(JSON.stringify({
    event: 'unhandled_error',
    message: error instanceof Error ? error.message : String(error),
  }));
  return c.json({ error: 'Internal server error' }, 500);
});

/** GET /v1/status/:batch_id -- batch status query (user-scoped) */
app.get('/v1/status/:batch_id', handleGetStatus);

/** GET /v1/batches -- list batches (paginated, filterable) */
app.get('/v1/batches', handleGetBatches);

/** GET /v1/download/:batch_id/:artifact_type -- presigned R2 URL redirect */
app.get('/v1/download/:batch_id/:artifact_type', (c) => {
  return c.json({ error: 'Not implemented', code: 'NOT_IMPLEMENTED' }, 501);
});

/** Logs R2 artifact paths that are now orphaned after a D1 failure. */
function logOrphanedR2Artifacts(stored: StoredArtifacts, error: unknown): void {
  const r2Paths = [stored.audioPath, stored.metadataPath, ...stored.imagePaths];
  if (stored.notesPath) {
    r2Paths.push(stored.notesPath);
  }
  console.error(JSON.stringify({
    event: 'orphaned_r2_artifacts',
    batch_id: stored.batchId,
    r2_paths: r2Paths,
    error: error instanceof Error ? error.message : String(error),
  }));
}

/** Logs a batch ID that was saved to D1 but could not be enqueued. */
function logUnqueuedBatch(batchId: string, error: unknown): void {
  console.error(JSON.stringify({
    event: 'unqueued_batch',
    batch_id: batchId,
    error: error instanceof Error ? error.message : String(error),
  }));
}

export default app;
