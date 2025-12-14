package ca.dgbi.ucapture.data.local.entity

import androidx.room.ColumnInfo
import androidx.room.Entity
import androidx.room.ForeignKey
import androidx.room.Index
import androidx.room.PrimaryKey

/**
 * Room entity representing a GPS location sample.
 *
 * Each sample belongs to a recording and captures location at a point in time.
 * Samples are automatically deleted when their parent recording is deleted.
 */
@Entity(
    tableName = "location_samples",
    foreignKeys = [
        ForeignKey(
            entity = RecordingEntity::class,
            parentColumns = ["id"],
            childColumns = ["recording_id"],
            onDelete = ForeignKey.CASCADE
        )
    ],
    indices = [
        Index("recording_id"),
        Index("timestamp")
    ]
)
data class LocationSampleEntity(
    @PrimaryKey(autoGenerate = true)
    val id: Long = 0,

    @ColumnInfo(name = "recording_id")
    val recordingId: Long,

    val latitude: Double,

    val longitude: Double,

    val altitude: Double?,

    val accuracy: Float,

    val speed: Float?,

    val bearing: Float?,

    @ColumnInfo(name = "timestamp")
    val timestampEpochMilli: Long,

    val provider: String
)
