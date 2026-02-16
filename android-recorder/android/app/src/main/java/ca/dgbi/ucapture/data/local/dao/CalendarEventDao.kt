package ca.dgbi.ucapture.data.local.dao

import androidx.room.Dao
import androidx.room.Insert
import androidx.room.Query
import ca.dgbi.ucapture.data.local.entity.CalendarEventEntity

@Dao
interface CalendarEventDao {

    @Insert
    suspend fun insert(event: CalendarEventEntity): Long

    @Insert
    suspend fun insertAll(events: List<CalendarEventEntity>)

    @Query("SELECT * FROM calendar_events WHERE recording_id = :recordingId ORDER BY start_time ASC")
    suspend fun getByRecordingId(recordingId: Long): List<CalendarEventEntity>

    @Query("DELETE FROM calendar_events WHERE recording_id = :recordingId")
    suspend fun deleteByRecordingId(recordingId: Long)

    @Query("SELECT COUNT(*) FROM calendar_events WHERE recording_id = :recordingId")
    suspend fun getCountByRecordingId(recordingId: Long): Int
}
