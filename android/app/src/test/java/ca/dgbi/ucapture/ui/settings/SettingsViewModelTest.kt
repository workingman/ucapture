package ca.dgbi.ucapture.ui.settings

import android.content.Context
import app.cash.turbine.test
import ca.dgbi.ucapture.data.remote.CloudFolder
import ca.dgbi.ucapture.data.remote.GoogleDriveAuthManager
import ca.dgbi.ucapture.data.remote.GoogleDriveStorage
import io.mockk.coEvery
import io.mockk.coVerify
import io.mockk.every
import io.mockk.mockk
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.ExperimentalCoroutinesApi
import kotlinx.coroutines.test.StandardTestDispatcher
import kotlinx.coroutines.test.advanceUntilIdle
import kotlinx.coroutines.test.resetMain
import kotlinx.coroutines.test.runTest
import kotlinx.coroutines.test.setMain
import org.junit.After
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Before
import org.junit.Test

@OptIn(ExperimentalCoroutinesApi::class)
class SettingsViewModelTest {

    private val testDispatcher = StandardTestDispatcher()
    private lateinit var authManager: GoogleDriveAuthManager
    private lateinit var storage: GoogleDriveStorage
    private lateinit var viewModel: SettingsViewModel
    private lateinit var mockContext: Context

    @Before
    fun setUp() {
        Dispatchers.setMain(testDispatcher)
        authManager = mockk()
        storage = mockk()
        mockContext = mockk(relaxed = true)
    }

    @After
    fun tearDown() {
        Dispatchers.resetMain()
    }

    @Test
    fun `initial state is not signed in when auth check returns false`() = runTest {
        coEvery { authManager.isSignedIn() } returns false
        coEvery { authManager.getCurrentAccountEmail() } returns null
        coEvery { storage.getTargetFolderId() } returns null

        viewModel = SettingsViewModel(authManager, storage)
        advanceUntilIdle()

        viewModel.uiState.test {
            val state = awaitItem()
            assertFalse(state.isSignedIn)
            assertNull(state.userEmail)
            assertNull(state.currentFolderName)
            assertFalse(state.isLoading)
        }
    }

    @Test
    fun `initial state is signed in when auth check returns true`() = runTest {
        coEvery { authManager.isSignedIn() } returns true
        coEvery { authManager.getCurrentAccountEmail() } returns "test@example.com"
        coEvery { storage.getTargetFolderId() } returns null

        viewModel = SettingsViewModel(authManager, storage)
        advanceUntilIdle()

        viewModel.uiState.test {
            val state = awaitItem()
            assertTrue(state.isSignedIn)
            assertEquals("test@example.com", state.userEmail)
            assertNull(state.currentFolderName)
            assertFalse(state.isLoading)
        }
    }

    @Test
    fun `initial state shows folder selected when target folder exists`() = runTest {
        coEvery { authManager.isSignedIn() } returns true
        coEvery { authManager.getCurrentAccountEmail() } returns "test@example.com"
        coEvery { storage.getTargetFolderId() } returns "folder123"

        viewModel = SettingsViewModel(authManager, storage)
        advanceUntilIdle()

        viewModel.uiState.test {
            val state = awaitItem()
            assertEquals("Folder selected", state.currentFolderName)
        }
    }

    @Test
    fun `signIn sets loading state and refreshes on success`() = runTest {
        coEvery { authManager.isSignedIn() } returns false andThen true
        coEvery { authManager.signIn(any()) } returns true
        coEvery { authManager.getCurrentAccountEmail() } returns "test@example.com"
        coEvery { storage.getTargetFolderId() } returns null

        viewModel = SettingsViewModel(authManager, storage)
        advanceUntilIdle()

        viewModel.uiState.test {
            skipItems(1) // Skip initial state

            viewModel.signIn(mockContext)

            val loadingState = awaitItem()
            assertTrue(loadingState.isLoading)

            advanceUntilIdle()

            val signedInState = awaitItem()
            assertFalse(signedInState.isLoading)
            assertTrue(signedInState.isSignedIn)
            assertEquals("test@example.com", signedInState.userEmail)
        }
    }

