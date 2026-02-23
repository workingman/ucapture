import { describe, it, expect, vi, beforeEach } from 'vitest';
import {
  createBatch,
  getBatchById,
  updateBatchStatus,
  insertBatchImages,
  insertBatchNotes,
} from '../src/storage/d1.ts';
import type { CreateBatchInput, BatchRow } from '../src/storage/d1.ts';

/**
 * Mock D1Database for unit testing query helpers.
 *
 * Captures SQL and bind parameters so tests can verify:
 * - Correct SQL structure (parameterized, no string interpolation)
 * - Correct bind values and ordering
 * - User isolation in WHERE clauses
 */
function createMockD1(options?: {
  firstResult?: unknown;
}): D1Database & {
  lastSql: string;
  lastBindings: unknown[];
  batchCalls: Array<{ sql: string; bindings: unknown[] }>;
} {
  // Shared state object -- all references point here (not spread-copied).
  const state = {
    lastSql: '' as string,
    lastBindings: [] as unknown[],
    batchCalls: [] as Array<{ sql: string; bindings: unknown[] }>,
  };

  const createStatement = (sql: string) => {
    return {
      bind(...args: unknown[]) {
        state.lastSql = sql;
        state.lastBindings = args;
        state.batchCalls.push({ sql, bindings: args });
        return this;
      },
      async run() {
        return { success: true, meta: {} };
      },
      async first<T>(): Promise<T | null> {
        return (options?.firstResult as T) ?? null;
      },
      async all() {
        return { results: [] };
      },
    };
  };

  const db = {
    // Expose state as getters so reads always hit the shared object
    get lastSql() { return state.lastSql; },
    get lastBindings() { return state.lastBindings; },
    get batchCalls() { return state.batchCalls; },

    prepare(sql: string) {
      return createStatement(sql);
    },
    async batch(statements: unknown[]) {
      return statements.map(() => ({ success: true, results: [], meta: {} }));
    },
    async dump() {
      return new ArrayBuffer(0);
    },
    async exec(_sql: string) {
      return { count: 0, duration: 0 };
    },
  };

  return db as unknown as D1Database & { lastSql: string; lastBindings: unknown[]; batchCalls: Array<{ sql: string; bindings: unknown[] }> };
}

// Reusable test fixtures
const SAMPLE_BATCH: CreateBatchInput = {
  id: '20260222-143027-GMT-a1b2c3d4-e5f6-7890-abcd-ef1234567890',
  user_id: 'user-abc-123',
  status: 'uploaded',
  priority: 'normal',
  raw_audio_path: 'user-abc-123/batch1/raw-audio/recording.m4a',
  metadata_path: 'user-abc-123/batch1/metadata/metadata.json',
  recording_started_at: '2026-02-22T14:30:27Z',
  recording_ended_at: '2026-02-22T15:00:00Z',
  recording_duration_seconds: 1773,
  raw_audio_size_bytes: 5242880,
  raw_audio_duration_seconds: 1773,
};

const SAMPLE_BATCH_ROW: BatchRow = {
  id: SAMPLE_BATCH.id,
  user_id: SAMPLE_BATCH.user_id,
  status: 'uploaded',
  priority: 'normal',
  raw_audio_path: SAMPLE_BATCH.raw_audio_path!,
  metadata_path: SAMPLE_BATCH.metadata_path!,
  cleaned_audio_path: null,
  transcript_formatted_path: null,
  transcript_raw_path: null,
  transcript_emotion_path: null,
  recording_started_at: SAMPLE_BATCH.recording_started_at,
  recording_ended_at: SAMPLE_BATCH.recording_ended_at!,
  recording_duration_seconds: SAMPLE_BATCH.recording_duration_seconds!,
  uploaded_at: '2026-02-22T14:31:00Z',
  processing_started_at: null,
  processing_completed_at: null,
  processing_wall_time_seconds: null,
  queue_wait_time_seconds: null,
  raw_audio_size_bytes: SAMPLE_BATCH.raw_audio_size_bytes!,
  raw_audio_duration_seconds: SAMPLE_BATCH.raw_audio_duration_seconds!,
  speech_duration_seconds: null,
  speech_ratio: null,
  cleaned_audio_size_bytes: null,
  speechmatics_job_id: null,
  speechmatics_cost_estimate: null,
  emotion_provider: null,
  emotion_analyzed_at: null,
  retry_count: 0,
  error_message: null,
  error_stage: null,
};

describe('createBatch', () => {
  it('inserts a batch with all fields using parameterized bindings', async () => {
    const db = createMockD1();
    await createBatch(db, SAMPLE_BATCH);

    expect(db.lastSql).toContain('INSERT INTO batches');
    expect(db.lastSql).toContain('VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)');
    expect(db.lastBindings).toEqual([
      SAMPLE_BATCH.id,
      SAMPLE_BATCH.user_id,
      'uploaded',
      'normal',
      SAMPLE_BATCH.raw_audio_path,
      SAMPLE_BATCH.metadata_path,
      SAMPLE_BATCH.recording_started_at,
      SAMPLE_BATCH.recording_ended_at,
      SAMPLE_BATCH.recording_duration_seconds,
      SAMPLE_BATCH.raw_audio_size_bytes,
      SAMPLE_BATCH.raw_audio_duration_seconds,
    ]);
  });

  it('binds null for optional fields when not provided', async () => {
    const db = createMockD1();
    const minimalBatch: CreateBatchInput = {
      id: 'batch-minimal',
      user_id: 'user-1',
      status: 'uploaded',
      priority: 'normal',
      recording_started_at: '2026-02-22T14:30:27Z',
    };

    await createBatch(db, minimalBatch);

    // Optional fields should be null
    expect(db.lastBindings[4]).toBeNull(); // raw_audio_path
    expect(db.lastBindings[5]).toBeNull(); // metadata_path
    expect(db.lastBindings[7]).toBeNull(); // recording_ended_at
    expect(db.lastBindings[8]).toBeNull(); // recording_duration_seconds
    expect(db.lastBindings[9]).toBeNull(); // raw_audio_size_bytes
    expect(db.lastBindings[10]).toBeNull(); // raw_audio_duration_seconds
  });
});

