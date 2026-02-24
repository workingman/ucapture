/**
 * Queue publisher for enqueuing audio processing jobs.
 *
 * Routes jobs to the correct queue based on priority:
 * - "immediate" -> PROCESSING_QUEUE_PRIORITY
 * - "normal"    -> PROCESSING_QUEUE
 */

import type { ProcessingJob } from '../types/queue.ts';
import type { BatchPriority } from '../types/batch.ts';

/**
 * Enqueues a processing job to the appropriate Cloudflare Queue.
 *
 * @param normalQueue - Queue for normal-priority jobs
 * @param priorityQueue - Queue for immediate-priority jobs
 * @param job - Processing job message to enqueue
 */
export async function enqueueProcessingJob(
  normalQueue: Queue,
  priorityQueue: Queue,
  job: ProcessingJob,
): Promise<void> {
  const queue = job.priority === 'immediate' ? priorityQueue : normalQueue;
  await queue.send(job);
}

/**
 * Builds a ProcessingJob message from upload context.
 *
 * @param batchId - Generated batch ID
 * @param userId - Authenticated user's ID
 * @param priority - Upload priority level
 * @returns Complete ProcessingJob message
 */
export function buildProcessingJob(
  batchId: string,
  userId: string,
  priority: BatchPriority,
): ProcessingJob {
  return {
    batch_id: batchId,
    user_id: userId,
    priority,
    enqueued_at: new Date().toISOString(),
  };
}
