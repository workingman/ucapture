package ca.dgbi.ucapture.service

import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Job
import kotlinx.coroutines.channels.Channel
import kotlinx.coroutines.delay
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.MutableSharedFlow
import kotlinx.coroutines.flow.SharedFlow
import kotlinx.coroutines.flow.asSharedFlow
import kotlinx.coroutines.flow.receiveAsFlow
import kotlinx.coroutines.isActive
import kotlinx.coroutines.launch
import java.io.File
import java.time.ZonedDateTime
import java.time.format.DateTimeFormatter
import javax.inject.Inject

/**
 * Manages automatic chunking of audio recordings.
 *
 * Splits long recordings into manageable chunks at configurable intervals.
 * Each chunk gets a sequential number suffix (e.g., -001, -002).
 */
class ChunkManager @Inject constructor() {

    data class ChunkInfo(
        val file: File,
        val chunkNumber: Int,
        val startTime: ZonedDateTime,
        val sessionId: String
    )

    data class CompletedChunk(
        val file: File,
        val chunkNumber: Int,
        val startTime: ZonedDateTime,
        val endTime: ZonedDateTime,
        val sessionId: String
    )

    companion object {
        const val DEFAULT_CHUNK_DURATION_MINUTES = 30L
        const val MIN_CHUNK_DURATION_MINUTES = 5L
        const val MAX_CHUNK_DURATION_MINUTES = 120L

        private val TIMESTAMP_FORMATTER = DateTimeFormatter.ofPattern("yyyyMMdd-HHmmss")
        private val TIMEZONE_FORMATTER = DateTimeFormatter.ofPattern("z")
    }

    private var chunkDurationMinutes: Long = DEFAULT_CHUNK_DURATION_MINUTES
    private var currentChunk: ChunkInfo? = null
    private var chunkTimerJob: Job? = null
    private var recordingsDir: File? = null

    private val _completedChunks = Channel<CompletedChunk>(Channel.UNLIMITED)
    val completedChunks: Flow<CompletedChunk> = _completedChunks.receiveAsFlow()

    private val _chunkRotationRequired = MutableSharedFlow<ChunkInfo>(extraBufferCapacity = 1)
    val chunkRotationRequired: SharedFlow<ChunkInfo> = _chunkRotationRequired.asSharedFlow()

    val currentChunkInfo: ChunkInfo?
        get() = currentChunk

    val currentChunkNumber: Int
        get() = currentChunk?.chunkNumber ?: 0

    fun configure(
        recordingsDir: File,
        chunkDurationMinutes: Long = DEFAULT_CHUNK_DURATION_MINUTES
    ) {
        this.recordingsDir = recordingsDir.apply { mkdirs() }
        this.chunkDurationMinutes = chunkDurationMinutes.coerceIn(
            MIN_CHUNK_DURATION_MINUTES,
            MAX_CHUNK_DURATION_MINUTES
        )
    }

    fun startNewSession(): ChunkInfo {
        val now = ZonedDateTime.now()
        val sessionId = TIMESTAMP_FORMATTER.format(now)
        return createChunk(sessionId, 1, now)
    }

    fun startChunkTimer(scope: CoroutineScope, onRotate: suspend (newChunk: ChunkInfo) -> Unit) {
        chunkTimerJob?.cancel()
        chunkTimerJob = scope.launch {
            while (isActive) {
                delay(chunkDurationMinutes * 60 * 1000)
                val newChunk = rotateChunk()
                if (newChunk != null) {
                    _chunkRotationRequired.emit(newChunk)
                    onRotate(newChunk)
                }
            }
        }
    }

    fun stopChunkTimer() {
        chunkTimerJob?.cancel()
        chunkTimerJob = null
    }

    fun completeCurrentChunk(): CompletedChunk? {
        val chunk = currentChunk ?: return null
        val now = ZonedDateTime.now()

        val finalFile = renameToEndTimestamp(chunk.file, now)

        val completed = CompletedChunk(
            file = finalFile,
            chunkNumber = chunk.chunkNumber,
            startTime = chunk.startTime,
            endTime = now,
            sessionId = chunk.sessionId
        )

        _completedChunks.trySend(completed)
        return completed
    }

    /**
     * Rename the chunk file from its temporary start-time name to a final name
     * based on the chunk's end time. The new name format is:
     *   ucap-YYYYMMDD-HHmmss-TZ.m4a
     *
     * On Android, renaming an open file is safe — the MediaRecorder's file
     * descriptor stays valid after the directory entry changes.
     */
    private fun renameToEndTimestamp(file: File, endTime: ZonedDateTime): File {
        val timezone = TIMEZONE_FORMATTER.format(endTime)
        val timestamp = TIMESTAMP_FORMATTER.format(endTime)
        val newName = "ucap-$timestamp-$timezone.m4a"
        val newFile = File(file.parentFile!!, newName)
        file.renameTo(newFile)
        return newFile
    }

    fun endSession(): CompletedChunk? {
        stopChunkTimer()
        val completed = completeCurrentChunk()
        currentChunk = null
        return completed
    }

    private fun rotateChunk(): ChunkInfo? {
        val current = currentChunk ?: return null

        // Complete current chunk
        completeCurrentChunk()

        // Start next chunk
        return createChunk(
            sessionId = current.sessionId,
            chunkNumber = current.chunkNumber + 1,
            startTime = ZonedDateTime.now()
        )
    }

    private fun createChunk(sessionId: String, chunkNumber: Int, startTime: ZonedDateTime): ChunkInfo {
        val dir = recordingsDir ?: throw IllegalStateException("ChunkManager not configured")
        val timezone = TIMEZONE_FORMATTER.format(startTime)
        val filename = "ucap-$sessionId-$timezone-%03d.m4a".format(chunkNumber)
        val file = File(dir, filename)

        val chunk = ChunkInfo(
            file = file,
            chunkNumber = chunkNumber,
            startTime = startTime,
            sessionId = sessionId
        )
        currentChunk = chunk
        return chunk
    }

    fun reset() {
        stopChunkTimer()
        currentChunk = null
    }
}