describe('getBatchById', () => {
  it('returns batch row when found with matching user_id', async () => {
    const db = createMockD1({ firstResult: SAMPLE_BATCH_ROW });
    const result = await getBatchById(db, SAMPLE_BATCH.id, SAMPLE_BATCH.user_id);

    expect(result).toEqual(SAMPLE_BATCH_ROW);
    expect(db.lastSql).toContain('WHERE id = ? AND user_id = ?');
    expect(db.lastBindings).toEqual([SAMPLE_BATCH.id, SAMPLE_BATCH.user_id]);
  });

  it('returns null when batch does not exist or user_id mismatches (user isolation)', async () => {
    const db = createMockD1({ firstResult: null });
    const result = await getBatchById(db, SAMPLE_BATCH.id, 'wrong-user');

    expect(result).toBeNull();
    expect(db.lastBindings).toEqual([SAMPLE_BATCH.id, 'wrong-user']);
  });

  it('enforces user isolation via AND user_id = ? in SQL', async () => {
    const db = createMockD1();
    await getBatchById(db, 'any-batch', 'any-user');

    // The SQL must include both conditions for user isolation
    expect(db.lastSql).toMatch(/WHERE\s+id\s*=\s*\?\s+AND\s+user_id\s*=\s*\?/);
  });
});

describe('updateBatchStatus', () => {
  it('updates status only when no extra fields given', async () => {
    const db = createMockD1();
    await updateBatchStatus(db, SAMPLE_BATCH.id, 'processing');

    expect(db.lastSql).toContain('UPDATE batches SET status = ? WHERE id = ?');
    expect(db.lastBindings).toEqual(['processing', SAMPLE_BATCH.id]);
  });

  it('updates status plus additional metric fields', async () => {
    const db = createMockD1();
    await updateBatchStatus(db, SAMPLE_BATCH.id, 'completed', {
      processing_completed_at: '2026-02-22T15:10:00Z',
      processing_wall_time_seconds: 120.5,
      speech_ratio: 0.85,
    });

    expect(db.lastSql).toContain('UPDATE batches SET');
    expect(db.lastSql).toContain('status = ?');
    expect(db.lastSql).toContain('processing_completed_at = ?');
    expect(db.lastSql).toContain('processing_wall_time_seconds = ?');
    expect(db.lastSql).toContain('speech_ratio = ?');
    expect(db.lastSql).toContain('WHERE id = ?');
    // Values: status, processing_completed_at, wall_time, speech_ratio, batchId
    expect(db.lastBindings).toEqual([
      'completed',
      '2026-02-22T15:10:00Z',
      120.5,
      0.85,
      SAMPLE_BATCH.id,
    ]);
  });
});

describe('insertBatchImages', () => {
  it('inserts multiple images using db.batch()', async () => {
    const db = createMockD1();
    const images = [
      { r2_path: 'user/batch/images/photo1.jpg', captured_at: '2026-02-22T14:35:00Z', size_bytes: 102400 },
      { r2_path: 'user/batch/images/photo2.jpg', captured_at: '2026-02-22T14:40:00Z', size_bytes: 204800 },
    ];

    await insertBatchImages(db, SAMPLE_BATCH.id, images);

    expect(db.batchCalls).toHaveLength(2);
    expect(db.batchCalls[0].sql).toContain('INSERT INTO batch_images');
    expect(db.batchCalls[0].bindings).toEqual([
      SAMPLE_BATCH.id, 'user/batch/images/photo1.jpg', '2026-02-22T14:35:00Z', 102400,
    ]);
    expect(db.batchCalls[1].bindings).toEqual([
      SAMPLE_BATCH.id, 'user/batch/images/photo2.jpg', '2026-02-22T14:40:00Z', 204800,
    ]);
  });

  it('does nothing for empty images array', async () => {
    const db = createMockD1();
    await insertBatchImages(db, SAMPLE_BATCH.id, []);

    expect(db.batchCalls).toHaveLength(0);
  });
});

describe('insertBatchNotes', () => {
  it('inserts multiple notes using db.batch()', async () => {
    const db = createMockD1();
    const notes = [
      { note_text: 'First observation', created_at: '2026-02-22T14:32:00Z' },
      { note_text: 'Follow-up note', created_at: '2026-02-22T14:45:00Z' },
    ];

    await insertBatchNotes(db, SAMPLE_BATCH.id, notes);

    expect(db.batchCalls).toHaveLength(2);
    expect(db.batchCalls[0].sql).toContain('INSERT INTO batch_notes');
    expect(db.batchCalls[0].bindings).toEqual([
      SAMPLE_BATCH.id, 'First observation', '2026-02-22T14:32:00Z',
    ]);
    expect(db.batchCalls[1].bindings).toEqual([
      SAMPLE_BATCH.id, 'Follow-up note', '2026-02-22T14:45:00Z',
    ]);
  });

  it('does nothing for empty notes array', async () => {
    const db = createMockD1();
    await insertBatchNotes(db, SAMPLE_BATCH.id, []);

    expect(db.batchCalls).toHaveLength(0);
  });
});
