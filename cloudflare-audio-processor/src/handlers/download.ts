/**
 * GET /v1/download/:batch_id/:artifact_type handler.
 *
 * Validates the artifact type, checks batch ownership, and redirects
 * to a presigned R2 URL for the requested artifact.
 */

import type { Context } from 'hono';
import type { Env } from '../env.d.ts';
import type { BatchRow } from '../storage/d1.ts';
import { findBatchById } from '../storage/d1.ts';
import { generatePresignedUrl } from '../storage/r2.ts';
import type { R2PresignConfig } from '../storage/r2.ts';
import {
  NotFoundError,
  ForbiddenError,
  ValidationError,
} from '../utils/errors.ts';

/** Valid artifact types for download and their corresponding D1 column names. */
const ARTIFACT_TYPE_COLUMNS: Record<string, keyof BatchRow> = {
  raw_audio: 'raw_audio_path',
  cleaned_audio: 'cleaned_audio_path',
  transcript_formatted: 'transcript_formatted_path',
  transcript_raw: 'transcript_raw_path',
  metadata: 'metadata_path',
};

/** All valid download artifact types. */
const VALID_ARTIFACT_TYPES = Object.keys(ARTIFACT_TYPE_COLUMNS);

/**
 * Handles GET /v1/download/:batch_id/:artifact_type requests.
 *
 * Validates the artifact type, fetches the batch, checks ownership,
 * verifies the artifact path exists, generates a presigned URL,
 * and returns a 302 redirect.
 *
 * @param c - Hono context with auth variables set by middleware
 * @returns 302 redirect to presigned R2 URL
 */
export async function handleGetDownload(
  c: Context<{ Bindings: Env; Variables: { user_id: string; email: string } }>,
): Promise<Response> {
  const batchId = c.req.param('batch_id');
  const artifactType = c.req.param('artifact_type');
  const userId = c.get('user_id');

  if (!VALID_ARTIFACT_TYPES.includes(artifactType)) {
    throw new ValidationError(
      `Invalid artifact type: "${artifactType}". Must be one of: ${VALID_ARTIFACT_TYPES.join(', ')}`,
    );
  }

  const batch = await findBatchById(c.env.DB, batchId);

  if (!batch) {
    throw new NotFoundError('Batch not found');
  }

  if (batch.user_id !== userId) {
    throw new ForbiddenError('Forbidden');
  }

  const column = ARTIFACT_TYPE_COLUMNS[artifactType];
  const r2Path = batch[column] as string | null;

  if (!r2Path) {
    throw new NotFoundError('Artifact not available');
  }

  const config: R2PresignConfig = {
    accountId: c.env.R2_ACCOUNT_ID,
    accessKeyId: c.env.R2_ACCESS_KEY_ID,
    secretAccessKey: c.env.R2_SECRET_ACCESS_KEY,
    bucketName: c.env.R2_BUCKET_NAME,
  };

  const presignedUrl = await generatePresignedUrl(config, r2Path);

  return c.redirect(presignedUrl, 302);
}
