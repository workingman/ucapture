/**
 * POST /internal/publish-event handler.
 *
 * Receives completion events from GCP and publishes them to Pub/Sub.
 * Authenticated via X-Internal-Secret header (not OAuth).
 */

import type { Context } from 'hono';
import type { Env } from '../../env.d.ts';
import type { CompletionEvent } from '../../types/events.ts';
import { publishEvent } from '../../events/pubsub.ts';

/**
 * Validates that the request body is a well-formed CompletionEvent.
 * Returns the validated event or null if invalid.
 */
function validateCompletionEvent(body: unknown): CompletionEvent | null {
  if (!body || typeof body !== 'object') {
    return null;
  }

  const obj = body as Record<string, unknown>;

  if (typeof obj.batch_id !== 'string' || obj.batch_id.length === 0) {
    return null;
  }

  if (typeof obj.user_id !== 'string' || obj.user_id.length === 0) {
    return null;
  }

  if (obj.status !== 'completed' && obj.status !== 'failed') {
    return null;
  }

  if (typeof obj.recording_started_at !== 'string' || obj.recording_started_at.length === 0) {
    return null;
  }

  if (!obj.artifact_paths || typeof obj.artifact_paths !== 'object') {
    return null;
  }

  if (typeof obj.published_at !== 'string' || obj.published_at.length === 0) {
    return null;
  }

  // Failed events must include error_message
  if (obj.status === 'failed' && typeof obj.error_message !== 'string') {
    return null;
  }

  return body as CompletionEvent;
}

/**
 * Handles POST /internal/publish-event requests.
 *
 * Verifies X-Internal-Secret header, validates the CompletionEvent payload,
 * and publishes to the user-scoped Pub/Sub topic.
 *
 * @param c - Hono context with Worker env bindings
 * @returns JSON response indicating success or error
 */
export async function handlePublishEvent(
  c: Context<{ Bindings: Env }>,
): Promise<Response> {
  const secret = c.req.header('X-Internal-Secret');

  if (!secret || secret !== c.env.INTERNAL_SECRET) {
    return c.json({ error: 'Forbidden' }, 403);
  }

  let body: unknown;
  try {
    body = await c.req.json();
  } catch {
    return c.json({ error: 'Invalid JSON body' }, 400);
  }

  const event = validateCompletionEvent(body);

  if (!event) {
    return c.json({ error: 'Invalid completion event payload' }, 400);
  }

  await publishEvent(c.env.PUBSUB_NAMESPACE, event);

  return c.json({ success: true }, 200);
}
