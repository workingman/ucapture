package ca.dgbi.ucapture.service.metadata

import java.time.Instant

/**
 * Represents a single GPS location sample collected during recording.
 *
 * @property latitude Latitude in degrees (-90 to 90)
 * @property longitude Longitude in degrees (-180 to 180)
 * @property altitude Altitude in meters above WGS84 ellipsoid, null if unavailable
 * @property accuracy Horizontal accuracy radius in meters
 * @property speed Speed in meters per second, null if unavailable
 * @property bearing Bearing in degrees (0-360), null if unavailable
 * @property timestamp Unix timestamp when the location was captured
 * @property provider Location provider (gps, network, fused)
 */
data class LocationSample(
    val latitude: Double,
    val longitude: Double,
    val altitude: Double?,
    val accuracy: Float,
    val speed: Float?,
    val bearing: Float?,
    val timestamp: Instant,
    val provider: String
)
