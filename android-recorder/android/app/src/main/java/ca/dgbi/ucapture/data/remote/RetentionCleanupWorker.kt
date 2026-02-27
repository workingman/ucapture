package ca.dgbi.ucapture.data.remote

import android.content.Context
import android.util.Log
import androidx.hilt.work.HiltWorker
import androidx.work.CoroutineWorker
import androidx.work.WorkerParameters
import ca.dgbi.ucapture.util.RetentionManager
import dagger.assisted.Assisted
import dagger.assisted.AssistedInject

/**
 * Periodic worker that cleans up local audio files after they've been uploaded
 * and the retention period has elapsed.
 */
@HiltWorker
class RetentionCleanupWorker @AssistedInject constructor(
    @Assisted appContext: Context,
    @Assisted workerParams: WorkerParameters,
    private val retentionManager: RetentionManager
) : CoroutineWorker(appContext, workerParams) {

    override suspend fun doWork(): Result {
        val deletedCount = retentionManager.cleanupOldRecordings()
        Log.d("RetentionCleanup", "Cleaned up $deletedCount old recordings")
        return Result.success()
    }
}
