/**
 * GET /v1/batches handler.
 *
 * Returns a paginated, filterable list of batches for the authenticated user.
 * Supports filtering by status and date range, with configurable limit/offset.
 */

import type { Context } from 'hono';
import type { Env } from '../env.d.ts';
import type { BatchListResponse, BatchSummary, Pagination } from '../types/api.ts';
import { listBatches, countBatches } from '../storage/d1.ts';
import type { ListBatchesFilter, BatchRow } from '../storage/d1.ts';
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

/** Converts a BatchRow to a lightweight BatchSummary (TDD Section 4.1). */
function batchRowToSummary(row: BatchRow): BatchSummary {
  return {
    batch_id: row.id,
    status: row.status as BatchSummary['status'],
    recording_started_at: row.recording_started_at,
    uploaded_at: row.uploaded_at,
  };
}
