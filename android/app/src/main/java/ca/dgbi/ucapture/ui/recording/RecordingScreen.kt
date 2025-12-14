package ca.dgbi.ucapture.ui.recording

import android.Manifest
import android.content.ComponentName
import android.content.Context
import android.content.Intent
import android.content.ServiceConnection
import android.os.IBinder
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.animation.core.LinearEasing
import androidx.compose.animation.core.RepeatMode
import androidx.compose.animation.core.animateFloat
import androidx.compose.animation.core.infiniteRepeatable
import androidx.compose.animation.core.rememberInfiniteTransition
import androidx.compose.animation.core.tween
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Check
import androidx.compose.material.icons.filled.PlayArrow
import androidx.compose.material3.Badge
import androidx.compose.material3.BadgedBox
import androidx.compose.material3.FloatingActionButton
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.DisposableEffect
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.scale
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.hilt.navigation.compose.hiltViewModel
import ca.dgbi.ucapture.service.RecordingService

/**
 * Recording screen with service binding and audio permission handling.
 *
 * Displays recording controls, duration timer, and upload queue status.
 */
@Composable
fun RecordingScreen(
    viewModel: RecordingViewModel = hiltViewModel()
) {
    val context = LocalContext.current
    val uiState by viewModel.uiState.collectAsState()
    val pendingUploadCount by viewModel.pendingUploadCount.collectAsState()

    // Service binding
    var service: RecordingService? by remember { mutableStateOf(null) }
    val connection = remember {
        object : ServiceConnection {
            override fun onServiceConnected(name: ComponentName?, binder: IBinder?) {
                service = (binder as? RecordingService.RecordingBinder)?.getService()
            }

            override fun onServiceDisconnected(name: ComponentName?) {
                service = null
            }
        }
    }

    // Bind to service
    DisposableEffect(Unit) {
        val intent = Intent(context, RecordingService::class.java)
        context.bindService(intent, connection, Context.BIND_AUTO_CREATE)

        onDispose {
            context.unbindService(connection)
        }
    }

    // Update ViewModel from service state
    LaunchedEffect(service, uiState) {
        viewModel.updateFromService(service)
    }

    // Subscribe to service state changes
    val serviceState = service?.state?.collectAsState()
    val serviceDuration = service?.durationSeconds?.collectAsState()
    LaunchedEffect(serviceState?.value, serviceDuration?.value) {
        viewModel.updateFromService(service)
    }

    // Permission launcher
    var hasPermission by remember { mutableStateOf(false) }
    val permissionLauncher = rememberLauncherForActivityResult(
        contract = ActivityResultContracts.RequestPermission()
    ) { isGranted ->
        hasPermission = isGranted
        if (isGranted) {
            service?.startRecording()
        }
    }

    RecordingScreenContent(
        isRecording = uiState.isRecording,
        isPaused = uiState.isPaused,
        durationText = viewModel.formatDuration(uiState.recordingDurationSeconds),
        pendingUploadCount = pendingUploadCount,
        onStartRecording = {
            if (hasPermission) {
                service?.startRecording()
            } else {
                permissionLauncher.launch(Manifest.permission.RECORD_AUDIO)
            }
        },
        onPauseRecording = {
            service?.pauseRecording()
        },
        onResumeRecording = {
            service?.resumeRecording()
        },
        onStopRecording = {
            service?.stopRecording()
        }
    )
}

/**
 * Content composable for the Recording screen.
 */
