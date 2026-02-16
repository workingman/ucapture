package ca.dgbi.ucapture.data.local

import androidx.room.Database
import androidx.room.RoomDatabase
import androidx.room.TypeConverters
import ca.dgbi.ucapture.data.local.dao.CalendarEventDao
import ca.dgbi.ucapture.data.local.dao.LocationSampleDao
import ca.dgbi.ucapture.data.local.dao.RecordingDao
import ca.dgbi.ucapture.data.local.entity.CalendarEventEntity
import ca.dgbi.ucapture.data.local.entity.LocationSampleEntity
import ca.dgbi.ucapture.data.local.entity.RecordingEntity

/**
 * Room database for uCapture app.
 *
 * Contains recordings and their associated metadata (location samples, calendar events).
 */
@Database(
    entities = [
        RecordingEntity::class,
        LocationSampleEntity::class,
        CalendarEventEntity::class
    ],
    version = 1,
    exportSchema = true
)
@TypeConverters(Converters::class)
abstract class AppDatabase : RoomDatabase() {
    abstract fun recordingDao(): RecordingDao
    abstract fun locationSampleDao(): LocationSampleDao
    abstract fun calendarEventDao(): CalendarEventDao

    companion object {
        const val DATABASE_NAME = "ucapture.db"
    }
}
