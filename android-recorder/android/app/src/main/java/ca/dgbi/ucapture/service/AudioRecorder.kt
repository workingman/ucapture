package ca.dgbi.ucapture.service

import android.content.Context
import android.media.MediaRecorder
import android.os.Build
import java.io.File
import javax.inject.Inject

/**
 * Handles audio recording using MediaRecorder API.
 *
 * Note: Android doesn't natively support MP3 encoding. We use AAC codec
 * in MPEG4 container (.m4a) which provides better quality at equivalent bitrates
 * and is universally supported.
 */
open class AudioRecorder @Inject constructor(
    private val context: Context
) {
    enum class Quality(val bitrate: Int) {
        LOW(64_000),      // 64 kbps
        MEDIUM(128_000),  // 128 kbps
        HIGH(256_000)     // 256 kbps
    }

    private var mediaRecorder: MediaRecorder? = null
    private var currentFile: File? = null
    private var isPaused: Boolean = false

    val isRecording: Boolean
        get() = mediaRecorder != null && !isPaused

    val isPausedState: Boolean
        get() = isPaused

    val outputFile: File?
        get() = currentFile

    fun start(outputFile: File, quality: Quality = Quality.MEDIUM): Boolean {
        if (mediaRecorder != null) {
            return false
        }

        currentFile = outputFile

        try {
            mediaRecorder = createMediaRecorderInstance().apply {
                setAudioSource(MediaRecorder.AudioSource.MIC)
                setOutputFormat(MediaRecorder.OutputFormat.MPEG_4)
                setAudioEncoder(MediaRecorder.AudioEncoder.AAC)
                setAudioEncodingBitRate(quality.bitrate)
                setAudioSamplingRate(44100)
                setAudioChannels(1) // Mono for voice recording
                setOutputFile(outputFile.absolutePath)

                prepare()
                start()
            }
            isPaused = false
            return true
        } catch (e: Exception) {
            release()
            throw AudioRecorderException("Failed to start recording: ${e.message}", e)
        }
    }

    fun pause(): Boolean {
        val recorder = mediaRecorder ?: return false
        if (isPaused) return false

        try {
            recorder.pause()
            isPaused = true
            return true
        } catch (e: Exception) {
            throw AudioRecorderException("Failed to pause recording: ${e.message}", e)
        }
    }

    fun resume(): Boolean {
        val recorder = mediaRecorder ?: return false
        if (!isPaused) return false

        try {
            recorder.resume()
            isPaused = false
            return true
        } catch (e: Exception) {
            throw AudioRecorderException("Failed to resume recording: ${e.message}", e)
        }
    }

    fun stop(): File? {
        val recorder = mediaRecorder ?: return null
        val file = currentFile

        try {
            if (isPaused) {
                recorder.resume() // Must resume before stopping
            }
            recorder.stop()
        } catch (e: Exception) {
            // Recording may have been too short or other issue
            // Still try to release resources
        } finally {
            release()
        }

        return file
    }

    fun release() {
        try {
            mediaRecorder?.release()
        } catch (e: Exception) {
            // Ignore release errors
        }
        mediaRecorder = null
        currentFile = null
        isPaused = false
    }

    @Suppress("DEPRECATION")
    protected open fun createMediaRecorderInstance(): MediaRecorder {
        return if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.S) {
            MediaRecorder(context)
        } else {
            MediaRecorder()
        }
    }

    class AudioRecorderException(message: String, cause: Throwable? = null) : Exception(message, cause)
}
