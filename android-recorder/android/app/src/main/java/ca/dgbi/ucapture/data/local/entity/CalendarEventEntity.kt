package ca.dgbi.ucapture.data.local.entity

import androidx.room.ColumnInfo
import androidx.room.Entity
import androidx.room.ForeignKey
import androidx.room.Index
import androidx.room.PrimaryKey

/**
 * Room entity representing a calendar event that overlaps with a recording.
 *
 * Events are automatically deleted when their parent recording is deleted.
 */
@Entity(
    tableName = "calendar_events",
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
        Index("event_id")
    ]
)
data class CalendarEventEntity(
    @PrimaryKey(autoGenerate = true)
    val id: Long = 0,

    @ColumnInfo(name = "recording_id")
    val recordingId: Long,

    @ColumnInfo(name = "event_id")
    val eventId: Long,

    val title: String,

    val description: String?,

    val location: String?,

    @ColumnInfo(name = "start_time")
    val startTimeEpochMilli: Long,

    @ColumnInfo(name = "end_time")
    val endTimeEpochMilli: Long,

    @ColumnInfo(name = "attendees_json")
    val attendeesJson: String,

    @ColumnInfo(name = "calendar_name")
    val calendarName: String,

    @ColumnInfo(name = "is_all_day")
    val isAllDay: Boolean
)
