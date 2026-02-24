# Observability: BigQuery Schema and Aggregation Queries

Reference for the `audio_pipeline.batch_metrics` table, GCP Cloud Logging
sink configuration, and operational SQL queries.

---

## 1. BigQuery Table DDL

```sql
-- Dataset: audio_pipeline
-- Table:   batch_metrics
--
-- Populated by a GCP Cloud Logging sink that routes structured JSON
-- log entries with metric_type = "batch_completion" from Cloud Run
-- stdout into BigQuery.

CREATE TABLE IF NOT EXISTS audio_pipeline.batch_metrics (
  timestamp                    TIMESTAMP   NOT NULL,
  batch_id                     STRING      NOT NULL,
  user_id                      STRING      NOT NULL,
  status                       STRING      NOT NULL,

  -- Audio durations
  raw_audio_duration_seconds   FLOAT64     NOT NULL,
  speech_duration_seconds      FLOAT64     NOT NULL,
  speech_ratio                 FLOAT64     NOT NULL,

  -- Processing timing
  processing_wall_time_seconds FLOAT64     NOT NULL,
  queue_wait_time_seconds      FLOAT64     NOT NULL,

  -- Sizes
  raw_audio_size_bytes         INT64       NOT NULL,
  cleaned_audio_size_bytes     INT64       NOT NULL,

  -- ASR cost tracking
  speechmatics_job_id          STRING,
  speechmatics_cost_estimate   FLOAT64     NOT NULL,

  -- Per-stage durations (seconds)
  transcode_duration_seconds   FLOAT64     NOT NULL,
  vad_duration_seconds         FLOAT64     NOT NULL,
  denoise_duration_seconds     FLOAT64     NOT NULL,
  asr_submit_duration_seconds  FLOAT64     NOT NULL,
  asr_wait_duration_seconds    FLOAT64     NOT NULL,
  post_process_duration_seconds FLOAT64    NOT NULL,

  -- Error tracking
  retry_count                  INT64       NOT NULL DEFAULT 0,
  error_stage                  STRING,
  error_message                STRING
)
PARTITION BY DATE(timestamp)
CLUSTER BY user_id, status;
```

**Column naming** matches the `BatchMetrics` dataclass fields exactly
(`audio_processor/observability/metrics.py`).

---

## 2. GCP Cloud Logging Sink Configuration

Create a log sink that routes batch-completion metrics from Cloud Run
stdout to BigQuery.

### Sink filter

```
resource.type="cloud_run_revision"
jsonPayload.metric_type="batch_completion"
```

### gcloud CLI

```bash
gcloud logging sinks create batch-metrics-to-bq \
  bigquery.googleapis.com/projects/PROJECT_ID/datasets/audio_pipeline \
  --log-filter='resource.type="cloud_run_revision" jsonPayload.metric_type="batch_completion"'
```

After creating the sink, grant the sink's service account the
**BigQuery Data Editor** role on the `audio_pipeline` dataset:

```bash
# Get the sink writer identity
WRITER=$(gcloud logging sinks describe batch-metrics-to-bq \
  --format='value(writerIdentity)')

# Grant BigQuery write access
bq add-iam-policy-binding \
  --member="$WRITER" \
  --role="roles/bigquery.dataEditor" \
  audio_pipeline
```

The sink auto-creates the table on first log entry. To use the explicit
schema above instead, create the table first, then create the sink with
`--use-partitioned-tables`.

---

## 3. Operational Queries

All queries reference `audio_pipeline.batch_metrics` and use column
names that match the `BatchMetrics` dataclass exactly.

### 3.1 Daily and hourly batch throughput

```sql
-- Daily throughput
SELECT
  DATE(timestamp)          AS day,
  COUNT(*)                 AS batches_total,
  COUNTIF(status = 'completed') AS batches_completed,
  COUNTIF(status = 'failed')    AS batches_failed
FROM audio_pipeline.batch_metrics
GROUP BY day
ORDER BY day DESC
LIMIT 30;

-- Hourly throughput (last 48 hours)
SELECT
  TIMESTAMP_TRUNC(timestamp, HOUR) AS hour,
  COUNT(*)                          AS batches_total,
  COUNTIF(status = 'completed')     AS batches_completed,
  COUNTIF(status = 'failed')        AS batches_failed
FROM audio_pipeline.batch_metrics
WHERE timestamp >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 48 HOUR)
GROUP BY hour
ORDER BY hour DESC;
```

### 3.2 Error rate by stage

