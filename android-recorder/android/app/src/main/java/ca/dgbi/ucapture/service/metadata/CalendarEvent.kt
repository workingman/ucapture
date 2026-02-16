package ca.dgbi.ucapture.service.metadata

import java.time.Instant

/**
 * Represents a calendar event that overlaps with a recording chunk.
 *
 * @property eventId Unique ID of the calendar event
 * @property title Event title/summary
 * @property description Event description, null if not set
 * @property location Event location string, null if not set
 * @property startTime Event start time
 * @property endTime Event end time
 * @property attendees List of attendee names/emails
 * @property calendarName Name of the calendar containing this event
 * @property isAllDay Whether this is an all-day event
 */
data class CalendarEvent(
    val eventId: Long,
    val title: String,
    val description: String?,
    val location: String?,
    val startTime: Instant,
    val endTime: Instant,
    val attendees: List<String>,
    val calendarName: String,
    val isAllDay: Boolean
)
