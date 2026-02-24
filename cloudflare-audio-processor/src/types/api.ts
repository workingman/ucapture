/**
 * API request/response types for the Worker REST endpoints.
 *
 * Matches TDD section 4.1 (REST API response shapes).
 */

import type { BatchStatus, BatchPriority, ArtifactPaths } from './batch.ts';

/** POST /v1/upload response body. */
export interface UploadResponse {
  readonly batch_id: string;
  readonly status: BatchStatus;
  readonly uploaded_at: string;
}

/** GET /v1/status/:batch_id response body. */
export interface StatusResponse {
  readonly batch_id: string;
  readonly user_id: string;
  readonly status: BatchStatus;
  readonly priority: BatchPriority;
  readonly artifacts: ArtifactPaths;
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
  readonly retry_count: number;
  readonly error_message: string | null;
  readonly error_stage: string | null;
}

/** Pagination metadata for list endpoints. */
export interface Pagination {
  readonly limit: number;
  readonly offset: number;
  readonly total: number;
}

/** GET /v1/batches response body. */
export interface BatchListResponse {
  readonly batches: StatusResponse[];
  readonly pagination: Pagination;
}

/** Batch summary used in list responses (same shape as StatusResponse). */
export type BatchSummary = StatusResponse;

/** Pagination metadata (alias for Pagination). */
export type PaginationMeta = Pagination;

/** Artifact map (re-export for API consumers). */
export type ArtifactMap = ArtifactPaths;

/** Batch processing metrics (non-null subset of StatusResponse fields). */
export interface BatchMetrics {
  readonly speech_duration_seconds: number | null;
  readonly speech_ratio: number | null;
  readonly speechmatics_cost_estimate?: number | null;
}

/** Standard error response body. */
export interface ErrorResponse {
  readonly error: string;
  readonly details?: string;
}
