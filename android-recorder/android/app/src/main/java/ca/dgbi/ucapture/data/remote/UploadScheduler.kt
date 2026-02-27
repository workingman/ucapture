package ca.dgbi.ucapture.data.remote

import android.content.Context
import androidx.work.Constraints
import androidx.work.ExistingPeriodicWorkPolicy
import androidx.work.NetworkType
import androidx.work.PeriodicWorkRequestBuilder
import androidx.work.WorkManager
import ca.dgbi.ucapture.data.local.entity.RecordingEntity
import ca.dgbi.ucapture.data.repository.RecordingRepository
import ca.dgbi.ucapture.util.RetentionManager
import dagger.hilt.android.qualifiers.ApplicationContext
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.launch
import java.util.concurrent.TimeUnit
import javax.inject.Inject
import javax.inject.Singleton

/**
 * Schedules and manages upload workers.
 *
 * Handles:
 * - Individual upload scheduling
 * - Periodic retry of failed uploads
 * - Bulk upload scheduling on app start
 */
@Singleton
class UploadScheduler @Inject constructor(
    @ApplicationContext private val context: Context,
    private val recordingRepository: RecordingRepository,
    private val retentionManager: RetentionManager
) {
    companion object {
        private const val RETRY_WORK_NAME = "retry_failed_uploads"
        private const val RETRY_INTERVAL_HOURS = 1L
        private const val CLEANUP_WORK_NAME = "retention_cleanup"
        private const val CLEANUP_INTERVAL_MINUTES = 30L
    }

    private val workManager = WorkManager.getInstance(context)

    /**
     * Schedule upload for a single recording.
     */
    fun scheduleUpload(recordingId: Long) {
        UploadWorker.enqueue(context, recordingId)
    }

    /**
     * Schedule uploads for all pending recordings.
     * Call this on app startup.
     */
    fun schedulePendingUploads(scope: CoroutineScope) {
        scope.launch {
            val pendingRecordings = recordingRepository.getPendingUploads()
            pendingRecordings.forEach { recording ->
                scheduleUpload(recording.id)
            }
        }
    }

    /**
     * Retry failed uploads.
     */
    fun retryFailedUploads(scope: CoroutineScope) {
        scope.launch {
            val failedRecordings = recordingRepository.getFailedUploads()
            failedRecordings.forEach { recording ->
                // Reset to pending and reschedule
                recordingRepository.updateUploadStatus(
                    recording.id,
                    RecordingEntity.UploadStatus.PENDING
                )
                scheduleUpload(recording.id)
            }
        }
    }

    /**
     * Set up periodic work to retry failed uploads.
     */
    fun setupPeriodicRetry() {
        val constraints = Constraints.Builder()
            .setRequiredNetworkType(NetworkType.CONNECTED)
            .setRequiresBatteryNotLow(true)
            .build()

        val retryWork = PeriodicWorkRequestBuilder<RetryFailedUploadsWorker>(
            RETRY_INTERVAL_HOURS,
            TimeUnit.HOURS
        )
            .setConstraints(constraints)
            .build()

        workManager.enqueueUniquePeriodicWork(
            RETRY_WORK_NAME,
            ExistingPeriodicWorkPolicy.KEEP,
            retryWork
        )
    }

    /**
     * Set up periodic retention cleanup to delete local files after upload + retention period.
     */
    fun setupPeriodicCleanup() {
        val cleanupWork = PeriodicWorkRequestBuilder<RetentionCleanupWorker>(
            CLEANUP_INTERVAL_MINUTES,
            TimeUnit.MINUTES
        ).build()

        workManager.enqueueUniquePeriodicWork(
            CLEANUP_WORK_NAME,
            ExistingPeriodicWorkPolicy.KEEP,
            cleanupWork
        )
    }

    /**
     * Run a one-shot retention cleanup on app startup.
     */
    fun runStartupCleanup(scope: CoroutineScope) {
        scope.launch {
            val deletedCount = retentionManager.cleanupOldRecordings()
            if (deletedCount > 0) {
                android.util.Log.d("UploadScheduler", "Startup cleanup: deleted $deletedCount old recordings")
            }
        }
    }

    /**
     * Cancel all pending upload work.
     */
    fun cancelAllUploads() {
        workManager.cancelAllWorkByTag("upload")
    }

    /**
     * Cancel a specific upload.
     */
    fun cancelUpload(recordingId: Long) {
        workManager.cancelAllWorkByTag("upload_$recordingId")
    }
}
