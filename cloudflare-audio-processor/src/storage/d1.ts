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
