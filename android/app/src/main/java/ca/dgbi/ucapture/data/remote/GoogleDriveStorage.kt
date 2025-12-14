package ca.dgbi.ucapture.data.remote

import android.content.Context
import androidx.datastore.preferences.core.edit
import androidx.datastore.preferences.core.stringPreferencesKey
import androidx.datastore.preferences.preferencesDataStore
import com.google.api.client.http.FileContent
import com.google.api.services.drive.model.File as DriveFile
import android.util.Log
import dagger.hilt.android.qualifiers.ApplicationContext
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.flow.first
import kotlinx.coroutines.withContext
import java.io.File
import java.io.IOException
import javax.inject.Inject
import javax.inject.Singleton

private val Context.drivePreferences by preferencesDataStore("drive_preferences")

/**
 * Google Drive implementation of CloudStorageProvider.
 *
 * Uses Drive REST API v3 for file operations.
 * Stores target folder preference in DataStore.
 */
@Singleton
class GoogleDriveStorage @Inject constructor(
    @ApplicationContext private val context: Context,
    private val authManager: GoogleDriveAuthManager
) : CloudStorageProvider {

    companion object {
        private val KEY_TARGET_FOLDER = stringPreferencesKey("target_folder_id")
        private val KEY_TARGET_FOLDER_NAME = stringPreferencesKey("target_folder_name")
        private const val MIME_TYPE_AUDIO = "audio/mp4"
        private const val MIME_TYPE_JSON = "application/json"
        private const val MIME_TYPE_FOLDER = "application/vnd.google-apps.folder"
    }

    override val providerId: String = "google_drive"

    override suspend fun isAuthenticated(): Boolean {
        return authManager.isSignedIn()
    }

    override suspend fun getTargetFolderId(): String? {
        return context.drivePreferences.data.first()[KEY_TARGET_FOLDER]
    }

    override suspend fun setTargetFolderId(folderId: String) {
        context.drivePreferences.edit { prefs ->
            prefs[KEY_TARGET_FOLDER] = folderId
        }
    }

    /**
     * Get the stored target folder name.
     */
    suspend fun getTargetFolderName(): String? {
        return context.drivePreferences.data.first()[KEY_TARGET_FOLDER_NAME]
    }

    /**
     * Set the target folder ID and name together.
     */
    suspend fun setTargetFolder(folderId: String, folderName: String) {
        context.drivePreferences.edit { prefs ->
            prefs[KEY_TARGET_FOLDER] = folderId
            prefs[KEY_TARGET_FOLDER_NAME] = folderName
        }
    }

    override suspend fun upload(
        audioFile: File,
        metadataFile: File?,
        folderId: String?
    ): UploadResult = withContext(Dispatchers.IO) {
        try {
            if (!authManager.isSignedIn()) {
                return@withContext UploadResult(
                    success = false,
                    error = UploadError.NotAuthenticated
                )
            }

            val targetFolder = folderId ?: getTargetFolderId()
            if (targetFolder == null) {
                return@withContext UploadResult(
                    success = false,
                    error = UploadError.NoTargetFolder
                )
            }

            if (!audioFile.exists()) {
                return@withContext UploadResult(
                    success = false,
                    error = UploadError.FileError("Audio file does not exist: ${audioFile.path}")
                )
            }

            val driveService = authManager.getDriveService()

            // Upload audio file
            val audioFileMetadata = DriveFile().apply {
                name = audioFile.name
                parents = listOf(targetFolder)
            }
            val audioContent = FileContent(MIME_TYPE_AUDIO, audioFile)
            val audioResult = driveService.files()
                .create(audioFileMetadata, audioContent)
                .setFields("id, md5Checksum")
                .execute()

            // Upload metadata sidecar if present
            var metadataFileId: String? = null
            if (metadataFile != null && metadataFile.exists()) {
                val metadataFileMetadata = DriveFile().apply {
                    name = metadataFile.name
                    parents = listOf(targetFolder)
                }
                val metadataContent = FileContent(MIME_TYPE_JSON, metadataFile)
                val metadataResult = driveService.files()
                    .create(metadataFileMetadata, metadataContent)
                    .setFields("id")
                    .execute()
                metadataFileId = metadataResult.id
            }

            UploadResult(
                success = true,
                audioFileId = audioResult.id,
                metadataFileId = metadataFileId
            )
        } catch (e: IOException) {
            UploadResult(
                success = false,
                error = UploadError.NetworkError
            )
        } catch (e: Exception) {
            UploadResult(
                success = false,
                error = UploadError.ApiError(0, e.message ?: "Unknown error")
            )
        }
    }

    override suspend fun verifyUpload(fileId: String, expectedMd5: String): Boolean =
        withContext(Dispatchers.IO) {
            try {
                val driveService = authManager.getDriveService()
                val file = driveService.files()
                    .get(fileId)
                    .setFields("md5Checksum")
                    .execute()

                file.md5Checksum.equals(expectedMd5, ignoreCase = true)
            } catch (e: Exception) {
                false
            }
        }

    override suspend fun delete(fileId: String): Boolean = withContext(Dispatchers.IO) {
        try {
            val driveService = authManager.getDriveService()
            driveService.files().delete(fileId).execute()
            true
        } catch (e: Exception) {
            false
        }
    }

    override suspend fun listFolders(parentId: String?): List<CloudFolder> =
        withContext(Dispatchers.IO) {
            try {
                Log.d("GoogleDriveStorage", "listFolders called, parentId=$parentId")
                val driveService = authManager.getDriveService()
                Log.d("GoogleDriveStorage", "Got drive service")
                val query = buildString {
                    append("mimeType = '$MIME_TYPE_FOLDER' and trashed = false")
                    if (parentId != null) {
                        append(" and '$parentId' in parents")
                    } else {
                        append(" and 'root' in parents")
                    }
                }
                Log.d("GoogleDriveStorage", "Query: $query")

                val result = driveService.files()
                    .list()
                    .setQ(query)
                    .setFields("files(id, name, parents)")
                    .setOrderBy("name")
                    .execute()

                Log.d("GoogleDriveStorage", "Got ${result.files?.size ?: 0} folders")
                result.files.map { file ->
                    CloudFolder(
                        id = file.id,
                        name = file.name,
                        parentId = file.parents?.firstOrNull()
                    )
                }
            } catch (e: Exception) {
                Log.e("GoogleDriveStorage", "listFolders failed", e)
                emptyList()
            }
        }

    /**
     * Find or create a folder in Google Drive root.
     *
     * With the drive.file scope, we can only access folders created by this app.
     * This method searches for an existing folder with the given name, or creates it if not found.
     *
     * @param folderName The folder name
     * @return CloudFolder if successful, null otherwise
     */
    suspend fun findOrCreateFolder(folderName: String): CloudFolder? =
        withContext(Dispatchers.IO) {
            try {
                if (!authManager.isSignedIn()) {
                    Log.e("GoogleDriveStorage", "Not signed in")
                    return@withContext null
                }

                val driveService = authManager.getDriveService()

                // Search for existing folder with this name
                val searchQuery = "mimeType = '$MIME_TYPE_FOLDER' and name = '$folderName' and trashed = false"
                Log.d("GoogleDriveStorage", "Searching for folder: $searchQuery")

                val searchResult = driveService.files()
                    .list()
                    .setQ(searchQuery)
                    .setFields("files(id, name)")
                    .setSpaces("drive")
                    .execute()

                // If folder exists, return it
                if (searchResult.files.isNotEmpty()) {
                    val folder = searchResult.files.first()
                    Log.d("GoogleDriveStorage", "Found existing folder: ${folder.name} (${folder.id})")
                    return@withContext CloudFolder(
                        id = folder.id,
                        name = folder.name,
                        parentId = null
                    )
                }

                // Otherwise, create new folder
                Log.d("GoogleDriveStorage", "Creating new folder: $folderName")
                val folderMetadata = DriveFile().apply {
                    name = folderName
                    mimeType = MIME_TYPE_FOLDER
                }

                val createdFolder = driveService.files()
                    .create(folderMetadata)
                    .setFields("id, name")
                    .execute()

                Log.d("GoogleDriveStorage", "Created folder: ${createdFolder.name} (${createdFolder.id})")
                CloudFolder(
                    id = createdFolder.id,
                    name = createdFolder.name,
                    parentId = null
                )
            } catch (e: Exception) {
                Log.e("GoogleDriveStorage", "findOrCreateFolder failed", e)
                null
            }
        }
}
