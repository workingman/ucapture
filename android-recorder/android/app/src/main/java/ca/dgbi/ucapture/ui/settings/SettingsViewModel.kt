package ca.dgbi.ucapture.ui.settings

import android.content.Context
import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import ca.dgbi.ucapture.data.preferences.StoragePreferences
import ca.dgbi.ucapture.data.remote.GoogleDriveAuthManager
import ca.dgbi.ucapture.data.remote.GoogleDriveStorage
import ca.dgbi.ucapture.data.remote.UploadScheduler
import dagger.hilt.android.lifecycle.HiltViewModel
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch
import javax.inject.Inject

/**
 * ViewModel for the Settings screen.
 *
 * Manages Google Drive authentication state and folder selection.
 */
@HiltViewModel
class SettingsViewModel @Inject constructor(
    private val authManager: GoogleDriveAuthManager,
    private val storage: GoogleDriveStorage,
    private val uploadScheduler: UploadScheduler,
    private val storagePreferences: StoragePreferences
) : ViewModel() {

    private val _uiState = MutableStateFlow(SettingsUiState())
    val uiState: StateFlow<SettingsUiState> = _uiState.asStateFlow()

    init {
        viewModelScope.launch {
            storagePreferences.useCloudflareWorker.collect { useCloudflare ->
                _uiState.update { it.copy(useCloudflareWorker = useCloudflare) }
            }
        }
        viewModelScope.launch {
            refreshAuthState()
        }
    }

    /**
     * Sign in with Google Drive.
     *
     * @param activityContext Activity context for sign-in UI
     */
    fun signIn(activityContext: Context) {
        viewModelScope.launch {
            _uiState.update { it.copy(isLoading = true) }
            val success = authManager.signIn(activityContext)
            if (success) {
                refreshAuthState()
                uploadScheduler.retryFailedUploads(viewModelScope)
                uploadScheduler.schedulePendingUploads(viewModelScope)
            } else {
                _uiState.update { it.copy(isLoading = false) }
            }
        }
    }

    /**
     * Sign out from Google Drive.
     */
    fun signOut() {
        viewModelScope.launch {
            _uiState.update { it.copy(isLoading = true) }
            authManager.signOut()
            refreshAuthState()
        }
    }

    /**
     * Create or select a Google Drive folder for uploads.
     *
     * With the drive.file scope, we can only access folders created by this app.
     * This method searches for an existing folder with the given name, or creates it if not found.
     *
     * @param folderName The folder name to create or select
     */
    fun createOrSelectFolder(folderName: String) {
        viewModelScope.launch {
            _uiState.update { it.copy(isLoading = true, errorMessage = null) }

            val result = storage.findOrCreateFolder(folderName)

            if (result != null) {
                storage.setTargetFolder(result.id, result.name)
                _uiState.update {
                    it.copy(
                        currentFolderName = result.name,
                        isLoading = false,
                        errorMessage = null
                    )
                }
            } else {
                _uiState.update {
                    it.copy(
                        isLoading = false,
                        errorMessage = "Failed to create or find folder. Please try again."
                    )
                }
            }
        }
    }

    fun toggleStorageBackend(useCloudflare: Boolean) {
        viewModelScope.launch {
            storagePreferences.setUseCloudflareWorker(useCloudflare)
        }
    }

    private suspend fun refreshAuthState() {
        val isSignedIn = authManager.isSignedIn()
        val email = if (isSignedIn) authManager.getCurrentAccountEmail() else null
        val currentFolderName = storage.getTargetFolderName()

        _uiState.update {
            it.copy(
                isSignedIn = isSignedIn,
                userEmail = email,
                currentFolderName = currentFolderName,
                isLoading = false
            )
        }
    }
}

/**
 * UI state for the Settings screen.
 */
data class SettingsUiState(
    val isSignedIn: Boolean = false,
    val userEmail: String? = null,
    val currentFolderName: String? = null,
    val isLoading: Boolean = false,
    val errorMessage: String? = null,
    val useCloudflareWorker: Boolean = false
)
