-- Migration 0001: Create batch tracking tables
-- Creates the 4-table D1 schema for audio batch lifecycle tracking.

-- Primary batch index: tracks every upload, artifacts, status, and metrics.
CREATE TABLE batches (
  id TEXT PRIMARY KEY,
  user_id TEXT NOT NULL,
  status TEXT NOT NULL,
  priority TEXT NOT NULL DEFAULT 'normal',
  raw_audio_path TEXT,
  metadata_path TEXT,
  cleaned_audio_path TEXT,
  transcript_formatted_path TEXT,
  transcript_raw_path TEXT,
  transcript_emotion_path TEXT,
  recording_started_at TEXT NOT NULL,
  recording_ended_at TEXT,
  recording_duration_seconds REAL,
  uploaded_at TEXT NOT NULL DEFAULT (datetime('now')),
  processing_started_at TEXT,
  processing_completed_at TEXT,
  processing_wall_time_seconds REAL,
  queue_wait_time_seconds REAL,
  raw_audio_size_bytes INTEGER,
  raw_audio_duration_seconds REAL,
  speech_duration_seconds REAL,
  speech_ratio REAL,
  cleaned_audio_size_bytes INTEGER,
  speechmatics_job_id TEXT,
  speechmatics_cost_estimate REAL,
  emotion_provider TEXT,
  emotion_analyzed_at TEXT,
  retry_count INTEGER DEFAULT 0,
  error_message TEXT,
  error_stage TEXT,
  CONSTRAINT status_values CHECK (status IN ('uploaded', 'processing', 'completed', 'failed')),
  CONSTRAINT priority_values CHECK (priority IN ('immediate', 'normal'))
);

CREATE INDEX idx_batches_user_id ON batches(user_id);
CREATE INDEX idx_batches_status ON batches(status);
CREATE INDEX idx_batches_user_status ON batches(user_id, status);
CREATE INDEX idx_batches_user_started ON batches(user_id, recording_started_at DESC);

-- Images captured during a recording session, linked to a batch.
CREATE TABLE batch_images (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  batch_id TEXT NOT NULL,
  r2_path TEXT NOT NULL,
  captured_at TEXT NOT NULL,
  size_bytes INTEGER,
  FOREIGN KEY (batch_id) REFERENCES batches(id) ON DELETE CASCADE
);

CREATE INDEX idx_images_batch ON batch_images(batch_id);

-- Text notes attached to a recording session, linked to a batch.
CREATE TABLE batch_notes (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  batch_id TEXT NOT NULL,
  note_text TEXT NOT NULL,
  created_at TEXT NOT NULL,
  FOREIGN KEY (batch_id) REFERENCES batches(id) ON DELETE CASCADE
);

CREATE INDEX idx_notes_batch ON batch_notes(batch_id);

-- Observability: tracks individual processing stages for each batch.
CREATE TABLE processing_stages (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  batch_id TEXT NOT NULL,
  stage TEXT NOT NULL,
  started_at TEXT NOT NULL,
  completed_at TEXT,
  duration_seconds REAL,
  success BOOLEAN,
  error_message TEXT,
  FOREIGN KEY (batch_id) REFERENCES batches(id) ON DELETE CASCADE
);

CREATE INDEX idx_stages_batch ON processing_stages(batch_id);
