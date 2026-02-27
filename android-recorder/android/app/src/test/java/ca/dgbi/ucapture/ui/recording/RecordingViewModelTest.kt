package ca.dgbi.ucapture.ui.recording

import app.cash.turbine.test
import ca.dgbi.ucapture.data.local.entity.RecordingEntity
import ca.dgbi.ucapture.data.local.relation.RecordingWithMetadata
import ca.dgbi.ucapture.data.repository.RecordingRepository
import io.mockk.every
import io.mockk.mockk
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.ExperimentalCoroutinesApi
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.test.StandardTestDispatcher
import kotlinx.coroutines.test.resetMain
import kotlinx.coroutines.test.runTest
import kotlinx.coroutines.test.setMain
import org.junit.After
import org.junit.Assert.assertEquals
import org.junit.Before
import org.junit.Test

@OptIn(ExperimentalCoroutinesApi::class)
class RecordingViewModelTest {

    private val testDispatcher = StandardTestDispatcher()
    private val unconfinedDispatcher = kotlinx.coroutines.test.UnconfinedTestDispatcher()
    private lateinit var recordingRepository: RecordingRepository
    private lateinit var viewModel: RecordingViewModel

    @Before
    fun setUp() {
        Dispatchers.setMain(testDispatcher)
        recordingRepository = mockk()
    }

    @After
    fun tearDown() {
        Dispatchers.resetMain()
    }

    @Test
    fun `formatDuration returns MM SS for zero seconds`() {
        val recordings = MutableStateFlow<List<RecordingWithMetadata>>(emptyList())
        every { recordingRepository.allRecordingsWithMetadata } returns recordings
        viewModel = RecordingViewModel(recordingRepository)

        val result = viewModel.formatDuration(0)

        assertEquals("00:00", result)
    }

    @Test
    fun `formatDuration returns MM SS for 45 seconds`() {
        val recordings = MutableStateFlow<List<RecordingWithMetadata>>(emptyList())
        every { recordingRepository.allRecordingsWithMetadata } returns recordings
        viewModel = RecordingViewModel(recordingRepository)

        val result = viewModel.formatDuration(45)

        assertEquals("00:45", result)
    }

    @Test
    fun `formatDuration returns MM SS for 2 minutes 30 seconds`() {
        val recordings = MutableStateFlow<List<RecordingWithMetadata>>(emptyList())
        every { recordingRepository.allRecordingsWithMetadata } returns recordings
        viewModel = RecordingViewModel(recordingRepository)

        val result = viewModel.formatDuration(150)

        assertEquals("02:30", result)
    }

    @Test
    fun `formatDuration returns HH MM SS for 1 hour 5 minutes 30 seconds`() {
        val recordings = MutableStateFlow<List<RecordingWithMetadata>>(emptyList())
        every { recordingRepository.allRecordingsWithMetadata } returns recordings
        viewModel = RecordingViewModel(recordingRepository)

        val result = viewModel.formatDuration(3930)

        assertEquals("01:05:30", result)
    }

    @Test
    fun `formatDuration returns HH MM SS for exactly 1 hour`() {
        val recordings = MutableStateFlow<List<RecordingWithMetadata>>(emptyList())
        every { recordingRepository.allRecordingsWithMetadata } returns recordings
        viewModel = RecordingViewModel(recordingRepository)

        val result = viewModel.formatDuration(3600)

        assertEquals("01:00:00", result)
    }

    @Test
    fun `formatDuration returns HH MM SS for multiple hours`() {
        val recordings = MutableStateFlow<List<RecordingWithMetadata>>(emptyList())
        every { recordingRepository.allRecordingsWithMetadata } returns recordings
        viewModel = RecordingViewModel(recordingRepository)

        val result = viewModel.formatDuration(7384) // 2h 3m 4s

        assertEquals("02:03:04", result)
    }

    @Test
    fun `pendingUploadCount emits count of pending recordings`() = runTest {
        val recordings = MutableStateFlow<List<RecordingWithMetadata>>(emptyList())
        every { recordingRepository.allRecordingsWithMetadata } returns recordings

        viewModel = RecordingViewModel(recordingRepository)

        viewModel.pendingUploadCount.test {
            assertEquals(0, awaitItem()) // Initial value

            // Add recordings with different statuses
            recordings.value = listOf(
                createRecordingWithMetadata(uploadStatus = RecordingEntity.UploadStatus.PENDING),
                createRecordingWithMetadata(uploadStatus = RecordingEntity.UploadStatus.UPLOADED),
                createRecordingWithMetadata(uploadStatus = RecordingEntity.UploadStatus.PENDING),
                createRecordingWithMetadata(uploadStatus = RecordingEntity.UploadStatus.FAILED)
            )

            assertEquals(2, awaitItem()) // Two pending recordings
        }
    }

    @Test
    fun `pendingUploadCount emits zero when no pending recordings`() = runTest(unconfinedDispatcher) {
        val recordings = MutableStateFlow<List<RecordingWithMetadata>>(
            listOf(
                createRecordingWithMetadata(uploadStatus = RecordingEntity.UploadStatus.UPLOADED),
                createRecordingWithMetadata(uploadStatus = RecordingEntity.UploadStatus.FAILED)
            )
        )
        every { recordingRepository.allRecordingsWithMetadata } returns recordings

        viewModel = RecordingViewModel(recordingRepository)

        viewModel.pendingUploadCount.test {
            assertEquals(0, awaitItem())
        }
    }

    private fun createRecordingWithMetadata(
        uploadStatus: String = RecordingEntity.UploadStatus.PENDING
    ): RecordingWithMetadata {
        return RecordingWithMetadata(
            recording = RecordingEntity(
                id = 1,
                sessionId = "test-session",
                chunkNumber = 1,
                filePath = "/test/path.m4a",
                startTimeEpochMilli = System.currentTimeMillis(),
                endTimeEpochMilli = System.currentTimeMillis() + 60000,
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
