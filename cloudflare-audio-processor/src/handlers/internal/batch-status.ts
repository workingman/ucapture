/**
 * POST /internal/batch-status handler.
 *
 * Receives batch status and metrics updates from GCP and writes them to D1.
 * Authenticated via X-Internal-Secret header (not OAuth).
 */

import type { Context } from 'hono';
import type { Env } from '../../env.d.ts';
import type { UpdateBatchFields } from '../../storage/d1.ts';
import { updateBatchStatus } from '../../storage/d1.ts';

/** Map from GCP artifact_paths keys to D1 column names. */
const ARTIFACT_COLUMN_MAP: Record<string, keyof UpdateBatchFields> = {
  cleaned_audio: 'cleaned_audio_path',
  transcript_formatted: 'transcript_formatted_path',
  transcript_raw: 'transcript_raw_path',
  transcript_emotion: 'transcript_emotion_path',
};

/** Fields that map directly from payload to UpdateBatchFields. */
const PASSTHROUGH_FIELDS: (keyof UpdateBatchFields)[] = [
  'processing_started_at',
  'processing_completed_at',
  'processing_wall_time_seconds',
  'queue_wait_time_seconds',
  'speech_duration_seconds',
  'speech_ratio',
  'cleaned_audio_size_bytes',
  'speechmatics_job_id',
  'speechmatics_cost_estimate',
  'emotion_provider',
  'emotion_analyzed_at',
  'retry_count',
  'error_message',
  'error_stage',
];

/**
 * Handles POST /internal/batch-status requests.
 *
 * Verifies X-Internal-Secret header, validates the payload, and updates
 * the batch record in D1 with status and optional metric fields.
 *
 * @param c - Hono context with Worker env bindings
 * @returns JSON response indicating success or error
 */
export async function handleBatchStatus(
  c: Context<{ Bindings: Env }>,
): Promise<Response> {
  const secret = c.req.header('X-Internal-Secret');

  if (!secret || secret !== c.env.INTERNAL_SECRET) {
    return c.json({ error: 'Forbidden' }, 403);
  }

  let body: Record<string, unknown>;
  try {
    body = await c.req.json();
  } catch {
    return c.json({ error: 'Invalid JSON body' }, 400);
  }

  const batchId = body.batch_id;
  const status = body.status;

  if (typeof batchId !== 'string' || batchId.length === 0) {
    return c.json({ error: 'Missing or invalid batch_id' }, 400);
  }

  if (typeof status !== 'string' || status.length === 0) {
    return c.json({ error: 'Missing or invalid status' }, 400);
  }

  const fields: UpdateBatchFields = {};

  // Map artifact_paths to individual D1 columns
  if (body.artifact_paths && typeof body.artifact_paths === 'object') {
    const paths = body.artifact_paths as Record<string, string>;
    for (const [key, column] of Object.entries(ARTIFACT_COLUMN_MAP)) {
      if (typeof paths[key] === 'string') {
        (fields as Record<string, unknown>)[column] = paths[key];
      }
    }
  }

  // Copy passthrough fields
  for (const field of PASSTHROUGH_FIELDS) {
    if (body[field] !== undefined && body[field] !== null) {
      (fields as Record<string, unknown>)[field] = body[field];
    }
  }

  // Map raw_audio_duration_seconds and raw_audio_size_bytes (not in UpdateBatchFields
  // but they exist as D1 columns on the batches table, handled via updateBatchStatus)
  if (body.raw_audio_duration_seconds !== undefined) {
    (fields as Record<string, unknown>)['raw_audio_duration_seconds'] = body.raw_audio_duration_seconds;
  }
  if (body.raw_audio_size_bytes !== undefined) {
    (fields as Record<string, unknown>)['raw_audio_size_bytes'] = body.raw_audio_size_bytes;
  }

  await updateBatchStatus(c.env.DB, batchId, status, fields);

  return c.json({ success: true }, 200);
}
