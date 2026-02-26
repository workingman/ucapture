package ca.dgbi.ucapture.data.remote

import android.content.Context
import android.os.Build
import android.util.Log
import androidx.hilt.work.HiltWorker
import androidx.work.BackoffPolicy
import androidx.work.Constraints
import androidx.work.CoroutineWorker
import androidx.work.Data
import androidx.work.NetworkType
import androidx.work.OneTimeWorkRequestBuilder
import androidx.work.WorkManager
import androidx.work.WorkerParameters
import ca.dgbi.ucapture.BuildConfig
import ca.dgbi.ucapture.data.local.entity.RecordingEntity
import ca.dgbi.ucapture.data.model.RecordingMetadata
import ca.dgbi.ucapture.data.repository.RecordingRepository
import ca.dgbi.ucapture.util.FileManager
import dagger.assisted.Assisted
import dagger.assisted.AssistedInject
import java.io.File
import java.util.concurrent.TimeUnit

/**
 * WorkManager worker for uploading recordings to cloud storage.
 *
 * Features:
 * - Exponential backoff for retries
 * - Network connectivity constraints
 * - MD5 verification after upload
 * - Metadata sidecar upload
 */
@HiltWorker
class UploadWorker @AssistedInject constructor(
    @Assisted appContext: Context,
    @Assisted workerParams: WorkerParameters,
    private val recordingRepository: RecordingRepository,
    private val cloudStorage: CloudStorageProvider,
    private val fileManager: FileManager
) : CoroutineWorker(appContext, workerParams) {

    companion object {
        const val KEY_RECORDING_ID = "recording_id"
        private const val MAX_RETRIES = 5
        private const val INITIAL_BACKOFF_SECONDS = 30L

        /**
         * Create a work request for uploading a recording.
         */
        fun createWorkRequest(recordingId: Long) = OneTimeWorkRequestBuilder<UploadWorker>()
            .setInputData(
                Data.Builder()
                    .putLong(KEY_RECORDING_ID, recordingId)
                    .build()
            )
            .setConstraints(
                Constraints.Builder()
                    .setRequiredNetworkType(NetworkType.CONNECTED)
                    .setRequiresBatteryNotLow(true)
                    .build()
            )
            .setBackoffCriteria(
                BackoffPolicy.EXPONENTIAL,
                INITIAL_BACKOFF_SECONDS,
                TimeUnit.SECONDS
            )
            .addTag("upload")
            .build()

        /**
         * Enqueue an upload for a recording.
         */
        fun enqueue(context: Context, recordingId: Long) {
            val workRequest = createWorkRequest(recordingId)
            WorkManager.getInstance(context)
                .enqueue(workRequest)
        }
    }

    override suspend fun doWork(): Result {
        val recordingId = inputData.getLong(KEY_RECORDING_ID, -1)
        if (recordingId == -1L) {
            return Result.failure()
        }

        Log.d("UploadWorker", "Starting upload for recording $recordingId (attempt ${runAttemptCount + 1}/$MAX_RETRIES)")

        // Check if authenticated
        if (!cloudStorage.isAuthenticated()) {
            Log.w("UploadWorker", "Not authenticated, will retry later")
            return Result.retry()
        }

        // Get recording from database
        val recording = recordingRepository.getById(recordingId)
        if (recording == null) {
            // Recording deleted - nothing to upload
            return Result.success()
        }

        // Check if already uploaded
        if (recording.uploadStatus == RecordingEntity.UploadStatus.UPLOADED) {
            return Result.success()
        }

        // Check if file exists
        val audioFile = File(recording.filePath)
        if (!audioFile.exists()) {
            recordingRepository.updateUploadStatus(recordingId, RecordingEntity.UploadStatus.FAILED)
            return Result.failure()
        }

        // Update status to uploading
        recordingRepository.updateUploadStatus(recordingId, RecordingEntity.UploadStatus.UPLOADING)

        try {
            // Get or create metadata sidecar
            val metadataFile = prepareMetadataSidecar(recording)

            // Upload files
            val uploadResult = cloudStorage.upload(
                audioFile = audioFile,
                metadataFile = metadataFile
            )

            if (!uploadResult.success) {
                Log.w("UploadWorker", "Upload failed for recording $recordingId: ${uploadResult.error}")
                handleUploadError(recordingId, uploadResult.error)
                return if (runAttemptCount < MAX_RETRIES) Result.retry() else {
                    Log.e("UploadWorker", "Max retries exceeded for recording $recordingId, marking as FAILED")
                    recordingRepository.updateUploadStatus(recordingId, RecordingEntity.UploadStatus.FAILED)
                    Result.failure()
                }
            }

            // Success — persist batch_id for transcript polling
            Log.d("UploadWorker", "Upload successful for recording $recordingId, batch_id=${uploadResult.batchId}")
            recordingRepository.updateUploadStatus(recordingId, RecordingEntity.UploadStatus.UPLOADED)
            uploadResult.batchId?.let { recordingRepository.updateBatchId(recordingId, it) }

            return Result.success()

        } catch (e: Exception) {
            Log.e("UploadWorker", "Upload exception for recording $recordingId", e)
            handleUploadError(recordingId, UploadError.ApiError(0, e.message ?: "Unknown error"))
            return if (runAttemptCount < MAX_RETRIES) Result.retry() else {
                Log.e("UploadWorker", "Max retries exceeded for recording $recordingId, marking as FAILED")
                recordingRepository.updateUploadStatus(recordingId, RecordingEntity.UploadStatus.FAILED)
                Result.failure()
            }
        }
    }

    private suspend fun prepareMetadataSidecar(recording: RecordingEntity): File? {
        val recordingWithMetadata = recordingRepository.getWithMetadata(recording.id) ?: return null

        val deviceInfo = RecordingMetadata.DeviceInfo(
            model = Build.MODEL ?: "unknown",
            osVersion = "Android ${Build.VERSION.RELEASE ?: "unknown"}",
            appVersion = BuildConfig.VERSION_NAME ?: "unknown"
        )

        val metadata = RecordingMetadata.fromEntities(
            recording = recordingWithMetadata.recording,
            locationSamples = recordingWithMetadata.locationSamples,
            calendarEvents = recordingWithMetadata.calendarEvents,
            deviceInfo = deviceInfo
        )

        return fileManager.writeMetadataSidecar(recording.filePath, metadata)
    }

    private suspend fun handleUploadError(recordingId: Long, error: UploadError?) {
        when (error) {
            is UploadError.NotAuthenticated -> {
                // Keep as pending - user needs to sign in
                recordingRepository.updateUploadStatus(recordingId, RecordingEntity.UploadStatus.PENDING)
            }
            is UploadError.QuotaExceeded -> {
                // Permanent failure - no point retrying
                recordingRepository.updateUploadStatus(recordingId, RecordingEntity.UploadStatus.FAILED)
            }
            else -> {
                // Transient error - mark as pending for retry
                recordingRepository.updateUploadStatus(recordingId, RecordingEntity.UploadStatus.PENDING)
            }
        }
    }
}
