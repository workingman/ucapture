package ca.dgbi.ucapture.data.remote

import android.content.Context
import android.util.Log
import androidx.hilt.work.HiltWorker
import androidx.work.CoroutineWorker
import androidx.work.WorkerParameters
import ca.dgbi.ucapture.data.local.entity.RecordingEntity
import ca.dgbi.ucapture.data.repository.RecordingRepository
import dagger.assisted.Assisted
import dagger.assisted.AssistedInject
import java.time.Instant

/**
 * Periodic worker that retries failed uploads and recovers stuck-UPLOADING recordings.
 *
 * Runs hourly to:
 * - Reschedule any uploads that previously failed
 * - Reset recordings stuck in UPLOADING state for over 15 minutes back to PENDING
 */
@HiltWorker
class RetryFailedUploadsWorker @AssistedInject constructor(
    @Assisted appContext: Context,
    @Assisted workerParams: WorkerParameters,
    private val recordingRepository: RecordingRepository
) : CoroutineWorker(appContext, workerParams) {

    companion object {
        private const val STUCK_UPLOADING_THRESHOLD_MINUTES = 15L
    }

    override suspend fun doWork(): Result {
        recoverStuckUploading()
        retryFailed()
        return Result.success()
    }

    private suspend fun recoverStuckUploading() {
        val cutoff = Instant.now().minusSeconds(STUCK_UPLOADING_THRESHOLD_MINUTES * 60)
        val stuckRecordings = recordingRepository.getStuckUploading(cutoff)
        if (stuckRecordings.isNotEmpty()) {
            Log.d("RetryFailedUploads", "Found ${stuckRecordings.size} stuck-UPLOADING recordings, resetting to PENDING")
        }
        stuckRecordings.forEach { recording ->
            recordingRepository.updateUploadStatus(recording.id, RecordingEntity.UploadStatus.PENDING)
            UploadWorker.enqueue(applicationContext, recording.id)
        }
    }

    private suspend fun retryFailed() {
        val failedRecordings = recordingRepository.getFailedUploads()
        Log.d("RetryFailedUploads", "Found ${failedRecordings.size} failed uploads to retry")

        failedRecordings.forEach { recording ->
            Log.d("RetryFailedUploads", "Re-queuing recording ${recording.id}: ${recording.filePath}")
            recordingRepository.updateUploadStatus(
                recording.id,
                RecordingEntity.UploadStatus.PENDING
            )
            UploadWorker.enqueue(applicationContext, recording.id)
        }
    }
}
