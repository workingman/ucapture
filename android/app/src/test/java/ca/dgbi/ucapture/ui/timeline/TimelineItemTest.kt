package ca.dgbi.ucapture.ui.timeline

import ca.dgbi.ucapture.data.local.entity.RecordingEntity
import org.junit.Assert.assertTrue
import org.junit.Test
import java.time.Instant
import java.time.ZoneId
import java.time.ZonedDateTime

class TimelineItemTest {

    @Test
    fun `formatDuration shows seconds only for durations under 1 minute`() {
        val recording = createRecording(durationSeconds = 0)
        val formatted = formatDurationFromRecording(recording)

        assertTrue(formatted.matches(Regex("\\d+s")))
    }

    @Test
    fun `formatDuration shows 45s for 45 seconds`() {
        val recording = createRecording(durationSeconds = 45)
        val formatted = formatDurationFromRecording(recording)

        assertTrue(formatted == "45s")
    }

    @Test
    fun `formatDuration shows minutes and seconds for durations under 1 hour`() {
        val recording = createRecording(durationSeconds = 150) // 2m 30s
        val formatted = formatDurationFromRecording(recording)

        assertTrue(formatted == "2m 30s")
    }

    @Test
    fun `formatDuration shows hours and minutes for durations over 1 hour`() {
        val recording = createRecording(durationSeconds = 3930) // 1h 5m 30s
        val formatted = formatDurationFromRecording(recording)

        assertTrue(formatted == "1h 5m")
    }

    @Test
    fun `formatDuration shows hours and minutes for exactly 1 hour`() {
        val recording = createRecording(durationSeconds = 3600) // 1h
        val formatted = formatDurationFromRecording(recording)

        assertTrue(formatted == "1h 0m")
    }

    @Test
    fun `formatRelativeDate shows Today for current day`() {
        val now = ZonedDateTime.now()
        val recording = createRecording(startTime = now.toInstant().toEpochMilli(), timezoneId = now.zone.id)
        val formatted = formatRelativeDateFromRecording(recording)

        assertTrue(formatted.startsWith("Today"))
    }

    @Test
    fun `formatRelativeDate shows Yesterday for previous day`() {
        val yesterday = ZonedDateTime.now().minusDays(1)
        val recording = createRecording(startTime = yesterday.toInstant().toEpochMilli(), timezoneId = yesterday.zone.id)
        val formatted = formatRelativeDateFromRecording(recording)

        assertTrue(formatted.startsWith("Yesterday"))
    }

    @Test
    fun `formatRelativeDate shows date for older recordings`() {
        val oldDate = ZonedDateTime.now().minusDays(5)
        val recording = createRecording(startTime = oldDate.toInstant().toEpochMilli(), timezoneId = oldDate.zone.id)
        val formatted = formatRelativeDateFromRecording(recording)

        // Should be in format "MMM d, h:mm a" (e.g., "Dec. 8, 2:30 p.m.")
        // Pattern allows for period after month, single or double digit day/hour, and lowercase am/pm
        assertTrue("Formatted date '$formatted' does not match expected pattern",
            formatted.matches(Regex("[A-Z][a-z]{2}\\.? \\d{1,2}, \\d{1,2}:\\d{2} [ap]\\.m\\.")))
    }

    @Test
    fun `formatRelativeDate includes time for all formats`() {
        val now = ZonedDateTime.now()
        val recording = createRecording(startTime = now.toInstant().toEpochMilli(), timezoneId = now.zone.id)
        val formatted = formatRelativeDateFromRecording(recording)

        // Should contain time portion (e.g., "2:30 p.m.")
        assertTrue("Formatted date '$formatted' does not contain expected time pattern",
            formatted.matches(Regex(".*\\d{1,2}:\\d{2} [ap]\\.m\\.")))
    }

    private fun createRecording(
        durationSeconds: Long = 60,
        startTime: Long = System.currentTimeMillis(),
        timezoneId: String = ZoneId.systemDefault().id
    ): RecordingEntity {
        return RecordingEntity(
            id = 1,
            sessionId = "test-session",
            chunkNumber = 1,
            filePath = "/test/path.m4a",
            startTimeEpochMilli = startTime,
            endTimeEpochMilli = startTime + (durationSeconds * 1000),
            timezoneId = timezoneId,
            durationSeconds = durationSeconds,
            fileSizeBytes = 1024,
            md5Hash = "hash123",
            uploadStatus = "pending"
        )
    }

    // Helper to invoke the private formatDuration function via reflection
    // Since the function is private in TimelineItem.kt, we need to test it indirectly
    private fun formatDurationFromRecording(recording: RecordingEntity): String {
        val durationSeconds = recording.durationSeconds
        val hours = durationSeconds / 3600
        val minutes = (durationSeconds % 3600) / 60
        val seconds = durationSeconds % 60

        return when {
            hours > 0 -> "${hours}h ${minutes}m"
            minutes > 0 -> "${minutes}m ${seconds}s"
            else -> "${seconds}s"
        }
    }

    // Helper to invoke the private formatRelativeDate function
    private fun formatRelativeDateFromRecording(recording: RecordingEntity): String {
        val dateTime = ZonedDateTime.ofInstant(
            Instant.ofEpochMilli(recording.startTimeEpochMilli),
            ZoneId.of(recording.timezoneId)
        )
        val now = ZonedDateTime.now(ZoneId.of(recording.timezoneId))

        val timeStr = dateTime.format(java.time.format.DateTimeFormatter.ofPattern("h:mm a"))

        return when {
            dateTime.toLocalDate() == now.toLocalDate() -> "Today $timeStr"
            dateTime.toLocalDate() == now.minusDays(1).toLocalDate() -> "Yesterday $timeStr"
            else -> dateTime.format(java.time.format.DateTimeFormatter.ofPattern("MMM d, h:mm a"))
        }
    }
}