    @Test
    fun `signIn clears loading state on failure`() = runTest {
        coEvery { authManager.isSignedIn() } returns false
        coEvery { authManager.signIn(any()) } returns false
        coEvery { storage.getTargetFolderId() } returns null

        viewModel = SettingsViewModel(authManager, storage)
        advanceUntilIdle()

        viewModel.uiState.test {
            skipItems(1) // Skip initial state

            viewModel.signIn(mockContext)

            val loadingState = awaitItem()
            assertTrue(loadingState.isLoading)

            advanceUntilIdle()

            val finalState = awaitItem()
            assertFalse(finalState.isLoading)
            assertFalse(finalState.isSignedIn)
        }
    }

    @Test
    fun `signOut sets loading state and refreshes auth state`() = runTest {
        coEvery { authManager.isSignedIn() } returns true andThen false
        coEvery { authManager.getCurrentAccountEmail() } returns "test@example.com" andThen null
        coEvery { authManager.signOut() } returns Unit
        coEvery { storage.getTargetFolderId() } returns null

        viewModel = SettingsViewModel(authManager, storage)
        advanceUntilIdle()

        viewModel.uiState.test {
            skipItems(1) // Skip initial state

            viewModel.signOut()

            val loadingState = awaitItem()
            assertTrue(loadingState.isLoading)

            advanceUntilIdle()

            val signedOutState = awaitItem()
            assertFalse(signedOutState.isLoading)
            assertFalse(signedOutState.isSignedIn)
            assertNull(signedOutState.userEmail)
        }
    }

    @Test
    fun `loadFolders sets loading state and updates folders list`() = runTest {
        coEvery { authManager.isSignedIn() } returns true
        coEvery { authManager.getCurrentAccountEmail() } returns "test@example.com"
        coEvery { storage.getTargetFolderId() } returns null

        val folders = listOf(
            CloudFolder("folder1", "Folder 1", "root"),
            CloudFolder("folder2", "Folder 2", "root")
        )
        coEvery { storage.listFolders(null) } returns folders

        viewModel = SettingsViewModel(authManager, storage)
        advanceUntilIdle()

        viewModel.uiState.test {
            skipItems(1) // Skip initial state

            viewModel.loadFolders()

            val loadingState = awaitItem()
            assertTrue(loadingState.isLoading)

            advanceUntilIdle()

            val loadedState = awaitItem()
            assertFalse(loadedState.isLoading)
            assertEquals(2, loadedState.folders.size)
            assertEquals("Folder 1", loadedState.folders[0].name)
            assertEquals("Folder 2", loadedState.folders[1].name)
        }
    }

    @Test
    fun `selectFolder updates target folder and current folder name`() = runTest {
        coEvery { authManager.isSignedIn() } returns true
        coEvery { authManager.getCurrentAccountEmail() } returns "test@example.com"
        coEvery { storage.getTargetFolderId() } returns null
        coEvery { storage.setTargetFolderId(any()) } returns Unit

        viewModel = SettingsViewModel(authManager, storage)
        advanceUntilIdle()

        viewModel.uiState.test {
            skipItems(1) // Skip initial state

            viewModel.selectFolder("folder123", "My Recordings")
            advanceUntilIdle()

            val updatedState = awaitItem()
            assertEquals("My Recordings", updatedState.currentFolderName)
        }

        coVerify { storage.setTargetFolderId("folder123") }
    }

    @Test
    fun `selectFolder persists folder ID to storage`() = runTest {
        coEvery { authManager.isSignedIn() } returns true
        coEvery { authManager.getCurrentAccountEmail() } returns "test@example.com"
        coEvery { storage.getTargetFolderId() } returns null
        coEvery { storage.setTargetFolderId(any()) } returns Unit

        viewModel = SettingsViewModel(authManager, storage)
        advanceUntilIdle()

        viewModel.selectFolder("folder456", "Test Folder")
        advanceUntilIdle()

        coVerify { storage.setTargetFolderId("folder456") }
    }
}
