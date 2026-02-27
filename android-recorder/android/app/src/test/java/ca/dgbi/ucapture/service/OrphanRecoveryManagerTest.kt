package ca.dgbi.ucapture.service

import ca.dgbi.ucapture.data.local.entity.RecordingEntity
import ca.dgbi.ucapture.data.repository.RecordingRepository
import ca.dgbi.ucapture.util.FileManager
import io.mockk.coEvery
import io.mockk.coVerify
import io.mockk.every
import io.mockk.mockk
import kotlinx.coroutines.test.runTest
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Before
import org.junit.Rule
import org.junit.Test
import org.junit.rules.TemporaryFolder
import java.io.File

class OrphanRecoveryManagerTest {

    @get:Rule
    val tempFolder = TemporaryFolder()

    private lateinit var fileManager: FileManager
    private lateinit var recordingRepository: RecordingRepository
    private lateinit var orphanRecoveryManager: OrphanRecoveryManager
    private lateinit var recordingsDir: File

    @Before
    fun setUp() {
        fileManager = mockk()
        recordingRepository = mockk()
        orphanRecoveryManager = OrphanRecoveryManager(fileManager, recordingRepository)
        recordingsDir = tempFolder.newFolder("recordings")
    }

    @Test
    fun `recovers orphaned completed files with no DB row`() = runTest {
        val orphanFile = File(recordingsDir, "ucap-20240315-150000-PST.m4a").apply {
            writeText("fake audio data")
        }

        every { fileManager.listRecordingFiles() } returns listOf(orphanFile)
        coEvery { recordingRepository.getByFilePath(orphanFile.absolutePath) } returns null
        coEvery { recordingRepository.insertRecording(any()) } returns 42L

        val recovered = orphanRecoveryManager.recoverOrphans()

        assertEquals(listOf(42L), recovered)
        coVerify {
            recordingRepository.insertRecording(match {
                it.filePath == orphanFile.absolutePath &&
                    it.uploadStatus == RecordingEntity.UploadStatus.PENDING &&
                    it.sessionId == "orphan-20240315-150000" &&
                    it.fileSizeBytes == orphanFile.length()
            })
        }
    }

    @Test
    fun `skips files that already have a DB row`() = runTest {
        val existingFile = File(recordingsDir, "ucap-20240315-150000-PST.m4a").apply {
            writeText("fake audio data")
        }

        val existingEntity = mockk<RecordingEntity>()
        every { fileManager.listRecordingFiles() } returns listOf(existingFile)
        coEvery { recordingRepository.getByFilePath(existingFile.absolutePath) } returns existingEntity

        val recovered = orphanRecoveryManager.recoverOrphans()

        assertTrue(recovered.isEmpty())
        coVerify(exactly = 0) { recordingRepository.insertRecording(any()) }
    }

    @Test
    fun `skips in-progress files with chunk number suffix`() = runTest {
        val inProgressFile = File(recordingsDir, "ucap-20240315-143000-PST-001.m4a").apply {
            writeText("fake audio data")
        }

        every { fileManager.listRecordingFiles() } returns listOf(inProgressFile)

        val recovered = orphanRecoveryManager.recoverOrphans()

        assertTrue(recovered.isEmpty())
        coVerify(exactly = 0) { recordingRepository.getByFilePath(any()) }
    }

    @Test
    fun `handles mix of orphans, existing, and in-progress files`() = runTest {
        val orphanFile = File(recordingsDir, "ucap-20240315-150000-PST.m4a").apply {
            writeText("orphan")
        }
        val existingFile = File(recordingsDir, "ucap-20240315-160000-PST.m4a").apply {
            writeText("existing")
        }
        val inProgressFile = File(recordingsDir, "ucap-20240315-170000-PST-002.m4a").apply {
            writeText("in-progress")
        }

        every { fileManager.listRecordingFiles() } returns listOf(orphanFile, existingFile, inProgressFile)
        coEvery { recordingRepository.getByFilePath(orphanFile.absolutePath) } returns null
        coEvery { recordingRepository.getByFilePath(existingFile.absolutePath) } returns mockk()
        coEvery { recordingRepository.insertRecording(any()) } returns 10L

        val recovered = orphanRecoveryManager.recoverOrphans()

        assertEquals(1, recovered.size)
        assertEquals(10L, recovered[0])
    }

    @Test
    fun `returns empty list when no recordings exist`() = runTest {
        every { fileManager.listRecordingFiles() } returns emptyList()

        val recovered = orphanRecoveryManager.recoverOrphans()

        assertTrue(recovered.isEmpty())
    }

    @Test
    fun `continues recovering remaining files when one insert fails`() = runTest {
        val file1 = File(recordingsDir, "ucap-20240315-150000-PST.m4a").apply {
            writeText("file1")
        }
        val file2 = File(recordingsDir, "ucap-20240315-160000-PST.m4a").apply {
            writeText("file2")
        }

        every { fileManager.listRecordingFiles() } returns listOf(file1, file2)
        coEvery { recordingRepository.getByFilePath(file1.absolutePath) } returns null
        coEvery { recordingRepository.getByFilePath(file2.absolutePath) } returns null
        coEvery { recordingRepository.insertRecording(match { it.filePath == file1.absolutePath }) } throws RuntimeException("DB error")
        coEvery { recordingRepository.insertRecording(match { it.filePath == file2.absolutePath }) } returns 20L

        val recovered = orphanRecoveryManager.recoverOrphans()

        assertEquals(listOf(20L), recovered)
    }

    @Test
    fun `recovered entity has PENDING upload status`() = runTest {
        val orphanFile = File(recordingsDir, "ucap-20240315-150000-PDT.m4a").apply {
            writeText("data")
        }

        every { fileManager.listRecordingFiles() } returns listOf(orphanFile)
        coEvery { recordingRepository.getByFilePath(orphanFile.absolutePath) } returns null
        coEvery { recordingRepository.insertRecording(any()) } returns 1L

        orphanRecoveryManager.recoverOrphans()

        coVerify {
            recordingRepository.insertRecording(match {
                it.uploadStatus == RecordingEntity.UploadStatus.PENDING
            })
        }
    }
}