@Composable
private fun RecordingScreenContent(
    isRecording: Boolean,
    isPaused: Boolean,
    durationText: String,
    pendingUploadCount: Int,
    onStartRecording: () -> Unit,
    onPauseRecording: () -> Unit,
    onResumeRecording: () -> Unit,
    onStopRecording: () -> Unit
) {
    Box(
        modifier = Modifier.fillMaxSize(),
        contentAlignment = Alignment.Center
    ) {
        Column(
            horizontalAlignment = Alignment.CenterHorizontally,
            verticalArrangement = Arrangement.Center
        ) {
            // Upload queue indicator
            if (pendingUploadCount > 0) {
                UploadQueueIndicator(count = pendingUploadCount)
                Spacer(modifier = Modifier.height(32.dp))
            }

            // Duration display
            Text(
                text = durationText,
                style = MaterialTheme.typography.displayLarge,
                fontWeight = FontWeight.Bold,
                color = if (isRecording && !isPaused) {
                    MaterialTheme.colorScheme.error
                } else {
                    MaterialTheme.colorScheme.onBackground
                }
            )

            Spacer(modifier = Modifier.height(48.dp))

            // Record button
            if (!isRecording && !isPaused) {
                RecordButton(
                    isRecording = false,
                    onClick = onStartRecording
                )
            } else {
                RecordButton(
                    isRecording = isRecording && !isPaused,
                    onClick = { }
                )
            }

            // Control buttons (when recording)
            if (isRecording || isPaused) {
                Spacer(modifier = Modifier.height(32.dp))

                Row(
                    horizontalArrangement = Arrangement.spacedBy(16.dp)
                ) {
                    // Pause/Resume button
                    FloatingActionButton(
                        onClick = if (isPaused) onResumeRecording else onPauseRecording,
                        containerColor = MaterialTheme.colorScheme.secondary
                    ) {
                        if (isPaused) {
                            Icon(
                                imageVector = Icons.Filled.PlayArrow,
                                contentDescription = "Resume"
                            )
                        } else {
                            Text(
                                text = "II",
                                style = MaterialTheme.typography.headlineSmall,
                                fontWeight = FontWeight.Bold
                            )
                        }
                    }

                    // Stop button
                    FloatingActionButton(
                        onClick = onStopRecording,
                        containerColor = MaterialTheme.colorScheme.error
                    ) {
                        Box(
                            modifier = Modifier
                                .size(20.dp)
                                .background(
                                    color = MaterialTheme.colorScheme.onError,
                                    shape = androidx.compose.foundation.shape.RoundedCornerShape(4.dp)
                                )
                        )
                    }
                }
            }
        }
    }
}

/**
 * Large circular record button with pulsing animation when recording.
 */
@Composable
private fun RecordButton(
    isRecording: Boolean,
    onClick: () -> Unit
) {
    // Pulsing animation
    val infiniteTransition = rememberInfiniteTransition(label = "pulse")
    val scale by infiniteTransition.animateFloat(
        initialValue = 1f,
        targetValue = 1.15f,
        animationSpec = infiniteRepeatable(
            animation = tween(800, easing = LinearEasing),
            repeatMode = RepeatMode.Reverse
        ),
        label = "scale"
    )

    Box(
        contentAlignment = Alignment.Center,
        modifier = Modifier
            .size(120.dp)
            .scale(if (isRecording) scale else 1f)
    ) {
        IconButton(
            onClick = onClick,
            modifier = Modifier
                .size(120.dp)
                .background(
                    color = Color.Red,
                    shape = CircleShape
                )
                .border(
                    width = 4.dp,
                    color = Color.Red.copy(alpha = 0.3f),
                    shape = CircleShape
                )
        ) {
            // Empty content - just a red circle
        }
    }
}

/**
 * Upload queue indicator showing pending upload count.
 */
@Composable
private fun UploadQueueIndicator(count: Int) {
    BadgedBox(
        badge = {
            Badge {
                Text(text = count.toString())
            }
        }
    ) {
        Row(
            verticalAlignment = Alignment.CenterVertically,
            horizontalArrangement = Arrangement.spacedBy(8.dp),
            modifier = Modifier.padding(8.dp)
        ) {
            Icon(
                imageVector = Icons.Filled.Check,
                contentDescription = "Uploads pending",
                tint = MaterialTheme.colorScheme.primary
            )
            Text(
                text = "Pending uploads",
                style = MaterialTheme.typography.bodyMedium,
                color = MaterialTheme.colorScheme.onBackground
            )
        }
    }
}
