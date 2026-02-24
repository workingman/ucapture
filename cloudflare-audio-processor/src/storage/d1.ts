/**
 * D1 query helpers for batch CRUD operations.
 *
 * All queries use parameterized bindings (.bind()) -- never string interpolation.
 * User isolation: getBatchById scopes SELECT by user_id.
 */

/** Input for creating a new batch record. */
export interface CreateBatchInput {
  readonly id: string;
  readonly user_id: string;
  readonly status: string;
  readonly priority: string;
  readonly raw_audio_path?: string | null;
  readonly metadata_path?: string | null;
  readonly recording_started_at: string;
  readonly recording_ended_at?: string | null;
  readonly recording_duration_seconds?: number | null;
  readonly raw_audio_size_bytes?: number | null;
  readonly raw_audio_duration_seconds?: number | null;
}

/** Row shape returned by D1 for the batches table. */
export interface BatchRow {
  readonly id: string;
  readonly user_id: string;
  readonly status: string;
  readonly priority: string;
  readonly raw_audio_path: string | null;
  readonly metadata_path: string | null;
  readonly cleaned_audio_path: string | null;
  readonly transcript_formatted_path: string | null;
  readonly transcript_raw_path: string | null;
  readonly transcript_emotion_path: string | null;
  readonly recording_started_at: string;
  readonly recording_ended_at: string | null;
  readonly recording_duration_seconds: number | null;
  readonly uploaded_at: string;
  readonly processing_started_at: string | null;
  readonly processing_completed_at: string | null;
  readonly processing_wall_time_seconds: number | null;
  readonly queue_wait_time_seconds: number | null;
  readonly raw_audio_size_bytes: number | null;
  readonly raw_audio_duration_seconds: number | null;
  readonly speech_duration_seconds: number | null;
  readonly speech_ratio: number | null;
  readonly cleaned_audio_size_bytes: number | null;
  readonly speechmatics_job_id: string | null;
  readonly speechmatics_cost_estimate: number | null;
  readonly emotion_provider: string | null;
  readonly emotion_analyzed_at: string | null;
  readonly retry_count: number;
  readonly error_message: string | null;
  readonly error_stage: string | null;
}

/** Optional fields that can be updated alongside status. */
export interface UpdateBatchFields {
  readonly processing_started_at?: string;
  readonly processing_completed_at?: string;
  readonly processing_wall_time_seconds?: number;
  readonly queue_wait_time_seconds?: number;
  readonly cleaned_audio_path?: string;
  readonly transcript_formatted_path?: string;
  readonly transcript_raw_path?: string;
  readonly transcript_emotion_path?: string;
  readonly speech_duration_seconds?: number;
  readonly speech_ratio?: number;
  readonly cleaned_audio_size_bytes?: number;
  readonly speechmatics_job_id?: string;
  readonly speechmatics_cost_estimate?: number;
  readonly emotion_provider?: string;
  readonly emotion_analyzed_at?: string;
  readonly retry_count?: number;
  readonly error_message?: string;
  readonly error_stage?: string;
}

/** Input for inserting a batch image record. */
export interface BatchImageInput {
  readonly r2_path: string;
  readonly captured_at: string;
  readonly size_bytes?: number | null;
}

/** Input for inserting a batch note record. */
export interface BatchNoteInput {
  readonly note_text: string;
  readonly created_at: string;
}

/**
 * Inserts a new batch record into the batches table.
 *
 * @param db - D1Database binding
 * @param batch - Batch fields to insert
 */
export async function createBatch(
  db: D1Database,
  batch: CreateBatchInput,
): Promise<void> {
  const sql = `
    INSERT INTO batches (
      id, user_id, status, priority,
      raw_audio_path, metadata_path,
      recording_started_at, recording_ended_at, recording_duration_seconds,
      raw_audio_size_bytes, raw_audio_duration_seconds
    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
  `;

  await db
    .prepare(sql)
    .bind(
      batch.id,
      batch.user_id,
      batch.status,
      batch.priority,
      batch.raw_audio_path ?? null,
      batch.metadata_path ?? null,
      batch.recording_started_at,
      batch.recording_ended_at ?? null,
      batch.recording_duration_seconds ?? null,
      batch.raw_audio_size_bytes ?? null,
      batch.raw_audio_duration_seconds ?? null,
    )
    .run();
}

