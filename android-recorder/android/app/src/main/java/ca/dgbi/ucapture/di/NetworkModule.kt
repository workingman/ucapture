package ca.dgbi.ucapture.di

import ca.dgbi.ucapture.data.remote.CloudStorageProvider
import ca.dgbi.ucapture.data.remote.GoogleDriveStorage
import dagger.Binds
import dagger.Module
import dagger.hilt.InstallIn
import dagger.hilt.components.SingletonComponent
import javax.inject.Singleton

/**
 * Hilt module for network/cloud storage dependencies.
 */
@Module
@InstallIn(SingletonComponent::class)
abstract class NetworkModule {

    @Binds
    @Singleton
    abstract fun bindCloudStorageProvider(
        googleDriveStorage: GoogleDriveStorage
    ): CloudStorageProvider
}
