package ca.dgbi.ucapture.service

import android.util.Log
import ca.dgbi.ucapture.data.local.entity.RecordingEntity
import ca.dgbi.ucapture.data.repository.RecordingRepository
import ca.dgbi.ucapture.util.FileManager
import java.io.File
import java.time.LocalDateTime
import java.time.format.DateTimeFormatter
import java.util.TimeZone
import javax.inject.Inject
import javax.inject.Singleton

/**
 * Recovers orphaned audio files that exist on disk but have no Room DB row.
 *
 * This can happen if the app is killed between writing audio to disk and
 * persisting the database row. Recovered files are re-entered into the
 * upload pipeline with PENDING status.
 *
 * Audio files are NEVER deleted — only recovered.
 */
@Singleton
class OrphanRecoveryManager @Inject constructor(
    private val fileManager: FileManager,
    private val recordingRepository: RecordingRepository
) {
    companion object {
        private const val TAG = "OrphanRecovery"

        private val TIMESTAMP_FORMATTER = DateTimeFormatter.ofPattern("yyyyMMdd-HHmmss")

        /**
         * Completed files: ucap-YYYYMMDD-HHmmss-TZ.m4a (no chunk number)
         * In-progress files: ucap-YYYYMMDD-HHmmss-TZ-NNN.m4a (has chunk number)
         *
         * Only completed (renamed) files are candidates for recovery.
         */
        private val COMPLETED_FILE_PATTERN =
            Regex("^ucap-(\\d{8}-\\d{6})-([A-Z]{2,5})\\.m4a$")
    }

    /**
     * Scan for orphaned audio files and insert them into the database.
     *
     * @return list of database IDs for recovered recordings (caller can schedule uploads)
     */
    suspend fun recoverOrphans(): List<Long> {
        val allFiles = fileManager.listRecordingFiles()
        val recoveredIds = mutableListOf<Long>()

        for (file in allFiles) {
            if (isOrphan(file)) {
                val id = recoverFile(file)
                if (id != null) {
                    recoveredIds.add(id)
                    Log.i(TAG, "Recovered orphan: ${file.name} -> id=$id")
                }
            }
        }

        if (recoveredIds.isNotEmpty()) {
            Log.i(TAG, "Recovered ${recoveredIds.size} orphaned recording(s)")
        }

        return recoveredIds
    }

    private suspend fun isOrphan(file: File): Boolean {
        // Only consider completed (renamed) files — skip in-progress chunks
        if (!COMPLETED_FILE_PATTERN.matches(file.name)) {
            return false
        }

        // Check if a DB row already exists for this file
        return recordingRepository.getByFilePath(file.absolutePath) == null
    }

    private suspend fun recoverFile(file: File): Long? {
        val match = COMPLETED_FILE_PATTERN.matchEntire(file.name) ?: return null
        val timestampStr = match.groupValues[1]
        val timezoneAbbr = match.groupValues[2]

        val epochMilli = try {
            val localDateTime = LocalDateTime.parse(timestampStr, TIMESTAMP_FORMATTER)
            val zoneId = TimeZone.getTimeZone(timezoneAbbr).toZoneId()
            localDateTime.atZone(zoneId).toInstant().toEpochMilli()
        } catch (e: Exception) {
            Log.w(TAG, "Failed to parse timestamp from ${file.name}, using file modified time", e)
            file.lastModified()
        }

        val entity = RecordingEntity(
            sessionId = "orphan-$timestampStr",
            chunkNumber = 1,
            filePath = file.absolutePath,
            startTimeEpochMilli = epochMilli,
            endTimeEpochMilli = epochMilli,
            timezoneId = timezoneAbbr,
            durationSeconds = 0,
            fileSizeBytes = file.length()
        )

        return try {
            recordingRepository.insertRecording(entity)
        } catch (e: Exception) {
            Log.e(TAG, "Failed to recover orphan ${file.name}", e)
            null
        }
    }
}