/**
 * Fetches a batch by ID, scoped to the given user.
 * Returns null if the batch does not exist or belongs to a different user.
 *
 * @param db - D1Database binding
 * @param batchId - The batch ID to look up
 * @param userId - The authenticated user's ID (user isolation)
 * @returns The batch row, or null if not found / wrong user
 */
export async function getBatchById(
  db: D1Database,
  batchId: string,
  userId: string,
): Promise<BatchRow | null> {
  const sql = `SELECT * FROM batches WHERE id = ? AND user_id = ?`;

  const result = await db.prepare(sql).bind(batchId, userId).first<BatchRow>();
  return result ?? null;
}

/**
 * Fetches a batch by ID without user scoping.
 * Used when the caller needs to distinguish 404 (not found) from 403 (wrong user).
 *
 * @param db - D1Database binding
 * @param batchId - The batch ID to look up
 * @returns The batch row, or null if not found
 */
export async function findBatchById(
  db: D1Database,
  batchId: string,
): Promise<BatchRow | null> {
  const sql = `SELECT * FROM batches WHERE id = ?`;

  const result = await db.prepare(sql).bind(batchId).first<BatchRow>();
  return result ?? null;
}

/** Row shape returned by D1 for the batch_images table. */
export interface BatchImageRow {
  readonly id: number;
  readonly batch_id: string;
  readonly r2_path: string;
  readonly captured_at: string | null;
  readonly size_bytes: number | null;
}

/**
 * Fetches all images associated with a batch.
 *
 * @param db - D1Database binding
 * @param batchId - The batch ID to look up images for
 * @returns Array of image rows
 */
export async function getBatchImages(
  db: D1Database,
  batchId: string,
): Promise<BatchImageRow[]> {
  const sql = `SELECT id, batch_id, r2_path, captured_at, size_bytes FROM batch_images WHERE batch_id = ?`;

  const result = await db.prepare(sql).bind(batchId).all<BatchImageRow>();
  return result.results ?? [];
}

/**
 * Updates a batch's status and optionally sets additional metric fields.
 *
 * @param db - D1Database binding
 * @param batchId - The batch ID to update
 * @param status - New status value
 * @param fields - Optional additional fields to update
 */
export async function updateBatchStatus(
  db: D1Database,
  batchId: string,
  status: string,
  fields?: UpdateBatchFields,
): Promise<void> {
  const setClauses: string[] = ['status = ?'];
  const values: unknown[] = [status];

  if (fields) {
    for (const [key, value] of Object.entries(fields)) {
      if (value !== undefined) {
        setClauses.push(`${key} = ?`);
        values.push(value);
      }
    }
  }

  values.push(batchId);

  const sql = `UPDATE batches SET ${setClauses.join(', ')} WHERE id = ?`;
  await db.prepare(sql).bind(...values).run();
}

/**
 * Inserts one or more image records linked to a batch.
 *
 * @param db - D1Database binding
 * @param batchId - The batch ID to link images to
 * @param images - Array of image records to insert
 */
export async function insertBatchImages(
  db: D1Database,
  batchId: string,
  images: BatchImageInput[],
): Promise<void> {
  if (images.length === 0) return;

  const stmt = db.prepare(
    `INSERT INTO batch_images (batch_id, r2_path, captured_at, size_bytes) VALUES (?, ?, ?, ?)`,
  );

  const statements = images.map((img) =>
    stmt.bind(batchId, img.r2_path, img.captured_at, img.size_bytes ?? null),
  );

  await db.batch(statements);
}

