package ca.dgbi.ucapture.di

import ca.dgbi.ucapture.data.preferences.StoragePreferences
import ca.dgbi.ucapture.data.remote.CloudStorageProvider
import ca.dgbi.ucapture.data.remote.CloudflareWorkerStorage
import ca.dgbi.ucapture.data.remote.GoogleDriveStorage
import dagger.Module
import dagger.Provides
import dagger.hilt.InstallIn
import dagger.hilt.components.SingletonComponent
import kotlinx.coroutines.flow.first
import kotlinx.coroutines.runBlocking
import java.io.File
import javax.inject.Singleton

/**
 * Hilt module for network/cloud storage dependencies.
 *
 * Provides a [CloudStorageProvider] that delegates to either [CloudflareWorkerStorage]
 * or [GoogleDriveStorage] based on the current [StoragePreferences] setting.
 * The active provider is resolved on each operation, so toggling the setting
 * takes effect immediately without restarting the app.
 * Default is Google Drive.
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
    ): CloudStorageProvider = object : CloudStorageProvider {

        private suspend fun active(): CloudStorageProvider =
            if (storagePreferences.useCloudflareWorker.first()) cloudflareWorkerStorage else googleDriveStorage

        override val providerId: String
            get() = runBlocking { active().providerId }

        override suspend fun isAuthenticated() = active().isAuthenticated()

        override suspend fun getTargetFolderId() = active().getTargetFolderId()

        override suspend fun setTargetFolderId(folderId: String) =
            active().setTargetFolderId(folderId)

        override suspend fun upload(audioFile: File, metadataFile: File?, folderId: String?) =
            active().upload(audioFile, metadataFile, folderId)

        override suspend fun verifyUpload(fileId: String, expectedMd5: String) =
            active().verifyUpload(fileId, expectedMd5)

        override suspend fun delete(fileId: String) = active().delete(fileId)

        override suspend fun listFolders(parentId: String?) = active().listFolders(parentId)
    }
}
