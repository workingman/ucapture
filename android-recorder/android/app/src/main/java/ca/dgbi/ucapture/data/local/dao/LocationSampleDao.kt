package ca.dgbi.ucapture.data.local.dao

import androidx.room.Dao
import androidx.room.Insert
import androidx.room.Query
import ca.dgbi.ucapture.data.local.entity.LocationSampleEntity

@Dao
interface LocationSampleDao {

    @Insert
    suspend fun insert(sample: LocationSampleEntity): Long

    @Insert
    suspend fun insertAll(samples: List<LocationSampleEntity>)

    @Query("SELECT * FROM location_samples WHERE recording_id = :recordingId ORDER BY timestamp ASC")
    suspend fun getByRecordingId(recordingId: Long): List<LocationSampleEntity>

    @Query("DELETE FROM location_samples WHERE recording_id = :recordingId")
    suspend fun deleteByRecordingId(recordingId: Long)

    @Query("SELECT COUNT(*) FROM location_samples WHERE recording_id = :recordingId")
    suspend fun getCountByRecordingId(recordingId: Long): Int
}
