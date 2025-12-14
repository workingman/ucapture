package ca.dgbi.ucapture.data.remote

import android.content.Context
import androidx.hilt.work.HiltWorker
import androidx.work.BackoffPolicy
import androidx.work.Constraints
import androidx.work.CoroutineWorker
import androidx.work.Data
import androidx.work.NetworkType
import androidx.work.OneTimeWorkRequestBuilder
import androidx.work.WorkManager
import androidx.work.WorkerParameters
import ca.dgbi.ucapture.data.local.entity.RecordingEntity
import ca.dgbi.ucapture.data.model.RecordingMetadata
import ca.dgbi.ucapture.data.repository.RecordingRepository
import ca.dgbi.ucapture.util.FileManager
import ca.dgbi.ucapture.util.HashUtil
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

        // Check if authenticated
        if (!cloudStorage.isAuthenticated()) {
            // Not authenticated - retry later (user needs to sign in)
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
                handleUploadError(recordingId, uploadResult.error)
                return if (runAttemptCount < MAX_RETRIES) Result.retry() else Result.failure()
            }

            // Verify upload if we have MD5 hash
            val audioFileId = uploadResult.audioFileId!!
            val md5Hash = recording.md5Hash ?: HashUtil.md5(audioFile)

            if (md5Hash != null) {
                val verified = cloudStorage.verifyUpload(audioFileId, md5Hash)
                if (!verified) {
                    // Verification failed - retry
                    recordingRepository.updateUploadStatus(
                        recordingId,
                        RecordingEntity.UploadStatus.PENDING
                    )
                    return Result.retry()
                }
            }

            // Success!
            recordingRepository.updateUploadStatus(recordingId, RecordingEntity.UploadStatus.UPLOADED)

            // Update MD5 hash if we calculated it
            if (recording.md5Hash == null && md5Hash != null) {
                recordingRepository.updateMd5Hash(recordingId, md5Hash)
            }

            return Result.success()

        } catch (e: Exception) {
            handleUploadError(recordingId, UploadError.ApiError(0, e.message ?: "Unknown error"))
            return if (runAttemptCount < MAX_RETRIES) Result.retry() else Result.failure()
        }
    }

    private suspend fun prepareMetadataSidecar(recording: RecordingEntity): File? {
        val recordingWithMetadata = recordingRepository.getWithMetadata(recording.id)
        if (recordingWithMetadata == null) return null

        val metadata = RecordingMetadata.fromEntities(
            recording = recordingWithMetadata.recording,
            locationSamples = recordingWithMetadata.locationSamples,
            calendarEvents = recordingWithMetadata.calendarEvents
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
