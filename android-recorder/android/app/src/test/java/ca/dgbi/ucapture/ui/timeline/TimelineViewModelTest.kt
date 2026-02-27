package ca.dgbi.ucapture.ui.timeline

import app.cash.turbine.test
import ca.dgbi.ucapture.data.local.entity.RecordingEntity
import ca.dgbi.ucapture.data.local.relation.RecordingWithMetadata
import ca.dgbi.ucapture.data.remote.UploadScheduler
import ca.dgbi.ucapture.data.repository.RecordingRepository
import io.mockk.every
import io.mockk.mockk
import io.mockk.verify
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.ExperimentalCoroutinesApi
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.launch
import kotlinx.coroutines.test.StandardTestDispatcher
import kotlinx.coroutines.test.resetMain
import kotlinx.coroutines.test.runTest
import kotlinx.coroutines.test.setMain
import org.junit.After
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Before
import org.junit.Test

@OptIn(ExperimentalCoroutinesApi::class)
class TimelineViewModelTest {

    private val testDispatcher = StandardTestDispatcher()
    private val unconfinedDispatcher = kotlinx.coroutines.test.UnconfinedTestDispatcher()
    private lateinit var recordingRepository: RecordingRepository
    private lateinit var uploadScheduler: UploadScheduler
    private lateinit var viewModel: TimelineViewModel

    @Before
    fun setUp() {
        Dispatchers.setMain(testDispatcher)
        recordingRepository = mockk()
        uploadScheduler = mockk(relaxed = true)
    }

    @After
    fun tearDown() {
        Dispatchers.resetMain()
    }

    @Test
    fun `hasFailedUploads emits false when recordings list is empty`() = runTest {
        val recordings = MutableStateFlow<List<RecordingWithMetadata>>(emptyList())
        every { recordingRepository.allRecordingsWithMetadata } returns recordings

        viewModel = TimelineViewModel(recordingRepository, uploadScheduler)

        viewModel.hasFailedUploads.test {
            assertEquals(false, awaitItem()) // Initial value
        }
    }

    @Test
    fun `hasFailedUploads emits false when no recordings have failed status`() = runTest(unconfinedDispatcher) {
        val recordings = MutableStateFlow<List<RecordingWithMetadata>>(
            listOf(
                createRecordingWithMetadata(uploadStatus = RecordingEntity.UploadStatus.PENDING),
                createRecordingWithMetadata(uploadStatus = RecordingEntity.UploadStatus.UPLOADED),
                createRecordingWithMetadata(uploadStatus = RecordingEntity.UploadStatus.UPLOADING)
            )
        )
        every { recordingRepository.allRecordingsWithMetadata } returns recordings

        viewModel = TimelineViewModel(recordingRepository, uploadScheduler)

        viewModel.hasFailedUploads.test {
            assertEquals(false, awaitItem())
        }
    }

    @Test
    fun `hasFailedUploads emits true when at least one recording has failed status`() = runTest {
        val recordings = MutableStateFlow<List<RecordingWithMetadata>>(emptyList())
        every { recordingRepository.allRecordingsWithMetadata } returns recordings

        viewModel = TimelineViewModel(recordingRepository, uploadScheduler)

        viewModel.hasFailedUploads.test {
            assertEquals(false, awaitItem())

            recordings.value = listOf(
                createRecordingWithMetadata(uploadStatus = RecordingEntity.UploadStatus.PENDING),
                createRecordingWithMetadata(uploadStatus = RecordingEntity.UploadStatus.FAILED),
                createRecordingWithMetadata(uploadStatus = RecordingEntity.UploadStatus.UPLOADED)
            )

            assertEquals(true, awaitItem())
        }
    }

    @Test
    fun `hasFailedUploads emits true when multiple recordings have failed status`() = runTest {
        val recordings = MutableStateFlow<List<RecordingWithMetadata>>(emptyList())
        every { recordingRepository.allRecordingsWithMetadata } returns recordings

        viewModel = TimelineViewModel(recordingRepository, uploadScheduler)

        viewModel.hasFailedUploads.test {
            assertEquals(false, awaitItem())

            recordings.value = listOf(
                createRecordingWithMetadata(uploadStatus = RecordingEntity.UploadStatus.FAILED),
                createRecordingWithMetadata(uploadStatus = RecordingEntity.UploadStatus.FAILED),
                createRecordingWithMetadata(uploadStatus = RecordingEntity.UploadStatus.UPLOADED)
            )

            assertEquals(true, awaitItem())
        }
    }

    @Test
    fun `recordings are sorted by start time with newest first`() = runTest {
        val recordings = MutableStateFlow<List<RecordingWithMetadata>>(emptyList())
        every { recordingRepository.allRecordingsWithMetadata } returns recordings

        viewModel = TimelineViewModel(recordingRepository, uploadScheduler)

        viewModel.recordings.test {
            assertEquals(emptyList<RecordingWithMetadata>(), awaitItem())

            // Add recordings out of order
            recordings.value = listOf(
                createRecordingWithMetadata(startTime = 1000),
                createRecordingWithMetadata(startTime = 3000),
                createRecordingWithMetadata(startTime = 2000)
            )

            val sorted = awaitItem()
            assertEquals(3000, sorted[0].recording.startTimeEpochMilli)
            assertEquals(2000, sorted[1].recording.startTimeEpochMilli)
            assertEquals(1000, sorted[2].recording.startTimeEpochMilli)
        }
    }

    @Test
    fun `isLoading initial state is true`() {
        val recordings = MutableStateFlow<List<RecordingWithMetadata>>(emptyList())
        every { recordingRepository.allRecordingsWithMetadata } returns recordings

        viewModel = TimelineViewModel(recordingRepository, uploadScheduler)

        // Initial state should be true
        assertTrue(viewModel.isLoading.value)
    }

    @Test
    fun `retryFailedUploads calls uploadScheduler`() {
        val recordings = MutableStateFlow<List<RecordingWithMetadata>>(emptyList())
        every { recordingRepository.allRecordingsWithMetadata } returns recordings

        viewModel = TimelineViewModel(recordingRepository, uploadScheduler)

        viewModel.retryFailedUploads()

        verify { uploadScheduler.retryFailedUploads(any()) }
    }

    private fun createRecordingWithMetadata(
        uploadStatus: String = RecordingEntity.UploadStatus.PENDING,
        startTime: Long = System.currentTimeMillis()
    ): RecordingWithMetadata {
        return RecordingWithMetadata(
            recording = RecordingEntity(
                id = 1,
                sessionId = "test-session",
                chunkNumber = 1,
                filePath = "/test/path.m4a",
                startTimeEpochMilli = startTime,
                endTimeEpochMilli = startTime + 60000,
                timezoneId = "America/New_York",
                durationSeconds = 60,
                fileSizeBytes = 1024,
                md5Hash = "hash123",
                uploadStatus = uploadStatus
            ),
            locationSamples = emptyList()
        )
    }
}
