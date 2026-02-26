package ca.dgbi.ucapture.di

import ca.dgbi.ucapture.data.remote.CloudStorageProvider
import ca.dgbi.ucapture.data.remote.CloudflareWorkerStorage
import dagger.Binds
import dagger.Module
import dagger.hilt.InstallIn
import dagger.hilt.components.SingletonComponent
import javax.inject.Singleton

/**
 * Hilt module for network/cloud storage dependencies.
 *
 * Binds [CloudflareWorkerStorage] as the active [CloudStorageProvider].
 * Recordings are uploaded to the Cloudflare Worker at audio-processor.geoff-ec6.workers.dev
 * rather than directly to Google Drive.
 */
@Module
@InstallIn(SingletonComponent::class)
abstract class NetworkModule {

    @Binds
    @Singleton
    abstract fun bindCloudStorageProvider(
        cloudflareWorkerStorage: CloudflareWorkerStorage
    ): CloudStorageProvider
}
