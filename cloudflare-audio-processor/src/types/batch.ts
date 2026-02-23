/**
 * Batch domain types matching the D1 batches table schema.
 */

/** Valid batch processing statuses (matches CHECK constraint). */
export type BatchStatus = 'uploaded' | 'processing' | 'completed' | 'failed';

/** Valid batch priority levels (matches CHECK constraint). */
export type BatchPriority = 'immediate' | 'normal';

/** Full batch record matching D1 batches table columns. */
export interface Batch {
  readonly id: string;
  readonly user_id: string;
  readonly status: BatchStatus;
  readonly priority: BatchPriority;
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

/** Keyed artifact paths for a batch's R2-stored files. */
export interface ArtifactPaths {
  readonly raw_audio?: string;
  readonly metadata?: string;
  readonly cleaned_audio?: string;
  readonly transcript_formatted?: string;
  readonly transcript_raw?: string;
  readonly transcript_emotion?: string;
  readonly images?: string[];
}
