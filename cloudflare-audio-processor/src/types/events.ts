/**
 * Event types for the Pub/Sub completion event pipeline.
 *
 * Matches TDD section 4.3 (Pub/Sub Event Schema).
 */

/** Completion event published to Pub/Sub when a batch finishes processing. */
export interface CompletionEvent {
  readonly batch_id: string;
  readonly user_id: string;
  readonly status: 'completed' | 'failed';
  readonly recording_started_at: string;
  readonly artifact_paths: {
    readonly raw_audio?: string;
    readonly cleaned_audio?: string;
    readonly transcript_formatted?: string;
    readonly transcript_raw?: string;
  };
  readonly error_message?: string;
  readonly published_at: string;
}
