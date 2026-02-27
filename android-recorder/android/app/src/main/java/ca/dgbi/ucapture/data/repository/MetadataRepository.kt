package ca.dgbi.ucapture.data.repository

import ca.dgbi.ucapture.data.local.dao.LocationSampleDao
import ca.dgbi.ucapture.data.local.entity.LocationSampleEntity
import javax.inject.Inject
import javax.inject.Singleton

/**
 * Repository for accessing recording metadata (location samples).
 *
 * Provides direct access to metadata without loading the full recording.
 */
@Singleton
class MetadataRepository @Inject constructor(
    private val locationSampleDao: LocationSampleDao
) {
    suspend fun getLocationSamplesForRecording(recordingId: Long): List<LocationSampleEntity> =
        locationSampleDao.getByRecordingId(recordingId)

    suspend fun getLocationSampleCount(recordingId: Long): Int =
        locationSampleDao.getCountByRecordingId(recordingId)
}
