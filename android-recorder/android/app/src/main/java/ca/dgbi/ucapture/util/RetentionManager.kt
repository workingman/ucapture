package ca.dgbi.ucapture.util

import ca.dgbi.ucapture.data.repository.RecordingRepository
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import java.time.Instant
import javax.inject.Inject
import javax.inject.Singleton

/**
 * Manages retention policy for local recordings.
 *
 * Handles cleanup of old recordings that have been uploaded to cloud storage.
 *
 * Safety model: files are only deleted after UPLOADED status + retention period elapsed.
 * Future: require CONFIRMED status from a backend poll (verifying durable storage)
 * before deleting local files. For dev/test, UPLOADED is treated as sufficient.
 */
@Singleton
class RetentionManager @Inject constructor(
    private val recordingRepository: RecordingRepository,
    private val fileManager: FileManager
) {
    companion object {
        const val DEFAULT_RETENTION_MINUTES = 30L
        const val MIN_RETENTION_MINUTES = 5L
        const val MAX_RETENTION_MINUTES = 24 * 60L  // 24 hours
    }

    /**
     * Clean up recordings that have been uploaded and exceed retention period.
     *
     * Only deletes recordings where:
     * 1. Upload status is "uploaded"
     * 2. Recording end time is older than retention period
     *
     * @param retentionMinutes How long to keep uploaded recordings
     * @return Number of recordings deleted
     */
    suspend fun cleanupOldRecordings(
        retentionMinutes: Long = DEFAULT_RETENTION_MINUTES
    ): Int = withContext(Dispatchers.IO) {
        val effectiveRetention = retentionMinutes.coerceIn(
            MIN_RETENTION_MINUTES,
            MAX_RETENTION_MINUTES
        )

        val cutoffTime = Instant.now().minusSeconds(effectiveRetention * 60)
        val recordingsToDelete = recordingRepository.getUploadedBefore(cutoffTime)

        var deletedCount = 0
        for (recording in recordingsToDelete) {
            try {
                val filesDeleted = fileManager.deleteRecordingFiles(recording.filePath)

                if (filesDeleted) {
                    recordingRepository.delete(recording)
                    deletedCount++
                }
            } catch (e: Exception) {
                // Log but continue with other deletions
            }
        }

        deletedCount
    }

    /**
     * Force cleanup when storage is critically low.
     *
     * Deletes oldest uploaded recordings until storage is above critical threshold.
     *
     * @return Number of recordings deleted
     */
    suspend fun emergencyCleanup(): Int = withContext(Dispatchers.IO) {
        var deletedCount = 0

        while (fileManager.getStorageStatus() == FileManager.StorageStatus.CRITICAL) {
            val oldestUploaded = recordingRepository
                .getUploadedBefore(Instant.now())
                .minByOrNull { it.startTimeEpochMilli }
                ?: break

            val filesDeleted = fileManager.deleteRecordingFiles(oldestUploaded.filePath)
            if (filesDeleted) {
                recordingRepository.delete(oldestUploaded)
                deletedCount++
            } else {
                break  // Can't delete files, stop to avoid infinite loop
            }
        }

        deletedCount
    }

    /**
     * Get statistics about recordings and storage.
     */
    suspend fun getRetentionStats(): RetentionStats {
        val totalUsedBytes = recordingRepository.getTotalStorageUsed()
        val pendingCount = recordingRepository.getPendingUploads().size
        val failedCount = recordingRepository.getFailedUploads().size

        return RetentionStats(
            totalStorageUsedBytes = totalUsedBytes,
            pendingUploadCount = pendingCount,
            failedUploadCount = failedCount,
            availableStorageBytes = fileManager.getAvailableStorageBytes(),
            storageStatus = fileManager.getStorageStatus()
        )
    }

    data class RetentionStats(
        val totalStorageUsedBytes: Long,
        val pendingUploadCount: Int,
        val failedUploadCount: Int,
        val availableStorageBytes: Long,
        val storageStatus: FileManager.StorageStatus
    )
}
