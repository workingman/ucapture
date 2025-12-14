package ca.dgbi.ucapture.data.repository

import ca.dgbi.ucapture.data.local.dao.CalendarEventDao
import ca.dgbi.ucapture.data.local.dao.LocationSampleDao
import ca.dgbi.ucapture.data.local.entity.CalendarEventEntity
import ca.dgbi.ucapture.data.local.entity.LocationSampleEntity
import javax.inject.Inject
import javax.inject.Singleton

/**
 * Repository for accessing recording metadata (location samples and calendar events).
 *
 * Provides direct access to metadata without loading the full recording.
 */
@Singleton
class MetadataRepository @Inject constructor(
    private val locationSampleDao: LocationSampleDao,
    private val calendarEventDao: CalendarEventDao
) {
    suspend fun getLocationSamplesForRecording(recordingId: Long): List<LocationSampleEntity> =
        locationSampleDao.getByRecordingId(recordingId)

    suspend fun getCalendarEventsForRecording(recordingId: Long): List<CalendarEventEntity> =
        calendarEventDao.getByRecordingId(recordingId)

    suspend fun getLocationSampleCount(recordingId: Long): Int =
        locationSampleDao.getCountByRecordingId(recordingId)

    suspend fun getCalendarEventCount(recordingId: Long): Int =
        calendarEventDao.getCountByRecordingId(recordingId)
}
