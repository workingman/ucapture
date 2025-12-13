package ca.dgbi.ucapture.service

import android.app.Notification
import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.PendingIntent
import android.app.Service
import android.content.Context
import android.content.Intent
import android.os.Binder
import android.os.IBinder
import android.os.PowerManager
import androidx.core.app.NotificationCompat
import ca.dgbi.ucapture.MainActivity
import ca.dgbi.ucapture.R
import ca.dgbi.ucapture.service.metadata.MetadataCollectorManager
import dagger.hilt.android.AndroidEntryPoint
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.Job
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.cancel
import kotlinx.coroutines.delay
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.SharedFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.isActive
import kotlinx.coroutines.launch
import java.io.File
import javax.inject.Inject

@AndroidEntryPoint
class RecordingService : Service() {

    enum class State {
        IDLE,
        RECORDING,
        PAUSED,
        STOPPED
    }

    companion object {
        private const val NOTIFICATION_CHANNEL_ID = "ucapture_recording"
        private const val NOTIFICATION_ID = 1
        private const val WAKE_LOCK_TAG = "ucapture:recording"

        const val ACTION_START = "ca.dgbi.ucapture.action.START"
        const val ACTION_PAUSE = "ca.dgbi.ucapture.action.PAUSE"
        const val ACTION_RESUME = "ca.dgbi.ucapture.action.RESUME"
        const val ACTION_STOP = "ca.dgbi.ucapture.action.STOP"

        const val EXTRA_QUALITY = "quality"
        const val EXTRA_CHUNK_DURATION_MINUTES = "chunk_duration"
    }

    @Inject
    lateinit var audioRecorder: AudioRecorder

    @Inject
    lateinit var chunkManager: ChunkManager

    @Inject
    lateinit var metadataCollectorManager: MetadataCollectorManager

    private var wakeLock: PowerManager.WakeLock? = null
    private val binder = RecordingBinder()
    private val serviceScope = CoroutineScope(SupervisorJob() + Dispatchers.Main)
    private var durationJob: Job? = null
    private var currentQuality: AudioRecorder.Quality = AudioRecorder.Quality.MEDIUM

    private val _state = MutableStateFlow(State.IDLE)
    val state: StateFlow<State> = _state.asStateFlow()

    private val _durationSeconds = MutableStateFlow(0L)
    val durationSeconds: StateFlow<Long> = _durationSeconds.asStateFlow()

    private val _currentFile = MutableStateFlow<File?>(null)
    val currentFile: StateFlow<File?> = _currentFile.asStateFlow()

    private val _currentChunkNumber = MutableStateFlow(0)
    val currentChunkNumber: StateFlow<Int> = _currentChunkNumber.asStateFlow()

    val completedChunks: SharedFlow<ChunkManager.CompletedChunk>
        get() = chunkManager.completedChunks

    inner class RecordingBinder : Binder() {
        fun getService(): RecordingService = this@RecordingService
    }

    override fun onCreate() {
        super.onCreate()
        createNotificationChannel()

        val recordingsDir = File(filesDir, "recordings")
        chunkManager.configure(recordingsDir)
    }

    override fun onStartCommand(intent: Intent?, flags: Int, startId: Int): Int {
        when (intent?.action) {
            ACTION_START -> {
                val qualityOrdinal = intent.getIntExtra(EXTRA_QUALITY, AudioRecorder.Quality.MEDIUM.ordinal)
                val quality = AudioRecorder.Quality.entries.getOrElse(qualityOrdinal) { AudioRecorder.Quality.MEDIUM }
                val chunkDuration = intent.getLongExtra(
                    EXTRA_CHUNK_DURATION_MINUTES,
                    ChunkManager.DEFAULT_CHUNK_DURATION_MINUTES
                )
                startRecording(quality, chunkDuration)
            }
            ACTION_PAUSE -> pauseRecording()
            ACTION_RESUME -> resumeRecording()
            ACTION_STOP -> stopRecording()
        }
        return START_STICKY
    }

    override fun onBind(intent: Intent?): IBinder {
        return binder
    }

    override fun onDestroy() {
        super.onDestroy()
        if (_state.value == State.RECORDING || _state.value == State.PAUSED) {
            stopRecording()
        }
        releaseWakeLock()
        serviceScope.cancel()
    }

    fun startRecording(
        quality: AudioRecorder.Quality = AudioRecorder.Quality.MEDIUM,
        chunkDurationMinutes: Long = ChunkManager.DEFAULT_CHUNK_DURATION_MINUTES
    ) {
        if (_state.value != State.IDLE && _state.value != State.STOPPED) {
            return
        }

        currentQuality = quality

        // Configure and start chunk manager
        val recordingsDir = File(filesDir, "recordings")
        chunkManager.configure(recordingsDir, chunkDurationMinutes)
        val chunk = chunkManager.startNewSession()

        _currentFile.value = chunk.file
        _currentChunkNumber.value = chunk.chunkNumber

        try {
            audioRecorder.start(chunk.file, quality)
            _state.value = State.RECORDING
            _durationSeconds.value = 0
            startForeground(NOTIFICATION_ID, createNotification())
            acquireWakeLock()
            startDurationTimer()

            // Start chunk rotation timer
            chunkManager.startChunkTimer(serviceScope) { newChunk ->
                rotateToNewChunk(newChunk)
            }

            // Start metadata collectors
            serviceScope.launch {
                metadataCollectorManager.startAll()
            }
        } catch (e: AudioRecorder.AudioRecorderException) {
            _state.value = State.IDLE
            _currentFile.value = null
            chunkManager.reset()
            // TODO: Notify UI of error
        }
    }

