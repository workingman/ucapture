package ca.dgbi.ucapture.ui.settings

import android.content.Context
import app.cash.turbine.test
import ca.dgbi.ucapture.data.remote.GoogleDriveAuthManager
import ca.dgbi.ucapture.data.preferences.StoragePreferences
import ca.dgbi.ucapture.data.remote.GoogleDriveStorage
import ca.dgbi.ucapture.data.remote.UploadScheduler
import io.mockk.coEvery
import io.mockk.coVerify
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
    private lateinit var uploadScheduler: UploadScheduler
    private lateinit var storagePreferences: StoragePreferences
    private lateinit var viewModel: SettingsViewModel
    private lateinit var mockContext: Context

    @Before
    fun setUp() {
        Dispatchers.setMain(testDispatcher)
        authManager = mockk()
        storage = mockk()
        uploadScheduler = mockk(relaxed = true)
        storagePreferences = mockk(relaxed = true)
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
        coEvery { storage.getTargetFolderName() } returns null

        viewModel = SettingsViewModel(authManager, storage, uploadScheduler, storagePreferences)
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
        coEvery { storage.getTargetFolderName() } returns null

        viewModel = SettingsViewModel(authManager, storage, uploadScheduler, storagePreferences)
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
    fun `initial state shows folder name when target folder exists`() = runTest {
        coEvery { authManager.isSignedIn() } returns true
        coEvery { authManager.getCurrentAccountEmail() } returns "test@example.com"
        coEvery { storage.getTargetFolderName() } returns "My Recordings"

        viewModel = SettingsViewModel(authManager, storage, uploadScheduler, storagePreferences)
        advanceUntilIdle()

        viewModel.uiState.test {
            val state = awaitItem()
            assertEquals("My Recordings", state.currentFolderName)
        }
    }

    @Test
    fun `signIn sets loading state and refreshes on success`() = runTest {
        coEvery { authManager.isSignedIn() } returns false andThen true
        coEvery { authManager.signIn(any()) } returns true
        coEvery { authManager.getCurrentAccountEmail() } returns "test@example.com"
        coEvery { storage.getTargetFolderName() } returns null

        viewModel = SettingsViewModel(authManager, storage, uploadScheduler, storagePreferences)
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
    fun `signIn schedules pending and failed uploads on success`() = runTest {
        coEvery { authManager.isSignedIn() } returns false andThen true
        coEvery { authManager.signIn(any()) } returns true
        coEvery { authManager.getCurrentAccountEmail() } returns "test@example.com"
        coEvery { storage.getTargetFolderName() } returns null

        viewModel = SettingsViewModel(authManager, storage, uploadScheduler, storagePreferences)
        advanceUntilIdle()

        viewModel.signIn(mockContext)
        advanceUntilIdle()

        coVerify { uploadScheduler.retryFailedUploads(any()) }
        coVerify { uploadScheduler.schedulePendingUploads(any()) }
    }

    @Test
    fun `signIn clears loading state on failure`() = runTest {
        coEvery { authManager.isSignedIn() } returns false
        coEvery { authManager.signIn(any()) } returns false
        coEvery { storage.getTargetFolderName() } returns null

        viewModel = SettingsViewModel(authManager, storage, uploadScheduler, storagePreferences)
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
        coEvery { storage.getTargetFolderName() } returns null

        viewModel = SettingsViewModel(authManager, storage, uploadScheduler, storagePreferences)
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
    fun `toggleStorageBackend persists preference via storagePreferences`() = runTest {
        coEvery { authManager.isSignedIn() } returns false
        coEvery { storage.getTargetFolderName() } returns null

        viewModel = SettingsViewModel(authManager, storage, uploadScheduler, storagePreferences)
        advanceUntilIdle()

        viewModel.toggleStorageBackend(false)
        advanceUntilIdle()

        coVerify { storagePreferences.setUseCloudflareWorker(false) }
    }
}
