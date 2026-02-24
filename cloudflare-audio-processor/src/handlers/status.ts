/**
 * GET /v1/status/:batch_id handler.
 *
 * Returns full batch details including artifacts, metrics, images, and error info.
 * User-scoped: returns 403 for batches owned by other users, 404 for non-existent.
 */

import type { Context } from 'hono';
import type { Env } from '../env.d.ts';
import type { StatusResponse } from '../types/api.ts';
import type { ArtifactPaths } from '../types/batch.ts';
import type { BatchRow } from '../storage/d1.ts';
import { findBatchById, getBatchImages } from '../storage/d1.ts';
import { NotFoundError, ForbiddenError } from '../utils/errors.ts';

/**
 * Handles GET /v1/status/:batch_id requests.
 *
 * Queries the batch by ID (without user filter) to distinguish 404 from 403,
 * then joins batch_images for the images array.
 *
 * @param c - Hono context with auth variables set by middleware
 * @returns JSON response with full batch status
 */
export async function handleGetStatus(
  c: Context<{ Bindings: Env; Variables: { user_id: string; email: string } }>,
): Promise<Response> {
  const batchId = c.req.param('batch_id');
  const userId = c.get('user_id');

  const batch = await findBatchById(c.env.DB, batchId);

  if (!batch) {
    throw new NotFoundError('Batch not found');
  }

  if (batch.user_id !== userId) {
    throw new ForbiddenError('Forbidden');
  }

  const imageRows = await getBatchImages(c.env.DB, batchId);

  const artifacts = buildArtifactsMap(batch, imageRows.map((r) => r.r2_path));
  const response = buildStatusResponse(batch, artifacts);

  return c.json(response, 200);
}

/** Builds the artifacts map from batch row, omitting NULL paths. */
function buildArtifactsMap(
  batch: BatchRow,
  imagePaths: string[],
): ArtifactPaths {
  const artifacts: Record<string, unknown> = {};

  if (batch.raw_audio_path) artifacts.raw_audio = batch.raw_audio_path;
  if (batch.metadata_path) artifacts.metadata = batch.metadata_path;
  if (batch.cleaned_audio_path) artifacts.cleaned_audio = batch.cleaned_audio_path;
  if (batch.transcript_formatted_path) artifacts.transcript_formatted = batch.transcript_formatted_path;
  if (batch.transcript_raw_path) artifacts.transcript_raw = batch.transcript_raw_path;
  if (batch.transcript_emotion_path) artifacts.transcript_emotion = batch.transcript_emotion_path;

  if (imagePaths.length > 0) {
    artifacts.images = imagePaths;
  }

  return artifacts as ArtifactPaths;
}

/** Builds a full StatusResponse from the batch row and assembled artifacts. */
function buildStatusResponse(
  batch: BatchRow,
  artifacts: ArtifactPaths,
): StatusResponse {
  return {
    batch_id: batch.id,
    user_id: batch.user_id,
    status: batch.status as StatusResponse['status'],
    priority: batch.priority as StatusResponse['priority'],
    artifacts,
    recording_started_at: batch.recording_started_at,
    recording_ended_at: batch.recording_ended_at,
    recording_duration_seconds: batch.recording_duration_seconds,
    uploaded_at: batch.uploaded_at,
    processing_started_at: batch.processing_started_at,
    processing_completed_at: batch.processing_completed_at,
    processing_wall_time_seconds: batch.processing_wall_time_seconds,
    queue_wait_time_seconds: batch.queue_wait_time_seconds,
    raw_audio_size_bytes: batch.raw_audio_size_bytes,
    raw_audio_duration_seconds: batch.raw_audio_duration_seconds,
    speech_duration_seconds: batch.speech_duration_seconds,
    speech_ratio: batch.speech_ratio,
    retry_count: batch.retry_count,
    error_message: batch.error_message,
    error_stage: batch.error_stage,
  };
}
