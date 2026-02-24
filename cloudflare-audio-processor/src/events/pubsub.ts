/**
 * Pub/Sub publishing helper for completion events.
 *
 * Publishes events to user-scoped topics via the Cloudflare Pub/Sub binding.
 * Topic pattern: `batch-completions/{user_id}`
 */

import type { CompletionEvent } from '../types/events.ts';

/** Pub/Sub binding interface (subset of Cloudflare Pub/Sub namespace). */
interface PubSubNamespace {
  publish(topic: string, message: string): Promise<void>;
}

/**
 * Publishes a completion event to the user-scoped Pub/Sub topic.
 *
 * @param pubsub - Cloudflare Pub/Sub namespace binding
 * @param event - Completion event to publish
 */
export async function publishEvent(
  pubsub: PubSubNamespace,
  event: CompletionEvent,
): Promise<void> {
  const topic = `batch-completions/${event.user_id}`;
  await pubsub.publish(topic, JSON.stringify(event));
}
