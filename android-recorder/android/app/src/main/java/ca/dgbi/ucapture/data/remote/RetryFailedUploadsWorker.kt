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

/**
 * Periodic worker that retries failed uploads.
 *
 * Runs hourly to reschedule any uploads that previously failed.
 */
@HiltWorker
class RetryFailedUploadsWorker @AssistedInject constructor(
    @Assisted appContext: Context,
    @Assisted workerParams: WorkerParameters,
    private val recordingRepository: RecordingRepository
) : CoroutineWorker(appContext, workerParams) {

    override suspend fun doWork(): Result {
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

        return Result.success()
    }
}
