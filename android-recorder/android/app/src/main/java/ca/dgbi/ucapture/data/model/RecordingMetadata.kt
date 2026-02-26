package ca.dgbi.ucapture.data.model

import ca.dgbi.ucapture.data.local.entity.CalendarEventEntity
import ca.dgbi.ucapture.data.local.entity.LocationSampleEntity
import ca.dgbi.ucapture.data.local.entity.RecordingEntity
import com.google.gson.FieldNamingPolicy
import com.google.gson.GsonBuilder
import com.google.gson.JsonObject
import com.google.gson.reflect.TypeToken
import java.time.Instant

/**
 * Aggregated metadata for a recording, matching the Cloudflare Worker upload API schema.
 *
 * Uploaded as a JSON file part alongside the audio in the multipart POST to /v1/upload.
 * All timestamps are UTC ISO 8601 strings (e.g. "2026-02-25T14:30:00Z").
 */
data class RecordingMetadata(
    val recording: RecordingInfo,
    val device: DeviceInfo,
    val location: LocationInfo? = null,
    val calendar: CalendarInfo? = null
) {
    /**
     * Core recording parameters. Field names use camelCase here and are serialized
     * as snake_case by the FieldNamingPolicy configured in [toJson].
     */
    data class RecordingInfo(
        val startedAt: String,
        val endedAt: String,
        val durationSeconds: Double,
        val audioFormat: String = "aac",
        val sampleRate: Int = 44100,
        val channels: Int = 1,
        val bitrate: Int = 128000,
        val fileSizeBytes: Long
    )

    data class DeviceInfo(
        val model: String,
        val osVersion: String,
        val appVersion: String
    )

    /** Single best-accuracy GPS point captured during the recording. */
    data class LocationInfo(
        val latitude: Double,
        val longitude: Double,
        val accuracyMeters: Float,
        val capturedAt: String,
        val address: String? = null
    )

    /** First calendar event that overlaps with the recording. */
    data class CalendarInfo(
        val eventId: String,
        val eventTitle: String,
        val attendees: List<String>
    )

    /**
     * Serialize to JSON string, omitting optional sections that are null.
     *
     * Uses LOWER_CASE_WITH_UNDERSCORES naming so Kotlin camelCase fields
     * (e.g. [RecordingInfo.startedAt]) map to snake_case keys in the output
     * (e.g. `started_at`) as required by the Worker Zod schema.
     */
    fun toJson(): String {
        val gson = GsonBuilder()
            .setFieldNamingPolicy(FieldNamingPolicy.LOWER_CASE_WITH_UNDERSCORES)
            .setPrettyPrinting()
            .create()

        val root = JsonObject()
        root.add("recording", gson.toJsonTree(recording))
        root.add("device", gson.toJsonTree(device))
        location?.let { root.add("location", gson.toJsonTree(it)) }
        calendar?.let { root.add("calendar", gson.toJsonTree(it)) }
        return gson.toJson(root)
    }

    companion object {
        // Reuse a single Gson instance for attendees list parsing (field names irrelevant for List<String>)
        private val gson = GsonBuilder()
            .setFieldNamingPolicy(FieldNamingPolicy.LOWER_CASE_WITH_UNDERSCORES)
            .create()

        /**
         * Build [RecordingMetadata] from Room entities.
         *
         * @param recording       The recording entity
         * @param locationSamples GPS samples collected during this chunk — the most-accurate
         *                        sample (lowest accuracy radius) is included in the output
         * @param calendarEvents  Events overlapping this chunk — the first is included
         * @param deviceInfo      Device model, OS version, and app version
         */
        fun fromEntities(
            recording: RecordingEntity,
            locationSamples: List<LocationSampleEntity>,
            calendarEvents: List<CalendarEventEntity>,
            deviceInfo: DeviceInfo
        ): RecordingMetadata {
            val startedAt = Instant.ofEpochMilli(recording.startTimeEpochMilli).toString()
            val endedAt = Instant.ofEpochMilli(recording.endTimeEpochMilli).toString()

            // Best accuracy = smallest radius in metres
            val locationInfo = locationSamples
                .minByOrNull { it.accuracy }
                ?.let { sample ->
                    LocationInfo(
                        latitude = sample.latitude,
                        longitude = sample.longitude,
                        accuracyMeters = sample.accuracy,
                        capturedAt = Instant.ofEpochMilli(sample.timestampEpochMilli).toString()
                    )
                }

            val calendarInfo = calendarEvents.firstOrNull()?.let { event ->
                val attendees: List<String> = try {
                    gson.fromJson(event.attendeesJson, object : TypeToken<List<String>>() {}.type)
                } catch (e: Exception) {
                    emptyList()
                }
                CalendarInfo(
                    eventId = event.eventId.toString(),
                    eventTitle = event.title,
                    attendees = attendees
                )
            }

            return RecordingMetadata(
                recording = RecordingInfo(
                    startedAt = startedAt,
                    endedAt = endedAt,
                    durationSeconds = recording.durationSeconds.toDouble(),
                    fileSizeBytes = recording.fileSizeBytes
                ),
                device = deviceInfo,
                location = locationInfo,
                calendar = calendarInfo
            )
        }
    }
}
