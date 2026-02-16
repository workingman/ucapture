package ca.dgbi.ucapture.data.remote

import java.io.File

/**
 * Interface for cloud storage providers.
 *
 * Abstracts cloud storage operations to support multiple providers
 * (Google Drive now, potentially others in the future).
 */
interface CloudStorageProvider {

    /**
     * Provider identifier for logging and preferences.
     */
    val providerId: String

    /**
     * Check if the user is authenticated with this provider.
     */
    suspend fun isAuthenticated(): Boolean

    /**
     * Get the target folder ID for uploads.
     *
     * @return Folder ID or null if not configured
     */
    suspend fun getTargetFolderId(): String?

    /**
     * Set the target folder for uploads.
     *
     * @param folderId The folder ID to upload to
     */
    suspend fun setTargetFolderId(folderId: String)

    /**
     * Upload a file with optional metadata sidecar.
     *
     * @param audioFile The audio file to upload
     * @param metadataFile Optional JSON metadata sidecar file
     * @param folderId Target folder ID (uses default if null)
     * @return Upload result with file IDs
     */
    suspend fun upload(
        audioFile: File,
        metadataFile: File?,
        folderId: String? = null
    ): UploadResult

    /**
     * Verify an uploaded file's integrity using MD5 hash.
     *
     * @param fileId The cloud file ID
     * @param expectedMd5 Expected MD5 hash
     * @return true if hash matches
     */
    suspend fun verifyUpload(fileId: String, expectedMd5: String): Boolean

    /**
     * Delete a file from cloud storage.
     *
     * @param fileId The cloud file ID
     * @return true if deleted successfully
     */
    suspend fun delete(fileId: String): Boolean

    /**
     * List folders for folder selection UI.
     *
     * @param parentId Parent folder ID (null for root)
     * @return List of folders
     */
    suspend fun listFolders(parentId: String? = null): List<CloudFolder>
}

/**
 * Result of an upload operation.
 */
data class UploadResult(
    val success: Boolean,
    val audioFileId: String? = null,
    val metadataFileId: String? = null,
    val error: UploadError? = null
)

/**
 * Upload error types.
 */
sealed class UploadError {
    data object NotAuthenticated : UploadError()
    data object NoTargetFolder : UploadError()
    data object NetworkError : UploadError()
    data object QuotaExceeded : UploadError()
    data class ApiError(val code: Int, val message: String) : UploadError()
    data class FileError(val message: String) : UploadError()
}

/**
 * Represents a folder in cloud storage.
 */
data class CloudFolder(
    val id: String,
    val name: String,
    val parentId: String?
)
