package ca.dgbi.ucapture.di

import android.content.Context
import androidx.room.Room
import ca.dgbi.ucapture.data.local.AppDatabase
import ca.dgbi.ucapture.data.local.dao.CalendarEventDao
import ca.dgbi.ucapture.data.local.dao.LocationSampleDao
import ca.dgbi.ucapture.data.local.dao.RecordingDao
import dagger.Module
import dagger.Provides
import dagger.hilt.InstallIn
import dagger.hilt.android.qualifiers.ApplicationContext
import dagger.hilt.components.SingletonComponent
import javax.inject.Singleton

@Module
@InstallIn(SingletonComponent::class)
object DatabaseModule {

    @Provides
    @Singleton
    fun provideAppDatabase(
        @ApplicationContext context: Context
    ): AppDatabase {
        return Room.databaseBuilder(
            context,
            AppDatabase::class.java,
            AppDatabase.DATABASE_NAME
        ).build()
    }

    @Provides
    fun provideRecordingDao(database: AppDatabase): RecordingDao =
        database.recordingDao()

    @Provides
    fun provideLocationSampleDao(database: AppDatabase): LocationSampleDao =
        database.locationSampleDao()

    @Provides
    fun provideCalendarEventDao(database: AppDatabase): CalendarEventDao =
        database.calendarEventDao()
}
