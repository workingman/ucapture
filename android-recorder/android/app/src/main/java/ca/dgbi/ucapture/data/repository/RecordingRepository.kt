package ca.dgbi.ucapture.data.repository

import ca.dgbi.ucapture.data.local.dao.LocationSampleDao
import ca.dgbi.ucapture.data.local.dao.RecordingDao
import ca.dgbi.ucapture.data.local.entity.LocationSampleEntity
import ca.dgbi.ucapture.data.local.entity.RecordingEntity
import ca.dgbi.ucapture.data.local.relation.RecordingWithMetadata
import ca.dgbi.ucapture.service.ChunkManager
import ca.dgbi.ucapture.service.metadata.LocationSample
import kotlinx.coroutines.flow.Flow
import java.time.Duration
import java.time.Instant
import javax.inject.Inject
import javax.inject.Singleton

/**
 * Repository for managing recording data.
 *
 * Provides an abstraction layer over Room DAOs and handles conversion between
 * service-layer types and Room entities.
 */
@Singleton
class RecordingRepository @Inject constructor(
    private val recordingDao: RecordingDao,
    private val locationSampleDao: LocationSampleDao
) {
    val allRecordings: Flow<List<RecordingEntity>> = recordingDao.getAllOrderedByTime()

    val allRecordingsWithMetadata: Flow<List<RecordingWithMetadata>> =
        recordingDao.getAllWithMetadata()

    /**
     * Save a completed chunk with its associated metadata.
     *
     * Converts service-layer types to Room entities and persists them.
     *
     * @param chunk The completed audio chunk
     * @param locationSamples Location samples collected during this chunk
     * @return The database ID of the saved recording
     */
    suspend fun saveCompletedChunk(
        chunk: ChunkManager.CompletedChunk,
        locationSamples: List<LocationSample>
    ): Long {
        val recordingEntity = RecordingEntity(
            sessionId = chunk.sessionId,
            chunkNumber = chunk.chunkNumber,
            filePath = chunk.file.absolutePath,
            startTimeEpochMilli = chunk.startTime.toInstant().toEpochMilli(),
            endTimeEpochMilli = chunk.endTime.toInstant().toEpochMilli(),
            timezoneId = chunk.startTime.zone.id,
            durationSeconds = Duration.between(chunk.startTime, chunk.endTime).seconds,
            fileSizeBytes = chunk.file.length()
        )

        val recordingId = recordingDao.insert(recordingEntity)

        if (locationSamples.isNotEmpty()) {
            val locationEntities = locationSamples.map { it.toEntity(recordingId) }
            locationSampleDao.insertAll(locationEntities)
        }

        return recordingId
    }

    suspend fun insertRecording(entity: RecordingEntity): Long =
        recordingDao.insert(entity)

    suspend fun getById(id: Long): RecordingEntity? = recordingDao.getById(id)

    suspend fun getByFilePath(filePath: String): RecordingEntity? =
        recordingDao.getByFilePath(filePath)

    suspend fun getWithMetadata(id: Long): RecordingWithMetadata? =
        recordingDao.getWithMetadata(id)

    suspend fun updateUploadStatus(id: Long, status: String) =
        recordingDao.updateUploadStatus(id, status)

    suspend fun updateMd5Hash(id: Long, hash: String) =
        recordingDao.updateMd5Hash(id, hash)

    suspend fun updateBatchId(id: Long, batchId: String) =
        recordingDao.updateBatchId(id, batchId)

    suspend fun getPendingUploads(): List<RecordingEntity> =
        recordingDao.getByUploadStatus(RecordingEntity.UploadStatus.PENDING)

    suspend fun getFailedUploads(): List<RecordingEntity> =
        recordingDao.getByUploadStatus(RecordingEntity.UploadStatus.FAILED)

    suspend fun getStuckUploading(cutoff: Instant): List<RecordingEntity> =
        recordingDao.getStuckUploading(cutoff.toEpochMilli())

    suspend fun getUploadedBefore(beforeTime: Instant): List<RecordingEntity> =
        recordingDao.getUploadedBefore(beforeTime.toEpochMilli())

    suspend fun getTotalStorageUsed(): Long = recordingDao.getTotalStorageUsed() ?: 0L

    suspend fun getCount(): Int = recordingDao.getCount()

    suspend fun delete(recording: RecordingEntity) {
        recordingDao.delete(recording)
    }

    suspend fun deleteByIds(ids: List<Long>) = recordingDao.deleteByIds(ids)

    private fun LocationSample.toEntity(recordingId: Long) = LocationSampleEntity(
        recordingId = recordingId,
        latitude = latitude,
        longitude = longitude,
        altitude = altitude,
        accuracy = accuracy,
        speed = speed,
        bearing = bearing,
        timestampEpochMilli = timestamp.toEpochMilli(),
        provider = provider
    )
}