    fun pauseRecording() {
        if (_state.value != State.RECORDING) {
            return
        }

        try {
            audioRecorder.pause()
            _state.value = State.PAUSED
            stopDurationTimer()
            chunkManager.stopChunkTimer()
            updateNotification()
        } catch (e: AudioRecorder.AudioRecorderException) {
            // TODO: Notify UI of error
        }
    }

    fun resumeRecording() {
        if (_state.value != State.PAUSED) {
            return
        }

        try {
            audioRecorder.resume()
            _state.value = State.RECORDING
            startDurationTimer()

            // Resume chunk timer
            chunkManager.startChunkTimer(serviceScope) { newChunk ->
                rotateToNewChunk(newChunk)
            }
            updateNotification()
        } catch (e: AudioRecorder.AudioRecorderException) {
            // TODO: Notify UI of error
        }
    }

    fun stopRecording(): File? {
        if (_state.value == State.IDLE || _state.value == State.STOPPED) {
            return null
        }

        stopDurationTimer()
        releaseWakeLock()

        // Stop metadata collectors
        serviceScope.launch {
            metadataCollectorManager.stopAll()
        }

        val file = audioRecorder.stop()
        chunkManager.endSession()
        _state.value = State.STOPPED

        stopForeground(STOP_FOREGROUND_REMOVE)
        stopSelf()

        return file
    }

    private suspend fun rotateToNewChunk(newChunk: ChunkManager.ChunkInfo) {
        // Stop current recording (completes the chunk)
        audioRecorder.stop()

        // Start new recording with new chunk file
        try {
            audioRecorder.start(newChunk.file, currentQuality)
            _currentFile.value = newChunk.file
            _currentChunkNumber.value = newChunk.chunkNumber
            updateNotification()
        } catch (e: AudioRecorder.AudioRecorderException) {
            // Chunk rotation failed - stop the session
            stopRecording()
        }
    }

    private fun startDurationTimer() {
        durationJob?.cancel()
        durationJob = serviceScope.launch {
            while (isActive) {
                delay(1000)
                _durationSeconds.value++
                updateNotification()
            }
        }
    }

    private fun stopDurationTimer() {
        durationJob?.cancel()
        durationJob = null
    }

    private fun createNotificationChannel() {
        val channel = NotificationChannel(
            NOTIFICATION_CHANNEL_ID,
            "Recording",
            NotificationManager.IMPORTANCE_LOW
        ).apply {
            description = "Shows when audio recording is active"
            setShowBadge(false)
        }

        val notificationManager = getSystemService(Context.NOTIFICATION_SERVICE) as NotificationManager
        notificationManager.createNotificationChannel(channel)
    }

    private fun createNotification(): Notification {
        val contentIntent = PendingIntent.getActivity(
            this,
            0,
            Intent(this, MainActivity::class.java),
            PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE
        )

        val stopIntent = PendingIntent.getService(
            this,
            0,
            Intent(this, RecordingService::class.java).apply { action = ACTION_STOP },
            PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE
        )

        val pauseResumeIntent = PendingIntent.getService(
            this,
            1,
            Intent(this, RecordingService::class.java).apply {
                action = if (_state.value == State.PAUSED) ACTION_RESUME else ACTION_PAUSE
            },
            PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE
        )

        val duration = _durationSeconds.value
        val durationText = String.format("%02d:%02d", duration / 60, duration % 60)
        val chunkText = if (_currentChunkNumber.value > 1) " (chunk ${_currentChunkNumber.value})" else ""

        val statusText = when (_state.value) {
            State.RECORDING -> "Recording $durationText$chunkText"
            State.PAUSED -> "Paused $durationText$chunkText"
            else -> "Ready"
        }

        val pauseResumeText = if (_state.value == State.PAUSED) "Resume" else "Pause"

        return NotificationCompat.Builder(this, NOTIFICATION_CHANNEL_ID)
            .setContentTitle("uCapture")
            .setContentText(statusText)
            .setSmallIcon(R.drawable.ic_launcher_foreground)
            .setOngoing(true)
            .setContentIntent(contentIntent)
            .addAction(0, pauseResumeText, pauseResumeIntent)
            .addAction(0, "Stop", stopIntent)
            .build()
    }

    private fun updateNotification() {
        val notificationManager = getSystemService(Context.NOTIFICATION_SERVICE) as NotificationManager
        notificationManager.notify(NOTIFICATION_ID, createNotification())
    }

    @Suppress("DEPRECATION")
    private fun acquireWakeLock() {
        if (wakeLock == null) {
            val powerManager = getSystemService(Context.POWER_SERVICE) as PowerManager
            wakeLock = powerManager.newWakeLock(
                PowerManager.PARTIAL_WAKE_LOCK,
                WAKE_LOCK_TAG
            )
        }
        wakeLock?.acquire()
    }

    private fun releaseWakeLock() {
        wakeLock?.let {
            if (it.isHeld) {
                it.release()
            }
        }
        wakeLock = null
    }
}
