/**
 * POST /internal/reprocess/:batch_id handler.
 *
 * Re-enqueues a failed batch for reprocessing. Validates the batch is in "failed"
 * state and that raw audio still exists in R2 before resetting status and re-enqueuing.
 * Authenticated via X-Internal-Secret header (not OAuth).
 */

import type { Context } from 'hono';
import type { Env } from '../../env.d.ts';
import type { BatchPriority } from '../../types/batch.ts';
import { findBatchById, updateBatchStatus } from '../../storage/d1.ts';
import { enqueueProcessingJob, buildProcessingJob } from '../../queue/publisher.ts';

/**
 * Handles POST /internal/reprocess/:batch_id requests.
 *
 * 1. Verifies X-Internal-Secret header
 * 2. Loads batch from D1 (no user scoping for internal endpoint)
 * 3. Validates batch is in "failed" state (409 if not)
 * 4. Validates raw audio exists in R2 (404 if missing)
 * 5. Resets batch status to "uploaded", clears error fields, resets retry_count
 * 6. Re-enqueues the processing job
 *
 * @param c - Hono context with Worker env bindings
 * @returns JSON response with reprocess result
 */
export async function handleReprocess(
  c: Context<{ Bindings: Env }>,
): Promise<Response> {
  const secret = c.req.header('X-Internal-Secret');

  if (!secret || secret !== c.env.INTERNAL_SECRET) {
    return c.json({ error: 'Forbidden' }, 403);
  }

  const batchId = c.req.param('batch_id');

  const batch = await findBatchById(c.env.DB, batchId);

  if (!batch) {
    return c.json({ error: 'Batch not found' }, 404);
  }

  if (batch.status !== 'failed') {
    return c.json({ error: `Batch is in "${batch.status}" state, only "failed" batches can be reprocessed` }, 409);
  }

  if (!batch.raw_audio_path) {
    return c.json({ error: 'Raw audio path not found in batch record' }, 404);
  }

  // Verify raw audio still exists in R2
  const r2Head = await c.env.R2_BUCKET.head(batch.raw_audio_path);

  if (!r2Head) {
    return c.json({ error: 'Raw audio file not found in storage' }, 404);
  }

  // Reset batch status and clear error fields
  await updateBatchStatus(c.env.DB, batchId, 'uploaded', {
    retry_count: 0,
    error_message: '',
    error_stage: '',
  });

  // Re-enqueue the processing job
  const job = buildProcessingJob(
    batchId,
    batch.user_id,
    batch.priority as BatchPriority,
  );

  await enqueueProcessingJob(
    c.env.PROCESSING_QUEUE,
    c.env.PROCESSING_QUEUE_PRIORITY,
    job,
  );

  return c.json({
    batch_id: batchId,
    status: 'uploaded',
    requeued_at: job.enqueued_at,
  }, 200);
}