/**
 * Inserts one or more note records linked to a batch.
 *
 * @param db - D1Database binding
 * @param batchId - The batch ID to link notes to
 * @param notes - Array of note records to insert
 */
export async function insertBatchNotes(
  db: D1Database,
  batchId: string,
  notes: BatchNoteInput[],
): Promise<void> {
  if (notes.length === 0) return;

  const stmt = db.prepare(
    `INSERT INTO batch_notes (batch_id, note_text, created_at) VALUES (?, ?, ?)`,
  );

  const statements = notes.map((note) =>
    stmt.bind(batchId, note.note_text, note.created_at),
  );

  await db.batch(statements);
}

/** Input for inserting a processing stage timing row. */
export interface ProcessingStageInput {
  readonly stage: string;
  readonly duration_seconds: number;
  readonly success: boolean;
  readonly error_message?: string | null;
}

/**
 * Inserts per-stage timing rows into the processing_stages table.
 *
 * @param db - D1Database binding
 * @param batchId - The batch ID to link stages to
 * @param stages - Array of stage timing records
 */
export async function insertProcessingStages(
  db: D1Database,
  batchId: string,
  stages: ProcessingStageInput[],
): Promise<void> {
  if (stages.length === 0) return;

  const stmt = db.prepare(
    `INSERT INTO processing_stages (batch_id, stage, started_at, duration_seconds, success, error_message) VALUES (?, ?, datetime('now'), ?, ?, ?)`,
  );

  const statements = stages.map((s) =>
    stmt.bind(batchId, s.stage, s.duration_seconds, s.success ? 1 : 0, s.error_message ?? null),
  );

  await db.batch(statements);
}

/** Filter options for listing batches. */
export interface ListBatchesFilter {
  readonly userId: string;
  readonly status?: string;
  readonly startDate?: string;
  readonly endDate?: string;
  readonly limit: number;
  readonly offset: number;
}

/**
 * Lists batches for a user with optional filtering, pagination, and ordering.
 *
 * @param db - D1Database binding
 * @param filter - Filter and pagination options
 * @returns Array of batch rows matching the filter
 */
export async function listBatches(
  db: D1Database,
  filter: ListBatchesFilter,
): Promise<BatchRow[]> {
  const { sql, bindings } = buildListQuery(filter, false);
  const result = await db.prepare(sql).bind(...bindings).all<BatchRow>();
  return result.results ?? [];
}

/**
 * Counts total batches matching the filter (for pagination metadata).
 *
 * @param db - D1Database binding
 * @param filter - Filter options (limit/offset ignored for counting)
 * @returns Total number of matching batches
 */
export async function countBatches(
  db: D1Database,
  filter: ListBatchesFilter,
): Promise<number> {
  const { sql, bindings } = buildListQuery(filter, true);
  const result = await db.prepare(sql).bind(...bindings).first<{ count: number }>();
  return result?.count ?? 0;
}

/** Builds the SQL and bindings for list/count queries with dynamic WHERE clauses. */
function buildListQuery(
  filter: ListBatchesFilter,
  countOnly: boolean,
): { sql: string; bindings: unknown[] } {
  const conditions: string[] = ['user_id = ?'];
  const bindings: unknown[] = [filter.userId];

  if (filter.status) {
    conditions.push('status = ?');
    bindings.push(filter.status);
  }

  if (filter.startDate) {
    conditions.push('recording_started_at >= ?');
    bindings.push(filter.startDate);
  }

  if (filter.endDate) {
    conditions.push('recording_started_at <= ?');
    bindings.push(filter.endDate);
  }

  const where = conditions.join(' AND ');

  if (countOnly) {
    return {
      sql: `SELECT COUNT(*) AS count FROM batches WHERE ${where}`,
      bindings,
    };
  }

  bindings.push(filter.limit, filter.offset);
  return {
    sql: `SELECT * FROM batches WHERE ${where} ORDER BY recording_started_at DESC LIMIT ? OFFSET ?`,
    bindings,
  };
}
