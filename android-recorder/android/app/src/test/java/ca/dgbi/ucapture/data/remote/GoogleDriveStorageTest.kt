package ca.dgbi.ucapture.data.remote

import android.content.Context
import com.google.api.services.drive.Drive
import com.google.api.services.drive.model.File as DriveFile
import com.google.api.services.drive.model.FileList
import io.mockk.coEvery
import io.mockk.every
import io.mockk.mockk
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.ExperimentalCoroutinesApi
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
import java.io.File
import java.io.IOException

@OptIn(ExperimentalCoroutinesApi::class)
class GoogleDriveStorageTest {

    private val testDispatcher = StandardTestDispatcher()
    private lateinit var context: Context
    private lateinit var authManager: GoogleDriveAuthManager
    private lateinit var driveService: Drive
    private lateinit var storage: GoogleDriveStorage

    @Before
    fun setUp() {
        Dispatchers.setMain(testDispatcher)
        context = mockk(relaxed = true)
        authManager = mockk()
        driveService = mockk()
        storage = GoogleDriveStorage(context, authManager)
    }

    @After
    fun tearDown() {
        Dispatchers.resetMain()
    }

    @Test
    fun `providerId returns google_drive`() {
        assertEquals("google_drive", storage.providerId)
    }

    @Test
    fun `isAuthenticated returns false when not signed in`() = runTest {
        coEvery { authManager.isSignedIn() } returns false

        assertFalse(storage.isAuthenticated())
    }

    @Test
    fun `isAuthenticated returns true when signed in`() = runTest {
        coEvery { authManager.isSignedIn() } returns true

        assertTrue(storage.isAuthenticated())
    }

    @Test
    fun `upload returns NotAuthenticated when not signed in`() = runTest {
        coEvery { authManager.isSignedIn() } returns false
        val tempFile = File.createTempFile("test", ".m4a")
        tempFile.deleteOnExit()

        val result = storage.upload(tempFile, null)

        assertFalse(result.success)
        assertEquals(UploadError.NotAuthenticated, result.error)
    }

    @Test
    fun `upload returns FileError when file does not exist`() = runTest {
        coEvery { authManager.isSignedIn() } returns true
        coEvery { authManager.ensureFreshToken() } returns true
        val nonExistentFile = File("/nonexistent/file.m4a")

        val result = storage.upload(nonExistentFile, null, "folder123")

        assertFalse(result.success)
        assertTrue(result.error is UploadError.FileError)
    }

    @Test
    fun `verifyUpload returns false when hashes differ`() = runTest {
        val filesGet = mockk<Drive.Files.Get>()
        val files = mockk<Drive.Files>()
        val driveFile = DriveFile().apply { md5Checksum = "abc123" }

        coEvery { authManager.ensureFreshToken() } returns true
        coEvery { authManager.getDriveService() } returns driveService
        every { driveService.files() } returns files
        every { files.get(any()) } returns filesGet
        every { filesGet.setFields(any()) } returns filesGet
        every { filesGet.execute() } returns driveFile

        val result = storage.verifyUpload("fileId", "xyz789")

        assertFalse(result)
    }

    @Test
    fun `verifyUpload returns true when hashes match`() = runTest {
        val filesGet = mockk<Drive.Files.Get>()
        val files = mockk<Drive.Files>()
        val driveFile = DriveFile().apply { md5Checksum = "abc123" }

        coEvery { authManager.ensureFreshToken() } returns true
        coEvery { authManager.getDriveService() } returns driveService
        every { driveService.files() } returns files
        every { files.get(any()) } returns filesGet
        every { filesGet.setFields(any()) } returns filesGet
        every { filesGet.execute() } returns driveFile

        val result = storage.verifyUpload("fileId", "abc123")

        assertTrue(result)
    }

    @Test
    fun `verifyUpload returns false on exception`() = runTest {
        coEvery { authManager.ensureFreshToken() } returns true
        coEvery { authManager.getDriveService() } throws IOException("Network error")

        val result = storage.verifyUpload("fileId", "abc123")

        assertFalse(result)
    }

    @Test
    fun `delete returns true on success`() = runTest {
        val filesDelete = mockk<Drive.Files.Delete>()
        val files = mockk<Drive.Files>()

        coEvery { authManager.getDriveService() } returns driveService
        every { driveService.files() } returns files
        every { files.delete(any()) } returns filesDelete
        every { filesDelete.execute() } returns mockk()

        val result = storage.delete("fileId")

        assertTrue(result)
    }

    @Test
    fun `delete returns false on exception`() = runTest {
        coEvery { authManager.getDriveService() } throws IOException("Network error")

        val result = storage.delete("fileId")

        assertFalse(result)
    }

    @Test
    fun `listFolders returns empty list on exception`() = runTest {
        coEvery { authManager.getDriveService() } throws IOException("Network error")

        val result = storage.listFolders()

        assertTrue(result.isEmpty())
    }

    @Test
    fun `listFolders returns folder list on success`() = runTest {
        val filesList = mockk<Drive.Files.List>()
        val driveFolder = DriveFile().apply {
            id = "folder1"
            name = "Test Folder"
            parents = listOf("root")
        }
        val fileList = FileList().apply {
            files = listOf(driveFolder)
        }

        coEvery { authManager.getDriveService() } returns driveService
        every { driveService.files() } returns mockk {
            every { list() } returns filesList
        }
        every { filesList.setQ(any()) } returns filesList
        every { filesList.setFields(any()) } returns filesList
        every { filesList.setOrderBy(any()) } returns filesList
        every { filesList.execute() } returns fileList

        val result = storage.listFolders()

        assertEquals(1, result.size)
        assertEquals("folder1", result[0].id)
        assertEquals("Test Folder", result[0].name)
    }
}
