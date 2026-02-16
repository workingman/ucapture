package ca.dgbi.ucapture.ui.timeline

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import ca.dgbi.ucapture.data.local.relation.RecordingWithMetadata
import ca.dgbi.ucapture.data.remote.UploadScheduler
import ca.dgbi.ucapture.data.repository.RecordingRepository
import dagger.hilt.android.lifecycle.HiltViewModel
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.SharingStarted
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.map
import kotlinx.coroutines.flow.stateIn
import javax.inject.Inject

/**
 * ViewModel for the Timeline screen.
 *
 * Displays all recordings with their upload status and metadata.
 */
@HiltViewModel
class TimelineViewModel @Inject constructor(
    private val recordingRepository: RecordingRepository,
    private val uploadScheduler: UploadScheduler
) : ViewModel() {

    private val _isLoading = MutableStateFlow(true)
    val isLoading: StateFlow<Boolean> = _isLoading.asStateFlow()

    /**
     * All recordings sorted by creation time (newest first).
     */
    val recordings: StateFlow<List<RecordingWithMetadata>> =
        recordingRepository.allRecordingsWithMetadata
            .map { list ->
                _isLoading.value = false
                list.sortedByDescending { it.recording.startTimeEpochMilli }
            }
            .stateIn(
                scope = viewModelScope,
                started = SharingStarted.WhileSubscribed(5000),
                initialValue = emptyList()
            )

    /**
     * Check if there are any failed uploads.
     */
    val hasFailedUploads: StateFlow<Boolean> = recordings
        .map { list ->
            list.any { it.recording.uploadStatus == "failed" }
        }
        .stateIn(
            scope = viewModelScope,
            started = SharingStarted.WhileSubscribed(5000),
            initialValue = false
        )

    /**
     * Retry all failed uploads.
     */
    fun retryFailedUploads() {
        uploadScheduler.retryFailedUploads(viewModelScope)
    }
}
