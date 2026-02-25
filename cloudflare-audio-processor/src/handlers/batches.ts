/**
 * GET /v1/batches handler.
 *
 * Returns a paginated, filterable list of batches for the authenticated user.
 * Supports filtering by status and date range, with configurable limit/offset.
 */

import type { Context } from 'hono';
import type { Env } from '../env.d.ts';
import type { BatchListResponse, Pagination } from '../types/api.ts';
import { listBatches, countBatches } from '../storage/d1.ts';
import type { ListBatchesFilter, BatchRow } from '../storage/d1.ts';
import type { StatusResponse } from '../types/api.ts';
import type { ArtifactPaths } from '../types/batch.ts';
import { BatchListQuerySchema } from '../utils/validation.ts';
import { ValidationError } from '../utils/errors.ts';

/**
 * Handles GET /v1/batches requests.
 *
 * Validates query parameters, builds a dynamic filter, and returns
 * a paginated list of batch summaries with pagination metadata.
 *
 * @param c - Hono context with auth variables set by middleware
 * @returns JSON response with batch list and pagination
 */
export async function handleGetBatches(
  c: Context<{ Bindings: Env; Variables: { user_id: string; email: string } }>,
): Promise<Response> {
  const userId = c.get('user_id');
  const rawQuery = extractQueryParams(c);

  const parseResult = BatchListQuerySchema.safeParse(rawQuery);
  if (!parseResult.success) {
    const details = parseResult.error.issues
      .map((issue) => `${issue.path.join('.')}: ${issue.message}`)
      .join('; ');
    throw new ValidationError('Invalid query parameters', details);
  }

  const query = parseResult.data;

  const filter: ListBatchesFilter = {
    userId,
    status: query.status,
    startDate: query.start_date,
    endDate: query.end_date,
    limit: query.limit,
    offset: query.offset,
  };

  const [batches, total] = await Promise.all([
    listBatches(c.env.DB, filter),
    countBatches(c.env.DB, filter),
  ]);

  const pagination: Pagination = {
    limit: query.limit,
    offset: query.offset,
    total,
  };

  const response: BatchListResponse = {
    batches: batches.map(batchRowToSummary),
    pagination,
  };

  return c.json(response, 200);
}

/** Extracts query parameters from the Hono context as a plain object. */
function extractQueryParams(
  c: Context<{ Bindings: Env; Variables: { user_id: string; email: string } }>,
): Record<string, string> {
  const params: Record<string, string> = {};
  const url = new URL(c.req.url);

  for (const [key, value] of url.searchParams.entries()) {
    params[key] = value;
  }

  return params;
}

/** Converts a BatchRow to a StatusResponse summary (without images). */
function batchRowToSummary(row: BatchRow): StatusResponse {
  const artifacts = buildArtifactsMap(row);

  return {
    batch_id: row.id,
    user_id: row.user_id,
    status: row.status as StatusResponse['status'],
    priority: row.priority as StatusResponse['priority'],
    artifacts,
    recording_started_at: row.recording_started_at,
    recording_ended_at: row.recording_ended_at,
    recording_duration_seconds: row.recording_duration_seconds,
    uploaded_at: row.uploaded_at,
    processing_started_at: row.processing_started_at,
    processing_completed_at: row.processing_completed_at,
    processing_wall_time_seconds: row.processing_wall_time_seconds,
    queue_wait_time_seconds: row.queue_wait_time_seconds,
    raw_audio_size_bytes: row.raw_audio_size_bytes,
    raw_audio_duration_seconds: row.raw_audio_duration_seconds,
    metrics: {
      speech_duration_seconds: row.speech_duration_seconds,
      speech_ratio: row.speech_ratio,
      speechmatics_cost_estimate: row.speechmatics_cost_estimate,
    },
    retry_count: row.retry_count,
    error_message: row.error_message,
    error_stage: row.error_stage,
  };
}

/** Builds the artifacts map from a batch row, omitting NULL paths. */
function buildArtifactsMap(row: BatchRow): ArtifactPaths {
  const artifacts: Record<string, unknown> = {};

  if (row.raw_audio_path) artifacts.raw_audio = row.raw_audio_path;
  if (row.metadata_path) artifacts.metadata = row.metadata_path;
  if (row.cleaned_audio_path) artifacts.cleaned_audio = row.cleaned_audio_path;
  if (row.transcript_formatted_path) artifacts.transcript_formatted = row.transcript_formatted_path;
  if (row.transcript_raw_path) artifacts.transcript_raw = row.transcript_raw_path;
  if (row.transcript_emotion_path) artifacts.transcript_emotion = row.transcript_emotion_path;

  return artifacts as ArtifactPaths;
}
