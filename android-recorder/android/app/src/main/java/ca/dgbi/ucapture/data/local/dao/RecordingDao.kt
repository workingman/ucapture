package ca.dgbi.ucapture.data.local.dao

import androidx.room.Dao
import androidx.room.Delete
import androidx.room.Insert
import androidx.room.Query
import androidx.room.Transaction
import androidx.room.Update
import ca.dgbi.ucapture.data.local.entity.RecordingEntity
import ca.dgbi.ucapture.data.local.relation.RecordingWithMetadata
import kotlinx.coroutines.flow.Flow

@Dao
interface RecordingDao {

    @Insert
    suspend fun insert(recording: RecordingEntity): Long

    @Update
    suspend fun update(recording: RecordingEntity)

    @Delete
    suspend fun delete(recording: RecordingEntity)

    @Query("SELECT * FROM recordings WHERE id = :id")
    suspend fun getById(id: Long): RecordingEntity?

    @Query("SELECT * FROM recordings WHERE file_path = :filePath")
    suspend fun getByFilePath(filePath: String): RecordingEntity?

    @Query("SELECT * FROM recordings ORDER BY start_time DESC")
    fun getAllOrderedByTime(): Flow<List<RecordingEntity>>

    @Query("SELECT * FROM recordings WHERE upload_status = :status")
    suspend fun getByUploadStatus(status: String): List<RecordingEntity>

    @Query("SELECT * FROM recordings WHERE end_time < :beforeEpochMilli AND upload_status = 'uploaded' ORDER BY end_time ASC")
    suspend fun getUploadedBefore(beforeEpochMilli: Long): List<RecordingEntity>

    @Query("UPDATE recordings SET upload_status = :status WHERE id = :id")
    suspend fun updateUploadStatus(id: Long, status: String)

    @Query("UPDATE recordings SET md5_hash = :hash WHERE id = :id")
    suspend fun updateMd5Hash(id: Long, hash: String)

    @Query("UPDATE recordings SET batch_id = :batchId WHERE id = :id")
    suspend fun updateBatchId(id: Long, batchId: String)

    @Query("SELECT SUM(file_size_bytes) FROM recordings")
    suspend fun getTotalStorageUsed(): Long?

    @Query("DELETE FROM recordings WHERE id IN (:ids)")
    suspend fun deleteByIds(ids: List<Long>)

    @Query("SELECT COUNT(*) FROM recordings")
    suspend fun getCount(): Int

    @Transaction
    @Query("SELECT * FROM recordings WHERE id = :id")
    suspend fun getWithMetadata(id: Long): RecordingWithMetadata?

    @Transaction
    @Query("SELECT * FROM recordings ORDER BY start_time DESC")
    fun getAllWithMetadata(): Flow<List<RecordingWithMetadata>>
}
