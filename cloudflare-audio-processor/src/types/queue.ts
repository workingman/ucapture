/**
 * Queue message types for the Cloudflare Queue processing pipeline.
 *
 * Matches TDD section 4.2 (Queue Message Schema).
 */

import type { BatchPriority } from './batch.ts';

/** Message body enqueued for audio processing on GCP Cloud Run. */
export interface ProcessingJob {
  readonly batch_id: string;
  readonly user_id: string;
  readonly priority: BatchPriority;
  readonly enqueued_at: string;
}
