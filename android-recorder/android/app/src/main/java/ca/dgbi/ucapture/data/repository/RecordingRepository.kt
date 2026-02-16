package ca.dgbi.ucapture.data.repository

import ca.dgbi.ucapture.data.local.dao.CalendarEventDao
import ca.dgbi.ucapture.data.local.dao.LocationSampleDao
import ca.dgbi.ucapture.data.local.dao.RecordingDao
import ca.dgbi.ucapture.data.local.entity.CalendarEventEntity
import ca.dgbi.ucapture.data.local.entity.LocationSampleEntity
import ca.dgbi.ucapture.data.local.entity.RecordingEntity
import ca.dgbi.ucapture.data.local.relation.RecordingWithMetadata
import ca.dgbi.ucapture.service.ChunkManager
import ca.dgbi.ucapture.service.metadata.CalendarEvent
import ca.dgbi.ucapture.service.metadata.LocationSample
import com.google.gson.Gson
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
    private val locationSampleDao: LocationSampleDao,
    private val calendarEventDao: CalendarEventDao
) {
    private val gson = Gson()

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
     * @param calendarEvents Calendar events that overlap with this chunk
     * @return The database ID of the saved recording
     */
    suspend fun saveCompletedChunk(
        chunk: ChunkManager.CompletedChunk,
        locationSamples: List<LocationSample>,
        calendarEvents: List<CalendarEvent>
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

        if (calendarEvents.isNotEmpty()) {
            val eventEntities = calendarEvents.map { it.toEntity(recordingId) }
            calendarEventDao.insertAll(eventEntities)
        }

        return recordingId
    }

    suspend fun getById(id: Long): RecordingEntity? = recordingDao.getById(id)

    suspend fun getByFilePath(filePath: String): RecordingEntity? =
        recordingDao.getByFilePath(filePath)

    suspend fun getWithMetadata(id: Long): RecordingWithMetadata? =
        recordingDao.getWithMetadata(id)

    suspend fun updateUploadStatus(id: Long, status: String) =
        recordingDao.updateUploadStatus(id, status)

    suspend fun updateMd5Hash(id: Long, hash: String) =
        recordingDao.updateMd5Hash(id, hash)

    suspend fun getPendingUploads(): List<RecordingEntity> =
        recordingDao.getByUploadStatus(RecordingEntity.UploadStatus.PENDING)

    suspend fun getFailedUploads(): List<RecordingEntity> =
        recordingDao.getByUploadStatus(RecordingEntity.UploadStatus.FAILED)

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

    private fun CalendarEvent.toEntity(recordingId: Long) = CalendarEventEntity(
        recordingId = recordingId,
        eventId = eventId,
        title = title,
        description = description,
        location = location,
        startTimeEpochMilli = startTime.toEpochMilli(),
        endTimeEpochMilli = endTime.toEpochMilli(),
        attendeesJson = gson.toJson(attendees),
        calendarName = calendarName,
        isAllDay = isAllDay
    )
}
