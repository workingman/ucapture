package ca.dgbi.ucapture.di

import android.content.Context
import ca.dgbi.ucapture.service.AudioRecorder
import ca.dgbi.ucapture.service.ChunkManager
import ca.dgbi.ucapture.service.metadata.LocationMetadataCollector
import ca.dgbi.ucapture.service.metadata.MetadataCollectorManager
import dagger.Module
import dagger.Provides
import dagger.hilt.InstallIn
import dagger.hilt.android.qualifiers.ApplicationContext
import dagger.hilt.components.SingletonComponent
import javax.inject.Singleton

@Module
@InstallIn(SingletonComponent::class)
object AppModule {

    @Provides
    @Singleton
    fun provideAudioRecorder(
        @ApplicationContext context: Context
    ): AudioRecorder {
        return AudioRecorder(context)
    }

    @Provides
    @Singleton
    fun provideChunkManager(): ChunkManager {
        return ChunkManager()
    }

    @Provides
    @Singleton
    fun provideLocationMetadataCollector(
        @ApplicationContext context: Context
    ): LocationMetadataCollector {
        return LocationMetadataCollector(context)
    }

    @Provides
    @Singleton
    fun provideMetadataCollectorManager(
        locationCollector: LocationMetadataCollector
    ): MetadataCollectorManager {
        return MetadataCollectorManager().apply {
            register(locationCollector)
        }
    }
}
