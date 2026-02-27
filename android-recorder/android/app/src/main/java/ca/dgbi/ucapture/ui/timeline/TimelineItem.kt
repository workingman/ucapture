package ca.dgbi.ucapture.ui.timeline

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.CheckCircle
import androidx.compose.material.icons.filled.Info
import androidx.compose.material.icons.filled.Warning
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.Icon
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import ca.dgbi.ucapture.data.local.entity.RecordingEntity
import ca.dgbi.ucapture.data.local.relation.RecordingWithMetadata
import java.time.Instant
import java.time.ZoneId
import java.time.ZonedDateTime
import java.time.format.DateTimeFormatter

/**
 * Reusable composable for a single recording item in the timeline.
 */
@Composable
fun TimelineItem(
    recordingWithMetadata: RecordingWithMetadata,
    modifier: Modifier = Modifier
) {
    val recording = recordingWithMetadata.recording

    Card(
        modifier = modifier.fillMaxWidth(),
        elevation = CardDefaults.cardElevation(defaultElevation = 2.dp)
    ) {
        Row(
            modifier = Modifier
                .fillMaxWidth()
                .padding(16.dp),
            horizontalArrangement = Arrangement.SpaceBetween,
            verticalAlignment = Alignment.CenterVertically
        ) {
            // Left side: Recording info
            Column(
                modifier = Modifier.weight(1f),
                verticalArrangement = Arrangement.spacedBy(4.dp)
            ) {
                Text(
                    text = formatRelativeDate(recording),
                    style = MaterialTheme.typography.bodyLarge,
                    fontWeight = FontWeight.Medium
                )
                Text(
                    text = formatDuration(recording.durationSeconds),
                    style = MaterialTheme.typography.bodyMedium,
                    color = MaterialTheme.colorScheme.onSurfaceVariant
                )
                // Show metadata counts if present
                if (recordingWithMetadata.locationSamples.isNotEmpty()) {
                    Text(
                        text = "${recordingWithMetadata.locationSamples.size} locations",
                        style = MaterialTheme.typography.bodySmall,
                        color = MaterialTheme.colorScheme.onSurfaceVariant
                    )
                }
            }

            // Right side: Upload status icon
            UploadStatusIcon(uploadStatus = recording.uploadStatus)
        }
    }
}

/**
 * Display the upload status icon based on the current status.
 */
@Composable
private fun UploadStatusIcon(uploadStatus: String) {
    when (uploadStatus) {
        RecordingEntity.UploadStatus.UPLOADED -> {
            Icon(
                imageVector = Icons.Default.CheckCircle,
                contentDescription = "Uploaded",
                tint = Color(0xFF4CAF50),
                modifier = Modifier.size(24.dp)
            )
        }
        RecordingEntity.UploadStatus.UPLOADING -> {
            CircularProgressIndicator(
                modifier = Modifier.size(24.dp),
                strokeWidth = 2.dp
            )
        }
        RecordingEntity.UploadStatus.PENDING -> {
            Icon(
                imageVector = Icons.Default.Info,
                contentDescription = "Pending upload",
                tint = MaterialTheme.colorScheme.onSurfaceVariant,
                modifier = Modifier.size(24.dp)
            )
        }
        RecordingEntity.UploadStatus.FAILED -> {
            Icon(
                imageVector = Icons.Default.Warning,
                contentDescription = "Upload failed",
                tint = MaterialTheme.colorScheme.error,
                modifier = Modifier.size(24.dp)
            )
        }
    }
}

/**
 * Format recording date/time relative to now.
 * Examples: "Today 2:30 PM", "Yesterday 3:45 PM", "Dec 12, 3:45 PM"
 */
private fun formatRelativeDate(recording: RecordingEntity): String {
    val dateTime = ZonedDateTime.ofInstant(
        Instant.ofEpochMilli(recording.startTimeEpochMilli),
        ZoneId.of(recording.timezoneId)
    )
    val now = ZonedDateTime.now(ZoneId.of(recording.timezoneId))

    return when {
        dateTime.toLocalDate() == now.toLocalDate() -> "Today ${formatTime(dateTime)}"
        dateTime.toLocalDate() == now.minusDays(1).toLocalDate() -> "Yesterday ${formatTime(dateTime)}"
        else -> dateTime.format(DateTimeFormatter.ofPattern("MMM d, h:mm a"))
    }
}

/**
 * Format time as "2:30 PM"
 */
private fun formatTime(dateTime: ZonedDateTime): String {
    return dateTime.format(DateTimeFormatter.ofPattern("h:mm a"))
}

/**
 * Format duration in seconds to human-readable string.
 * Examples: "2m 30s", "1h 5m", "45s"
 */
private fun formatDuration(durationSeconds: Long): String {
    val hours = durationSeconds / 3600
    val minutes = (durationSeconds % 3600) / 60
    val seconds = durationSeconds % 60

    return when {
        hours > 0 -> "${hours}h ${minutes}m"
        minutes > 0 -> "${minutes}m ${seconds}s"
        else -> "${seconds}s"
    }
}
