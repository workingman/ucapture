package ca.dgbi.ucapture.data.local.entity

import androidx.room.ColumnInfo
import androidx.room.Entity
import androidx.room.Index
import androidx.room.PrimaryKey

/**
 * Room entity representing a recording chunk.
 *
 * Each recording chunk is a single audio file with associated metadata.
 * Multiple chunks may belong to the same recording session.
 */
@Entity(
    tableName = "recordings",
    indices = [
        Index("session_id"),
        Index("start_time"),
        Index("upload_status")
    ]
)
data class RecordingEntity(
    @PrimaryKey(autoGenerate = true)
    val id: Long = 0,

    @ColumnInfo(name = "session_id")
    val sessionId: String,

    @ColumnInfo(name = "chunk_number")
    val chunkNumber: Int,

    @ColumnInfo(name = "file_path")
    val filePath: String,

    @ColumnInfo(name = "start_time")
    val startTimeEpochMilli: Long,

    @ColumnInfo(name = "end_time")
    val endTimeEpochMilli: Long,

    @ColumnInfo(name = "timezone_id")
    val timezoneId: String,

    @ColumnInfo(name = "duration_seconds")
    val durationSeconds: Long,

    @ColumnInfo(name = "file_size_bytes")
    val fileSizeBytes: Long,

    @ColumnInfo(name = "md5_hash")
    val md5Hash: String? = null,

    @ColumnInfo(name = "upload_status")
    val uploadStatus: String = UploadStatus.PENDING,

    /** Cloudflare Worker batch_id returned on successful upload (null until uploaded). */
    @ColumnInfo(name = "batch_id")
    val batchId: String? = null,

    @ColumnInfo(name = "created_at")
    val createdAt: Long = System.currentTimeMillis()
) {
    // TODO: Add CONFIRMED status once backend polling is implemented.
    //  CONFIRMED = backend has verified durable storage of this recording.
    //  RetentionManager should require CONFIRMED (not just UPLOADED) before
    //  deleting local files. For dev/test, UPLOADED is treated as sufficient.
    object UploadStatus {
        const val PENDING = "pending"
        const val UPLOADING = "uploading"
        const val UPLOADED = "uploaded"
        const val FAILED = "failed"
    }
}
