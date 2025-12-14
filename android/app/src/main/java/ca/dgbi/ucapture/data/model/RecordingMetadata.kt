package ca.dgbi.ucapture.data.model

import ca.dgbi.ucapture.data.local.entity.CalendarEventEntity
import ca.dgbi.ucapture.data.local.entity.LocationSampleEntity
import ca.dgbi.ucapture.data.local.entity.RecordingEntity
import com.google.gson.Gson
import com.google.gson.reflect.TypeToken
import java.io.File
import java.time.Instant
import java.time.ZoneId
import java.time.ZonedDateTime
import java.time.format.DateTimeFormatter

/**
 * Aggregated metadata for a recording, suitable for JSON export.
 *
 * This is the structure written to sidecar files and uploaded to cloud storage
 * alongside the audio file.
 */
data class RecordingMetadata(
    val version: Int = 1,
    val recording: RecordingInfo,
    val location: LocationInfo?,
    val calendar: CalendarInfo?
) {
    data class RecordingInfo(
        val sessionId: String,
        val chunkNumber: Int,
        val filename: String,
        val startTime: String,
        val endTime: String,
        val durationSeconds: Long,
        val fileSizeBytes: Long,
        val md5Hash: String?
    )

    data class LocationInfo(
        val sampleCount: Int,
        val samples: List<LocationSampleInfo>
    )

    data class LocationSampleInfo(
        val latitude: Double,
        val longitude: Double,
        val altitude: Double?,
        val accuracy: Float,
        val speed: Float?,
        val bearing: Float?,
        val timestamp: String,
        val provider: String
    )

    data class CalendarInfo(
        val eventCount: Int,
        val events: List<CalendarEventInfo>
    )

    data class CalendarEventInfo(
        val eventId: Long,
        val title: String,
        val description: String?,
        val location: String?,
        val startTime: String,
        val endTime: String,
        val attendees: List<String>,
        val calendarName: String,
        val isAllDay: Boolean
    )

    companion object {
        private val isoFormatter = DateTimeFormatter.ISO_OFFSET_DATE_TIME
        private val gson = Gson()

        /**
         * Build RecordingMetadata from Room entities.
         */
        fun fromEntities(
            recording: RecordingEntity,
            locationSamples: List<LocationSampleEntity>,
            calendarEvents: List<CalendarEventEntity>
        ): RecordingMetadata {
            val timezone = ZoneId.of(recording.timezoneId)

            return RecordingMetadata(
                recording = RecordingInfo(
                    sessionId = recording.sessionId,
                    chunkNumber = recording.chunkNumber,
                    filename = File(recording.filePath).name,
                    startTime = formatTime(recording.startTimeEpochMilli, timezone),
                    endTime = formatTime(recording.endTimeEpochMilli, timezone),
                    durationSeconds = recording.durationSeconds,
                    fileSizeBytes = recording.fileSizeBytes,
                    md5Hash = recording.md5Hash
                ),
                location = if (locationSamples.isNotEmpty()) {
                    LocationInfo(
                        sampleCount = locationSamples.size,
                        samples = locationSamples.map { it.toInfo() }
                    )
                } else null,
                calendar = if (calendarEvents.isNotEmpty()) {
                    CalendarInfo(
                        eventCount = calendarEvents.size,
                        events = calendarEvents.map { it.toInfo() }
                    )
                } else null
            )
        }

        private fun formatTime(epochMilli: Long, zone: ZoneId): String {
            return ZonedDateTime.ofInstant(
                Instant.ofEpochMilli(epochMilli),
                zone
            ).format(isoFormatter)
        }

        private fun LocationSampleEntity.toInfo() = LocationSampleInfo(
            latitude = latitude,
            longitude = longitude,
            altitude = altitude,
            accuracy = accuracy,
            speed = speed,
            bearing = bearing,
            timestamp = Instant.ofEpochMilli(timestampEpochMilli).toString(),
            provider = provider
        )

        private fun CalendarEventEntity.toInfo(): CalendarEventInfo {
            val attendees: List<String> = try {
                gson.fromJson(attendeesJson, object : TypeToken<List<String>>() {}.type)
            } catch (e: Exception) {
                emptyList()
            }

            return CalendarEventInfo(
                eventId = eventId,
                title = title,
                description = description,
                location = location,
                startTime = Instant.ofEpochMilli(startTimeEpochMilli).toString(),
                endTime = Instant.ofEpochMilli(endTimeEpochMilli).toString(),
                attendees = attendees,
                calendarName = calendarName,
                isAllDay = isAllDay
            )
        }
    }
}
