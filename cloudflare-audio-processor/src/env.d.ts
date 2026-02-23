/**
 * Cloudflare Worker environment bindings.
 *
 * All bindings declared in wrangler.toml must be typed here.
 */
export interface Env {
  /** R2 bucket for audio file storage */
  readonly R2_BUCKET: R2Bucket;

  /** D1 database for batch tracking */
  readonly DB: D1Database;

  /** Queue for normal-priority processing jobs */
  readonly PROCESSING_QUEUE: Queue;

  /** Queue for immediate-priority processing jobs */
  readonly PROCESSING_QUEUE_PRIORITY: Queue;

  /** KV namespace for OAuth token cache */
  readonly TOKEN_CACHE: KVNamespace;
}
