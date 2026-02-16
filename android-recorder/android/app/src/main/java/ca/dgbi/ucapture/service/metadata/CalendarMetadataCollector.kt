package ca.dgbi.ucapture.service.metadata

import android.Manifest
import android.content.ContentUris
import android.content.Context
import android.content.pm.PackageManager
import android.database.Cursor
import android.provider.CalendarContract
import androidx.core.content.ContextCompat
import ca.dgbi.ucapture.service.ChunkManager
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.MutableSharedFlow
import kotlinx.coroutines.sync.Mutex
import kotlinx.coroutines.sync.withLock
import kotlinx.coroutines.withContext
import java.time.Instant
import java.util.concurrent.ConcurrentHashMap
import javax.inject.Inject
import javax.inject.Singleton

/**
 * Collects calendar event metadata during audio recording sessions.
 *
 * Features:
 * - Queries Android Calendar Provider for events overlapping with recording chunks
 * - Caches results per chunk to avoid redundant queries
 * - Extracts title, description, location, times, and attendees
 * - Graceful handling of missing permissions (continues without calendar data)
 *
 * @property context Application context for calendar access and permission checks
 */
@Singleton
class CalendarMetadataCollector @Inject constructor(
    private val context: Context
) : MetadataCollector<CalendarEvent> {

    companion object {
        const val COLLECTOR_ID = "calendar"

        // Projection for events query
        private val EVENTS_PROJECTION = arrayOf(
            CalendarContract.Events._ID,
            CalendarContract.Events.TITLE,
            CalendarContract.Events.DESCRIPTION,
            CalendarContract.Events.EVENT_LOCATION,
            CalendarContract.Events.DTSTART,
            CalendarContract.Events.DTEND,
            CalendarContract.Events.CALENDAR_DISPLAY_NAME,
            CalendarContract.Events.ALL_DAY
        )

        // Projection for attendees query
        private val ATTENDEES_PROJECTION = arrayOf(
            CalendarContract.Attendees.ATTENDEE_NAME,
            CalendarContract.Attendees.ATTENDEE_EMAIL
        )

        // Column indices for events
        private const val COL_ID = 0
        private const val COL_TITLE = 1
        private const val COL_DESCRIPTION = 2
        private const val COL_LOCATION = 3
        private const val COL_DTSTART = 4
        private const val COL_DTEND = 5
        private const val COL_CALENDAR_NAME = 6
        private const val COL_ALL_DAY = 7
    }

    override val collectorId: String = COLLECTOR_ID

    private val _metadataFlow = MutableSharedFlow<CalendarEvent>(replay = 10)
    override val metadataFlow: Flow<CalendarEvent> = _metadataFlow

    // Cache: chunk file path -> list of events (to avoid re-querying)
    private val chunkCache = ConcurrentHashMap<String, List<CalendarEvent>>()
    private val cacheMutex = Mutex()

    private var recordingStartTime: Long = 0
    private var isCollecting = false

    /**
     * Check if calendar access is available.
     *
     * @return true if READ_CALENDAR permission is granted
     */
    override suspend fun isAvailable(): Boolean {
        return hasCalendarPermission()
    }

    private fun hasCalendarPermission(): Boolean {
        return ContextCompat.checkSelfPermission(
            context,
            Manifest.permission.READ_CALENDAR
        ) == PackageManager.PERMISSION_GRANTED
    }

    /**
     * Start collecting calendar metadata.
     *
     * Unlike location collection, calendar data is queried on-demand per chunk
     * rather than continuously. This method records the start time and enables
     * collection mode.
     */
    override suspend fun startCollecting() {
        if (isCollecting) return

        recordingStartTime = System.currentTimeMillis()
        chunkCache.clear()
        isCollecting = true
    }

    /**
     * Stop collecting calendar metadata.
     */
    override suspend fun stopCollecting() {
        isCollecting = false
    }

    /**
     * Get calendar events overlapping with a specific chunk's time range.
     *
     * Results are cached per chunk to avoid redundant calendar queries.
     *
     * @param chunk The completed chunk to get calendar events for
     * @return List of CalendarEvent objects overlapping with the chunk's time range
     */
    override suspend fun getMetadataForChunk(chunk: ChunkManager.CompletedChunk): List<CalendarEvent> {
        if (!hasCalendarPermission()) return emptyList()

        // Use chunk file path as cache key
        val cacheKey = chunk.file.absolutePath

        // Return cached result if available
        chunkCache[cacheKey]?.let { return it }

        // Query calendar and cache result
        return cacheMutex.withLock {
            // Double-check after acquiring lock
            chunkCache[cacheKey]?.let { return@withLock it }

            val startTimeMs = chunk.startTime.toInstant().toEpochMilli()
            val endTimeMs = chunk.endTime.toInstant().toEpochMilli()
            val events = queryCalendarEvents(startTimeMs, endTimeMs)
            chunkCache[cacheKey] = events

            // Emit events to flow for UI observation
            events.forEach { _metadataFlow.tryEmit(it) }

            events
        }
    }

    /**
     * Query calendar provider for events overlapping with the given time range.
     *
     * An event overlaps if:
     * - Event starts before time range ends AND
     * - Event ends after time range starts
     */
    private suspend fun queryCalendarEvents(startTimeMs: Long, endTimeMs: Long): List<CalendarEvent> =
        withContext(Dispatchers.IO) {
            if (!hasCalendarPermission()) return@withContext emptyList()

            val events = mutableListOf<CalendarEvent>()

            // Query for events that overlap with the time range
            // Overlap condition: event.start < range.end AND event.end > range.start
            val selection = "(${CalendarContract.Events.DTSTART} < ?) AND " +
                    "(${CalendarContract.Events.DTEND} > ?) AND " +
                    "(${CalendarContract.Events.DELETED} = 0)"
            val selectionArgs = arrayOf(
                endTimeMs.toString(),
                startTimeMs.toString()
            )

            try {
                context.contentResolver.query(
                    CalendarContract.Events.CONTENT_URI,
                    EVENTS_PROJECTION,
                    selection,
                    selectionArgs,
                    "${CalendarContract.Events.DTSTART} ASC"
                )?.use { cursor ->
                    while (cursor.moveToNext()) {
                        val event = cursorToCalendarEvent(cursor)
                        if (event != null) {
                            events.add(event)
                        }
                    }
                }
            } catch (e: SecurityException) {
                // Permission was revoked during query
                return@withContext emptyList()
            }

            events
        }

    /**
     * Convert a cursor row to a CalendarEvent object.
     */
    private suspend fun cursorToCalendarEvent(cursor: Cursor): CalendarEvent? {
        return try {
            val eventId = cursor.getLong(COL_ID)
            val title = cursor.getString(COL_TITLE) ?: return null
            val startMs = cursor.getLong(COL_DTSTART)
            val endMs = cursor.getLong(COL_DTEND)

            // Skip events with invalid times
            if (startMs <= 0 || endMs <= 0) return null

            val attendees = queryAttendees(eventId)

            CalendarEvent(
                eventId = eventId,
                title = title,
                description = cursor.getString(COL_DESCRIPTION),
                location = cursor.getString(COL_LOCATION),
                startTime = Instant.ofEpochMilli(startMs),
                endTime = Instant.ofEpochMilli(endMs),
                attendees = attendees,
                calendarName = cursor.getString(COL_CALENDAR_NAME) ?: "Unknown",
                isAllDay = cursor.getInt(COL_ALL_DAY) == 1
            )
        } catch (e: Exception) {
            null
        }
    }

    /**
     * Query attendees for a specific calendar event.
     */
    private suspend fun queryAttendees(eventId: Long): List<String> =
        withContext(Dispatchers.IO) {
            if (!hasCalendarPermission()) return@withContext emptyList()

            val attendees = mutableListOf<String>()

            try {
                val uri = CalendarContract.Attendees.CONTENT_URI
                val selection = "${CalendarContract.Attendees.EVENT_ID} = ?"
                val selectionArgs = arrayOf(eventId.toString())

                context.contentResolver.query(
                    uri,
                    ATTENDEES_PROJECTION,
                    selection,
                    selectionArgs,
                    null
                )?.use { cursor ->
                    while (cursor.moveToNext()) {
                        val name = cursor.getString(0)
                        val email = cursor.getString(1)

                        // Prefer name over email, but use email if name is empty
                        val attendee = when {
                            !name.isNullOrBlank() -> name
                            !email.isNullOrBlank() -> email
                            else -> null
                        }
                        attendee?.let { attendees.add(it) }
                    }
                }
            } catch (e: SecurityException) {
                // Permission was revoked
                return@withContext emptyList()
            }

            attendees
        }

    /**
     * Clear the event cache.
     *
     * Call this when starting a new recording session.
     */
    fun clearCache() {
        chunkCache.clear()
    }

    /**
     * Get the number of cached chunk queries.
     */
    fun getCacheSize(): Int = chunkCache.size

    /**
     * Check if currently in collection mode.
     */
    fun isCurrentlyCollecting(): Boolean = isCollecting
}
