package ca.dgbi.ucapture.data.remote

import android.content.Context
import androidx.work.ListenableWorker
import androidx.work.WorkerParameters
import ca.dgbi.ucapture.data.local.entity.RecordingEntity
import ca.dgbi.ucapture.data.local.relation.RecordingWithMetadata
import ca.dgbi.ucapture.data.repository.RecordingRepository
import ca.dgbi.ucapture.util.FileManager
import io.mockk.coEvery
import io.mockk.coVerify
import io.mockk.every
import io.mockk.mockk
import kotlinx.coroutines.test.runTest
import org.junit.Assert.assertEquals
import org.junit.Before
import org.junit.Test
import java.io.File

class UploadWorkerTest {

    private lateinit var context: Context
    private lateinit var workerParams: WorkerParameters
    private lateinit var recordingRepository: RecordingRepository
    private lateinit var cloudStorage: CloudStorageProvider
    private lateinit var fileManager: FileManager
    private lateinit var worker: UploadWorker

    @Before
    fun setUp() {
        context = mockk(relaxed = true)
        workerParams = mockk(relaxed = true)
        recordingRepository = mockk(relaxed = true)
        cloudStorage = mockk(relaxed = true)
        fileManager = mockk(relaxed = true)
    }

    private fun createWorker(recordingId: Long = 1L): UploadWorker {
        every { workerParams.inputData.getLong(UploadWorker.KEY_RECORDING_ID, -1) } returns recordingId
        return UploadWorker(context, workerParams, recordingRepository, cloudStorage, fileManager)
    }

    @Test
    fun `doWork returns failure when recording ID is invalid`() = runTest {
        val worker = createWorker(recordingId = -1L)

        val result = worker.doWork()

        assertEquals(ListenableWorker.Result.failure(), result)
    }

    @Test
    fun `doWork returns retry when not authenticated`() = runTest {
        val worker = createWorker()
        coEvery { cloudStorage.isAuthenticated() } returns false

        val result = worker.doWork()

        assertEquals(ListenableWorker.Result.retry(), result)
    }

    @Test
    fun `doWork returns success when recording does not exist`() = runTest {
        val worker = createWorker()
        coEvery { cloudStorage.isAuthenticated() } returns true
        coEvery { recordingRepository.getById(1L) } returns null

        val result = worker.doWork()

        assertEquals(ListenableWorker.Result.success(), result)
    }

    @Test
    fun `doWork returns success when recording already uploaded`() = runTest {
        val worker = createWorker()
        val recording = createRecordingEntity(uploadStatus = RecordingEntity.UploadStatus.UPLOADED)
        coEvery { cloudStorage.isAuthenticated() } returns true
        coEvery { recordingRepository.getById(1L) } returns recording

        val result = worker.doWork()

        assertEquals(ListenableWorker.Result.success(), result)
    }

    @Test
    fun `doWork returns failure when file does not exist`() = runTest {
        val worker = createWorker()
        val recording = createRecordingEntity(filePath = "/nonexistent/file.m4a")
        coEvery { cloudStorage.isAuthenticated() } returns true
        coEvery { recordingRepository.getById(1L) } returns recording

        val result = worker.doWork()

        assertEquals(ListenableWorker.Result.failure(), result)
        coVerify { recordingRepository.updateUploadStatus(1L, RecordingEntity.UploadStatus.FAILED) }
    }

    @Test
    fun `doWork updates status to uploading when starting`() = runTest {
        val tempFile = File.createTempFile("test", ".m4a")
        tempFile.deleteOnExit()

        val worker = createWorker()
        val recording = createRecordingEntity(filePath = tempFile.absolutePath)
        val recordingWithMetadata = RecordingWithMetadata(recording, emptyList(), emptyList())

        val metadataFile = File.createTempFile("metadata", ".json")
        metadataFile.deleteOnExit()

        coEvery { cloudStorage.isAuthenticated() } returns true
        coEvery { recordingRepository.getById(1L) } returns recording
        coEvery { recordingRepository.getWithMetadata(1L) } returns recordingWithMetadata
        coEvery { fileManager.writeMetadataSidecar(any(), any()) } returns metadataFile
        coEvery { cloudStorage.upload(any(), any(), any()) } returns UploadResult(
            success = true,
            audioFileId = "fileId123"
        )
        coEvery { cloudStorage.verifyUpload(any(), any()) } returns true

        worker.doWork()

        coVerify { recordingRepository.updateUploadStatus(1L, RecordingEntity.UploadStatus.UPLOADING) }
    }

