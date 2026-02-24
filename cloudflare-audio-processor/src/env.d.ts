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

  /** Cloudflare account ID for R2 S3-compatible endpoint */
  readonly R2_ACCOUNT_ID: string;

  /** R2 S3-compatible access key ID for presigned URLs */
  readonly R2_ACCESS_KEY_ID: string;

  /** R2 S3-compatible secret access key for presigned URLs */
  readonly R2_SECRET_ACCESS_KEY: string;

  /** R2 bucket name for S3-compatible presigned URL generation */
  readonly R2_BUCKET_NAME: string;

  /** Shared secret for GCP -> Worker internal endpoint authentication */
  readonly INTERNAL_SECRET: string;

  /** Cloudflare Pub/Sub binding for publishing completion events */
  readonly PUBSUB_NAMESPACE: {
    publish(topic: string, message: string): Promise<void>;
  };

  /** MQTT broker URL for client credential responses */
  readonly PUBSUB_BROKER_URL: string;
}