```sql
SELECT
  error_stage,
  COUNT(*)                                          AS failure_count,
  ROUND(COUNT(*) * 100.0 / SUM(COUNT(*)) OVER(), 2) AS pct_of_failures
FROM audio_pipeline.batch_metrics
WHERE status = 'failed'
  AND error_stage IS NOT NULL
GROUP BY error_stage
ORDER BY failure_count DESC;
```

### 3.3 Rolling 30-day Speechmatics cost

```sql
-- Per-user rolling 30-day cost
SELECT
  user_id,
  SUM(speechmatics_cost_estimate) AS cost_30d,
  SUM(raw_audio_duration_seconds) / 3600.0 AS audio_hours_30d
FROM audio_pipeline.batch_metrics
WHERE status = 'completed'
  AND timestamp >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 30 DAY)
GROUP BY user_id
ORDER BY cost_30d DESC;

-- System-wide rolling 30-day cost
SELECT
  SUM(speechmatics_cost_estimate)          AS total_cost_30d,
  SUM(raw_audio_duration_seconds) / 3600.0 AS total_audio_hours_30d,
  COUNT(DISTINCT user_id)                  AS active_users
FROM audio_pipeline.batch_metrics
WHERE status = 'completed'
  AND timestamp >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 30 DAY);
```

### 3.4 R2 storage consumed per user and system-wide

```sql
-- Per-user storage
SELECT
  user_id,
  SUM(raw_audio_size_bytes)     / (1024 * 1024 * 1024) AS raw_audio_gb,
  SUM(cleaned_audio_size_bytes) / (1024 * 1024 * 1024) AS cleaned_audio_gb,
  SUM(raw_audio_size_bytes + cleaned_audio_size_bytes)
    / (1024 * 1024 * 1024)                              AS total_gb
FROM audio_pipeline.batch_metrics
WHERE status = 'completed'
GROUP BY user_id
ORDER BY total_gb DESC;

-- System-wide storage
SELECT
  SUM(raw_audio_size_bytes)     / (1024 * 1024 * 1024) AS raw_audio_gb,
  SUM(cleaned_audio_size_bytes) / (1024 * 1024 * 1024) AS cleaned_audio_gb,
  SUM(raw_audio_size_bytes + cleaned_audio_size_bytes)
    / (1024 * 1024 * 1024)                              AS total_gb
FROM audio_pipeline.batch_metrics
WHERE status = 'completed';
```

### 3.5 Per-user batch count and audio hours

```sql
SELECT
  user_id,
  COUNT(*)                                    AS batch_count,
  SUM(raw_audio_duration_seconds) / 3600.0    AS raw_audio_hours,
  SUM(speech_duration_seconds)    / 3600.0    AS speech_hours,
  ROUND(AVG(speech_ratio), 3)                 AS avg_speech_ratio
FROM audio_pipeline.batch_metrics
WHERE status = 'completed'
GROUP BY user_id
ORDER BY raw_audio_hours DESC;
```

### 3.6 Queue depth (unprocessed batches from D1)

Queue depth is not directly available from BigQuery (it lives in D1).
This query provides a proxy: batches that entered the pipeline recently
but have not yet completed.

```sql
-- Batches still in-flight (submitted but no completion metric yet)
-- Requires a D1 query for real-time accuracy. This BigQuery query
-- identifies recent failures that may need reprocessing.
SELECT
  batch_id,
  user_id,
  status,
  error_stage,
  retry_count,
  timestamp
FROM audio_pipeline.batch_metrics
WHERE status = 'failed'
  AND retry_count < 3
  AND timestamp >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 24 HOUR)
ORDER BY timestamp DESC;
```

For real-time queue depth, query the D1 `batches` table directly:

```sql
-- D1 query (run via Worker internal API or Cloudflare dashboard)
SELECT COUNT(*) AS queue_depth
FROM batches
WHERE status IN ('queued', 'processing');
```

### 3.7 Average stage duration (performance profiling)

```sql
SELECT
  ROUND(AVG(transcode_duration_seconds), 3)    AS avg_transcode_s,
  ROUND(AVG(vad_duration_seconds), 3)          AS avg_vad_s,
  ROUND(AVG(denoise_duration_seconds), 3)      AS avg_denoise_s,
  ROUND(AVG(asr_submit_duration_seconds), 3)   AS avg_asr_submit_s,
  ROUND(AVG(asr_wait_duration_seconds), 3)     AS avg_asr_wait_s,
  ROUND(AVG(post_process_duration_seconds), 3) AS avg_postprocess_s,
  ROUND(AVG(processing_wall_time_seconds), 3)  AS avg_wall_time_s,
  ROUND(AVG(queue_wait_time_seconds), 3)       AS avg_queue_wait_s
FROM audio_pipeline.batch_metrics
WHERE status = 'completed'
  AND timestamp >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 7 DAY);
```
