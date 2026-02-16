package ca.dgbi.ucapture.ui.recording

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import ca.dgbi.ucapture.data.local.entity.RecordingEntity
import ca.dgbi.ucapture.data.repository.RecordingRepository
import ca.dgbi.ucapture.service.RecordingService
import dagger.hilt.android.lifecycle.HiltViewModel
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.SharingStarted
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.map
import kotlinx.coroutines.flow.stateIn
import kotlinx.coroutines.flow.update
import javax.inject.Inject

/**
 * ViewModel for the Recording screen.
 *
 * Manages recording state and provides UI state derived from RecordingService.
 * Service binding is handled by the composable for proper lifecycle management.
 */
@HiltViewModel
class RecordingViewModel @Inject constructor(
    private val recordingRepository: RecordingRepository
) : ViewModel() {

    private val _uiState = MutableStateFlow(RecordingUiState())
    val uiState: StateFlow<RecordingUiState> = _uiState.asStateFlow()

    // Pending upload count from repository
    val pendingUploadCount: StateFlow<Int> = recordingRepository.allRecordingsWithMetadata
        .map { recordings ->
            recordings.count { it.recording.uploadStatus == RecordingEntity.UploadStatus.PENDING }
        }
        .stateIn(
            scope = viewModelScope,
            started = SharingStarted.WhileSubscribed(5000),
            initialValue = 0
        )

    /**
     * Update UI state from the bound service.
     * Called by the composable when service state changes.
     */
    fun updateFromService(service: RecordingService?) {
        if (service == null) {
            _uiState.update {
                it.copy(
                    isRecording = false,
                    isPaused = false,
                    recordingDurationSeconds = 0
                )
            }
            return
        }

        val state = service.state.value
        val duration = service.durationSeconds.value

        _uiState.update {
            it.copy(
                isRecording = state == RecordingService.State.RECORDING,
                isPaused = state == RecordingService.State.PAUSED,
                recordingDurationSeconds = duration
            )
        }
    }

    /**
     * Format duration in seconds to MM:SS or HH:MM:SS.
     */
    fun formatDuration(seconds: Long): String {
        val hours = seconds / 3600
        val minutes = (seconds % 3600) / 60
        val secs = seconds % 60

        return if (hours > 0) {
            String.format("%02d:%02d:%02d", hours, minutes, secs)
        } else {
            String.format("%02d:%02d", minutes, secs)
        }
    }
}

/**
 * UI state for the Recording screen.
 */
data class RecordingUiState(
    val isRecording: Boolean = false,
    val isPaused: Boolean = false,
    val recordingDurationSeconds: Long = 0
)
