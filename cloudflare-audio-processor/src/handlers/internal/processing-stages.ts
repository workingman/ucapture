/**
 * POST /internal/processing-stages handler.
 *
 * Receives per-stage timing data from GCP and writes rows to D1's
 * processing_stages table. Authenticated via X-Internal-Secret header.
 */

import type { Context } from 'hono';
import type { Env } from '../../env.d.ts';
import { insertProcessingStages } from '../../storage/d1.ts';
import type { ProcessingStageInput } from '../../storage/d1.ts';

/**
 * Validates a single stage object from the request body.
 */
function isValidStage(s: unknown): s is ProcessingStageInput {
  if (!s || typeof s !== 'object') return false;
  const obj = s as Record<string, unknown>;
  return (
    typeof obj.stage === 'string' &&
    obj.stage.length > 0 &&
    typeof obj.duration_seconds === 'number' &&
    typeof obj.success === 'boolean'
  );
}

/**
 * Handles POST /internal/processing-stages requests.
 *
 * @param c - Hono context with Worker env bindings
 * @returns JSON response indicating success or error
 */
export async function handleProcessingStages(
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
  if (typeof batchId !== 'string' || batchId.length === 0) {
    return c.json({ error: 'Missing or invalid batch_id' }, 400);
  }

  if (!Array.isArray(body.stages) || body.stages.length === 0) {
    return c.json({ error: 'Missing or empty stages array' }, 400);
  }

  const stages: ProcessingStageInput[] = [];
  for (const s of body.stages) {
    if (!isValidStage(s)) {
      return c.json({ error: 'Invalid stage object in stages array' }, 400);
    }
    stages.push(s);
  }

  await insertProcessingStages(c.env.DB, batchId, stages);

  return c.json({ success: true, inserted: stages.length }, 200);
}
