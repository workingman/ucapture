package ca.dgbi.ucapture.service.metadata

import android.Manifest
import android.annotation.SuppressLint
import android.content.Context
import android.content.pm.PackageManager
import android.os.Looper
import androidx.core.content.ContextCompat
import ca.dgbi.ucapture.service.ChunkManager
import com.google.android.gms.location.FusedLocationProviderClient
import com.google.android.gms.location.LocationCallback
import com.google.android.gms.location.LocationRequest
import com.google.android.gms.location.LocationResult
import com.google.android.gms.location.LocationServices
import com.google.android.gms.location.Priority
import kotlinx.coroutines.channels.awaitClose
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.MutableSharedFlow
import kotlinx.coroutines.flow.callbackFlow
import java.time.Instant
import java.util.concurrent.CopyOnWriteArrayList
import javax.inject.Inject
import javax.inject.Singleton

/**
 * Collects location metadata during audio recording using Fused Location Provider.
 *
 * Features:
 * - Periodic location sampling at configurable intervals (default: 1 minute)
 * - PRIORITY_BALANCED_POWER_ACCURACY for battery efficiency
 * - Graceful handling of missing permissions (continues without location)
 * - Thread-safe sample storage
 *
 * @property context Application context for location services and permission checks
 * @property samplingIntervalMs Location sampling interval in milliseconds (default: 60000ms = 1 min)
 */
@Singleton
class LocationMetadataCollector @Inject constructor(
    private val context: Context,
    private val samplingIntervalMs: Long = DEFAULT_SAMPLING_INTERVAL_MS
) : MetadataCollector<LocationSample> {

    companion object {
        const val COLLECTOR_ID = "location"
        const val DEFAULT_SAMPLING_INTERVAL_MS = 60_000L // 1 minute
        const val MIN_SAMPLING_INTERVAL_MS = 10_000L // 10 seconds minimum
        const val FASTEST_INTERVAL_MS = 30_000L // Fastest update rate
    }

    override val collectorId: String = COLLECTOR_ID

    private val fusedLocationClient: FusedLocationProviderClient by lazy {
        LocationServices.getFusedLocationProviderClient(context)
    }

    private val _metadataFlow = MutableSharedFlow<LocationSample>(replay = 1)
    override val metadataFlow: Flow<LocationSample> = _metadataFlow

    // Thread-safe list to store collected samples
    private val collectedSamples = CopyOnWriteArrayList<LocationSample>()

    private var locationCallback: LocationCallback? = null
    private var isCollecting = false

    /**
     * Check if location collection is available.
     *
     * Returns true if either fine or coarse location permission is granted.
     * Recording can proceed without location if permissions are denied.
     */
    override suspend fun isAvailable(): Boolean {
        return hasLocationPermission()
    }

    private fun hasLocationPermission(): Boolean {
        val fineLocation = ContextCompat.checkSelfPermission(
            context,
            Manifest.permission.ACCESS_FINE_LOCATION
        ) == PackageManager.PERMISSION_GRANTED

        val coarseLocation = ContextCompat.checkSelfPermission(
            context,
            Manifest.permission.ACCESS_COARSE_LOCATION
        ) == PackageManager.PERMISSION_GRANTED

        return fineLocation || coarseLocation
    }

    /**
     * Start collecting location samples.
     *
     * Uses PRIORITY_BALANCED_POWER_ACCURACY for reasonable accuracy
     * while preserving battery life during long recording sessions.
     */
    @SuppressLint("MissingPermission")
    override suspend fun startCollecting() {
        if (isCollecting) return
        if (!hasLocationPermission()) return

        collectedSamples.clear()

        val locationRequest = LocationRequest.Builder(
            Priority.PRIORITY_BALANCED_POWER_ACCURACY,
            samplingIntervalMs
        ).apply {
            setMinUpdateIntervalMillis(FASTEST_INTERVAL_MS)
            setWaitForAccurateLocation(false)
        }.build()

        locationCallback = object : LocationCallback() {
            override fun onLocationResult(result: LocationResult) {
                result.lastLocation?.let { location ->
                    val sample = LocationSample(
                        latitude = location.latitude,
                        longitude = location.longitude,
                        altitude = if (location.hasAltitude()) location.altitude else null,
                        accuracy = location.accuracy,
                        speed = if (location.hasSpeed()) location.speed else null,
                        bearing = if (location.hasBearing()) location.bearing else null,
                        timestamp = Instant.ofEpochMilli(location.time),
                        provider = location.provider ?: "fused"
                    )
                    collectedSamples.add(sample)
                    _metadataFlow.tryEmit(sample)
                }
            }
        }

        fusedLocationClient.requestLocationUpdates(
            locationRequest,
            locationCallback!!,
            Looper.getMainLooper()
        )

        isCollecting = true
    }

    /**
     * Stop collecting location samples.
     */
    override suspend fun stopCollecting() {
        if (!isCollecting) return

        locationCallback?.let {
            fusedLocationClient.removeLocationUpdates(it)
        }
        locationCallback = null
        isCollecting = false
    }

    /**
     * Get location samples collected during a specific chunk's time range.
     *
     * @param chunk The completed chunk to get metadata for
     * @return List of LocationSample objects within the chunk's time range
     */
    override suspend fun getMetadataForChunk(chunk: ChunkManager.CompletedChunk): List<LocationSample> {
        val chunkStartMs = chunk.startTime.toInstant().toEpochMilli()
        val chunkEndMs = chunk.endTime.toInstant().toEpochMilli()

        return collectedSamples.filter { sample ->
            val sampleTime = sample.timestamp.toEpochMilli()
            sampleTime >= chunkStartMs && sampleTime <= chunkEndMs
        }
    }

    /**
     * Get the most recent location sample, if any.
     */
    fun getLastLocation(): LocationSample? = collectedSamples.lastOrNull()

    /**
     * Get all collected samples (for debugging/testing).
     */
    fun getAllSamples(): List<LocationSample> = collectedSamples.toList()

    /**
     * Clear all collected samples.
     */
    fun clearSamples() {
        collectedSamples.clear()
    }

    /**
     * Check if currently collecting location updates.
     */
    fun isCurrentlyCollecting(): Boolean = isCollecting
}
