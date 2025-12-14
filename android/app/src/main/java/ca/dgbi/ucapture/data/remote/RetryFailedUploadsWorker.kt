package ca.dgbi.ucapture.data.remote

import android.content.Context
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

        failedRecordings.forEach { recording ->
            recordingRepository.updateUploadStatus(
                recording.id,
                RecordingEntity.UploadStatus.PENDING
            )
            UploadWorker.enqueue(applicationContext, recording.id)
        }

        return Result.success()
    }
}
