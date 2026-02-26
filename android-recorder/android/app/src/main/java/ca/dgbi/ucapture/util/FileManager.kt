package ca.dgbi.ucapture.util

import android.content.Context
import android.os.StatFs
import ca.dgbi.ucapture.data.model.RecordingMetadata
import dagger.hilt.android.qualifiers.ApplicationContext
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import java.io.File
import javax.inject.Inject
import javax.inject.Singleton

/**
 * Manages file system operations for recordings and metadata.
 */
@Singleton
class FileManager @Inject constructor(
    @ApplicationContext private val context: Context
) {
    companion object {
        private const val RECORDINGS_DIR = "recordings"
        private const val METADATA_DIR = "metadata"

        const val LOW_STORAGE_THRESHOLD_MB = 100L
        const val CRITICAL_STORAGE_THRESHOLD_MB = 50L
    }

    val recordingsDirectory: File
        get() = File(context.filesDir, RECORDINGS_DIR).apply { mkdirs() }

    val metadataDirectory: File
        get() = File(context.filesDir, METADATA_DIR).apply { mkdirs() }

    /**
     * Get available storage space on internal storage.
     *
     * @return Available bytes
     */
    fun getAvailableStorageBytes(): Long {
        val stat = StatFs(context.filesDir.absolutePath)
        return stat.availableBytes
    }

    /**
     * Get total internal storage space.
     *
     * @return Total bytes
     */
    fun getTotalStorageBytes(): Long {
        val stat = StatFs(context.filesDir.absolutePath)
        return stat.totalBytes
    }

    /**
     * Calculate storage used by this app's recordings.
     *
     * @return Used bytes
     */
    fun getAppStorageUsedBytes(): Long {
        return recordingsDirectory.walkTopDown()
            .filter { it.isFile }
            .sumOf { it.length() }
    }

    /**
     * Check current storage status.
     */
    fun getStorageStatus(): StorageStatus {
        val availableMb = getAvailableStorageBytes() / (1024 * 1024)
        return when {
            availableMb < CRITICAL_STORAGE_THRESHOLD_MB -> StorageStatus.CRITICAL
            availableMb < LOW_STORAGE_THRESHOLD_MB -> StorageStatus.LOW
            else -> StorageStatus.OK
        }
    }

    /**
     * Delete a recording file and its associated metadata sidecar.
     *
     * @return true if all files were deleted successfully
     */
    fun deleteRecordingFiles(filePath: String): Boolean {
        val audioFile = File(filePath)
        val metadataFile = getMetadataSidecarFile(filePath)

        val audioDeleted = if (audioFile.exists()) audioFile.delete() else true
        val metadataDeleted = if (metadataFile.exists()) metadataFile.delete() else true

        return audioDeleted && metadataDeleted
    }

    /**
     * Get the metadata sidecar file path for an audio file.
     */
    fun getMetadataSidecarFile(audioFilePath: String): File {
        val audioFile = File(audioFilePath)
        val baseName = audioFile.nameWithoutExtension
        return File(metadataDirectory, "$baseName.json")
    }

    /**
     * Write metadata JSON sidecar file.
     *
     * @return The created sidecar file
     */
    suspend fun writeMetadataSidecar(audioFilePath: String, metadata: RecordingMetadata): File =
        withContext(Dispatchers.IO) {
            val sidecarFile = getMetadataSidecarFile(audioFilePath)
            sidecarFile.writeText(metadata.toJson())
            sidecarFile
        }

    /**
     * Check whether a metadata sidecar exists for the given audio file path.
     */
    fun hasMetadataSidecar(audioFilePath: String): Boolean =
        getMetadataSidecarFile(audioFilePath).exists()

    /**
     * List all recording files sorted by modification time (newest first).
     */
    fun listRecordingFiles(): List<File> {
        return recordingsDirectory.listFiles()
            ?.filter { it.isFile && it.extension == "m4a" }
            ?.sortedByDescending { it.lastModified() }
            ?: emptyList()
    }

    /**
     * Check if a file exists.
     */
    fun fileExists(filePath: String): Boolean = File(filePath).exists()

    /**
     * Get file size in bytes.
     *
     * @return File size, or 0 if file doesn't exist
     */
    fun getFileSize(filePath: String): Long {
        val file = File(filePath)
        return if (file.exists()) file.length() else 0L
    }

    enum class StorageStatus {
        OK,
        LOW,
        CRITICAL
    }
}
