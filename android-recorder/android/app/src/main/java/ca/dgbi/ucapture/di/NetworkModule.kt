package ca.dgbi.ucapture.di

import ca.dgbi.ucapture.data.preferences.StoragePreferences
import ca.dgbi.ucapture.data.remote.CloudStorageProvider
import ca.dgbi.ucapture.data.remote.CloudflareWorkerStorage
import ca.dgbi.ucapture.data.remote.GoogleDriveStorage
import dagger.Module
import dagger.Provides
import dagger.hilt.InstallIn
import dagger.hilt.components.SingletonComponent
import kotlinx.coroutines.runBlocking
import javax.inject.Singleton

/**
 * Hilt module for network/cloud storage dependencies.
 *
 * Provides [CloudStorageProvider] that switches between Cloudflare Worker
 * and Google Drive based on the [StoragePreferences] setting.
 * Default is Cloudflare Worker.
 */
@Module
@InstallIn(SingletonComponent::class)
object NetworkModule {

    @Provides
    @Singleton
    fun provideCloudStorageProvider(
        cloudflareWorkerStorage: CloudflareWorkerStorage,
        googleDriveStorage: GoogleDriveStorage,
        storagePreferences: StoragePreferences
    ): CloudStorageProvider {
        // Use runBlocking to get the preference synchronously for injection
        // In normal operation, this reads from cached preference
        val useCloudflare = runBlocking {
            storagePreferences.isUsingCloudflareWorker()
        }
        return if (useCloudflare) cloudflareWorkerStorage else googleDriveStorage
    }
}
