/**
 * GET /v1/pubsub/credentials handler.
 *
 * Returns MQTT connection details for the authenticated user's persistent Pub/Sub session.
 * The client ID is stable per user (`ucapture-{user_sub}`) so the broker retains
 * session state across disconnects.
 *
 * Open Question Q6: Cloudflare Pub/Sub has offline queue depth/TTL limits (TBD).
 * If the phone is offline longer than broker retention, the app should call
 * GET /v1/batches on reconnect as a catch-up fallback.
 */

import type { Context } from 'hono';
import type { Env } from '../env.d.ts';

/** Response shape for the MQTT credential endpoint. */
export interface PubSubCredentialsResponse {
  readonly broker_url: string;
  readonly client_id: string;
  readonly topic_pattern: string;
  readonly session_config: {
    readonly clean_session: boolean;
    readonly qos: number;
  };
}

/**
 * Handles GET /v1/pubsub/credentials requests.
 *
 * Returns MQTT broker URL, a stable client ID derived from the OAuth user sub,
 * the topic pattern for completion events, and session configuration hints
 * for persistent delivery (clean_session=false, QoS=1).
 *
 * @param c - Hono context with auth variables set by OAuth middleware
 * @returns JSON response with MQTT connection details
 */
export async function handleGetPubSubCredentials(
  c: Context<{ Bindings: Env; Variables: { user_id: string; email: string } }>,
): Promise<Response> {
  const userId = c.get('user_id');

  const response: PubSubCredentialsResponse = {
    broker_url: c.env.PUBSUB_BROKER_URL,
    client_id: `ucapture-${userId}`,
    topic_pattern: `batch-completions/${userId}`,
    session_config: {
      clean_session: false,
      qos: 1,
    },
  };

  return c.json(response, 200);
}