    @Test
    fun `doWork updates status to uploaded on success`() = runTest {
        val tempFile = File.createTempFile("test", ".m4a")
        tempFile.deleteOnExit()
        val metadataFile = File.createTempFile("metadata", ".json")
        metadataFile.deleteOnExit()

        val worker = createWorker()
        val recording = createRecordingEntity(filePath = tempFile.absolutePath, md5Hash = "abc123")
        val recordingWithMetadata = RecordingWithMetadata(recording, emptyList(), emptyList())

        coEvery { cloudStorage.isAuthenticated() } returns true
        coEvery { recordingRepository.getById(1L) } returns recording
        coEvery { recordingRepository.getWithMetadata(1L) } returns recordingWithMetadata
        coEvery { fileManager.writeMetadataSidecar(any(), any()) } returns metadataFile
        coEvery { cloudStorage.upload(any(), any(), any()) } returns UploadResult(
            success = true,
            audioFileId = "fileId123"
        )
        coEvery { cloudStorage.verifyUpload("fileId123", "abc123") } returns true

        val result = worker.doWork()

        assertEquals(ListenableWorker.Result.success(), result)
        coVerify { recordingRepository.updateUploadStatus(1L, RecordingEntity.UploadStatus.UPLOADED) }
    }

    @Test
    fun `doWork retries on verification failure`() = runTest {
        val tempFile = File.createTempFile("test", ".m4a")
        tempFile.deleteOnExit()
        val metadataFile = File.createTempFile("metadata", ".json")
        metadataFile.deleteOnExit()

        val worker = createWorker()
        val recording = createRecordingEntity(filePath = tempFile.absolutePath, md5Hash = "abc123")
        val recordingWithMetadata = RecordingWithMetadata(recording, emptyList(), emptyList())

        coEvery { cloudStorage.isAuthenticated() } returns true
        coEvery { recordingRepository.getById(1L) } returns recording
        coEvery { recordingRepository.getWithMetadata(1L) } returns recordingWithMetadata
        coEvery { fileManager.writeMetadataSidecar(any(), any()) } returns metadataFile
        coEvery { cloudStorage.upload(any(), any(), any()) } returns UploadResult(
            success = true,
            audioFileId = "fileId123"
        )
        coEvery { cloudStorage.verifyUpload("fileId123", "abc123") } returns false

        val result = worker.doWork()

        assertEquals(ListenableWorker.Result.retry(), result)
        coVerify { recordingRepository.updateUploadStatus(1L, RecordingEntity.UploadStatus.PENDING) }
    }

    @Test
    fun `doWork marks as failed on quota exceeded error`() = runTest {
        val tempFile = File.createTempFile("test", ".m4a")
        tempFile.deleteOnExit()
        val metadataFile = File.createTempFile("metadata", ".json")
        metadataFile.deleteOnExit()

        val worker = createWorker()
        val recording = createRecordingEntity(filePath = tempFile.absolutePath)
        val recordingWithMetadata = RecordingWithMetadata(recording, emptyList(), emptyList())

        every { workerParams.runAttemptCount } returns 5 // Max retries reached

        coEvery { cloudStorage.isAuthenticated() } returns true
        coEvery { recordingRepository.getById(1L) } returns recording
        coEvery { recordingRepository.getWithMetadata(1L) } returns recordingWithMetadata
        coEvery { fileManager.writeMetadataSidecar(any(), any()) } returns metadataFile
        coEvery { cloudStorage.upload(any(), any(), any()) } returns UploadResult(
            success = false,
            error = UploadError.QuotaExceeded
        )

        worker.doWork()

        coVerify { recordingRepository.updateUploadStatus(1L, RecordingEntity.UploadStatus.FAILED) }
    }

    private fun createRecordingEntity(
        id: Long = 1L,
        filePath: String = "/test/file.m4a",
        uploadStatus: String = RecordingEntity.UploadStatus.PENDING,
        md5Hash: String? = null
    ) = RecordingEntity(
        id = id,
        sessionId = "test-session",
        chunkNumber = 1,
        filePath = filePath,
        startTimeEpochMilli = 0L,
        endTimeEpochMilli = 1000L,
        timezoneId = "UTC",
        durationSeconds = 1L,
        fileSizeBytes = 1000L,
        md5Hash = md5Hash,
        uploadStatus = uploadStatus
    )
}
