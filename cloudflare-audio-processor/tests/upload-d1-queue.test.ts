import { describe, it, expect, vi, beforeEach } from 'vitest';
import { buildProcessingJob, enqueueProcessingJob } from '../src/queue/publisher.ts';
import type { ProcessingJob } from '../src/types/queue.ts';
import type { BatchPriority } from '../src/types/batch.ts';

describe('buildProcessingJob', () => {
  it('builds a ProcessingJob with correct fields', () => {
    const beforeTime = new Date().toISOString();
    const job = buildProcessingJob('batch-abc-123', 'user-xyz-456', 'normal');
    const afterTime = new Date().toISOString();

    expect(job.batch_id).toBe('batch-abc-123');
    expect(job.user_id).toBe('user-xyz-456');
    expect(job.priority).toBe('normal');
    expect(job.enqueued_at >= beforeTime).toBe(true);
    expect(job.enqueued_at <= afterTime).toBe(true);
  });

  it('preserves immediate priority in the job message', () => {
    const job = buildProcessingJob('batch-imm-001', 'user-fast', 'immediate');

    expect(job.priority).toBe('immediate');
    expect(job.batch_id).toBe('batch-imm-001');
    expect(job.user_id).toBe('user-fast');
  });
});

describe('enqueueProcessingJob', () => {
  let normalQueue: Queue & { send: ReturnType<typeof vi.fn> };
  let priorityQueue: Queue & { send: ReturnType<typeof vi.fn> };

  beforeEach(() => {
    normalQueue = { send: vi.fn() } as unknown as Queue & { send: ReturnType<typeof vi.fn> };
    priorityQueue = { send: vi.fn() } as unknown as Queue & { send: ReturnType<typeof vi.fn> };
  });

  it('routes normal priority jobs to the normal queue', async () => {
    const job: ProcessingJob = {
      batch_id: 'batch-normal-001',
      user_id: 'user-001',
      priority: 'normal',
      enqueued_at: '2026-02-22T14:30:00Z',
    };

    await enqueueProcessingJob(normalQueue, priorityQueue, job);

    expect(normalQueue.send).toHaveBeenCalledWith(job);
    expect(priorityQueue.send).not.toHaveBeenCalled();
  });

  it('routes immediate priority jobs to the priority queue', async () => {
    const job: ProcessingJob = {
      batch_id: 'batch-urgent-001',
      user_id: 'user-002',
      priority: 'immediate',
      enqueued_at: '2026-02-22T14:30:00Z',
    };

    await enqueueProcessingJob(normalQueue, priorityQueue, job);

    expect(priorityQueue.send).toHaveBeenCalledWith(job);
    expect(normalQueue.send).not.toHaveBeenCalled();
  });
});
