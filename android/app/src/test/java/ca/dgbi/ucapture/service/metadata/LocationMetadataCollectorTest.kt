package ca.dgbi.ucapture.service.metadata

import android.Manifest
import android.content.Context
import android.content.pm.PackageManager
import android.location.Location
import ca.dgbi.ucapture.service.ChunkManager
import com.google.android.gms.location.FusedLocationProviderClient
import com.google.android.gms.location.LocationCallback
import com.google.android.gms.location.LocationRequest
import com.google.android.gms.location.LocationResult
import com.google.android.gms.location.LocationServices
import com.google.android.gms.tasks.Task
import io.mockk.every
import io.mockk.mockk
import io.mockk.mockkStatic
import io.mockk.slot
import io.mockk.unmockkAll
import io.mockk.verify
import kotlinx.coroutines.ExperimentalCoroutinesApi
import kotlinx.coroutines.test.runTest
import org.junit.After
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Before
import org.junit.Test
import java.io.File
import java.time.Instant
import java.time.ZoneId
import java.time.ZonedDateTime

@OptIn(ExperimentalCoroutinesApi::class)
class LocationMetadataCollectorTest {

    private lateinit var mockContext: Context
    private lateinit var mockFusedLocationClient: FusedLocationProviderClient
    private lateinit var mockLooper: android.os.Looper
    private lateinit var collector: LocationMetadataCollector
    private val locationCallbackSlot = slot<LocationCallback>()

    @Before
    fun setUp() {
        mockContext = mockk(relaxed = true)
        mockFusedLocationClient = mockk(relaxed = true)
        mockLooper = mockk(relaxed = true)

        mockkStatic(LocationServices::class)
        every { LocationServices.getFusedLocationProviderClient(any<Context>()) } returns mockFusedLocationClient

        mockkStatic(android.os.Looper::class)
        every { android.os.Looper.getMainLooper() } returns mockLooper

        every {
            mockFusedLocationClient.requestLocationUpdates(
                any<LocationRequest>(),
                capture(locationCallbackSlot),
                any()
            )
        } returns mockk<Task<Void>>(relaxed = true)

        every {
            mockFusedLocationClient.removeLocationUpdates(any<LocationCallback>())
        } returns mockk<Task<Void>>(relaxed = true)
    }

    @After
    fun tearDown() {
        unmockkAll()
    }

    @Test
    fun `collectorId returns location`() {
        collector = createCollectorWithPermission(granted = true)
        assertEquals("location", collector.collectorId)
    }

    @Test
    fun `isAvailable returns true when fine location permission granted`() = runTest {
        collector = createCollectorWithPermission(granted = true, permissionType = Manifest.permission.ACCESS_FINE_LOCATION)
        assertTrue(collector.isAvailable())
    }

    @Test
    fun `isAvailable returns true when coarse location permission granted`() = runTest {
        collector = createCollectorWithPermission(granted = true, permissionType = Manifest.permission.ACCESS_COARSE_LOCATION)
        assertTrue(collector.isAvailable())
    }

    @Test
    fun `isAvailable returns false when no location permission granted`() = runTest {
        collector = createCollectorWithPermission(granted = false)
        assertFalse(collector.isAvailable())
    }

    @Test
    fun `startCollecting requests location updates when permission granted`() = runTest {
        collector = createCollectorWithPermission(granted = true)

        collector.startCollecting()

        assertTrue(collector.isCurrentlyCollecting())
        verify { mockFusedLocationClient.requestLocationUpdates(any<LocationRequest>(), any<LocationCallback>(), any()) }
    }

    @Test
    fun `startCollecting does nothing when no permission`() = runTest {
        collector = createCollectorWithPermission(granted = false)

        collector.startCollecting()

        assertFalse(collector.isCurrentlyCollecting())
        verify(exactly = 0) { mockFusedLocationClient.requestLocationUpdates(any<LocationRequest>(), any<LocationCallback>(), any()) }
    }

    @Test
    fun `startCollecting does nothing when already collecting`() = runTest {
        collector = createCollectorWithPermission(granted = true)

        collector.startCollecting()
        collector.startCollecting() // Second call should be no-op

        verify(exactly = 1) { mockFusedLocationClient.requestLocationUpdates(any<LocationRequest>(), any<LocationCallback>(), any()) }
    }

    @Test
    fun `stopCollecting removes location updates`() = runTest {
        collector = createCollectorWithPermission(granted = true)

        collector.startCollecting()
        collector.stopCollecting()

        assertFalse(collector.isCurrentlyCollecting())
        verify { mockFusedLocationClient.removeLocationUpdates(any<LocationCallback>()) }
    }

    @Test
    fun `stopCollecting does nothing when not collecting`() = runTest {
        collector = createCollectorWithPermission(granted = true)

        collector.stopCollecting()

        verify(exactly = 0) { mockFusedLocationClient.removeLocationUpdates(any<LocationCallback>()) }
    }

    @Test
    fun `location callback stores samples`() = runTest {
        collector = createCollectorWithPermission(granted = true)
        collector.startCollecting()

        // Simulate location update
        val mockLocation = createMockLocation(
            latitude = 37.7749,
            longitude = -122.4194,
            accuracy = 10.0f,
            time = 1000L
        )
        val locationResult = LocationResult.create(listOf(mockLocation))
        locationCallbackSlot.captured.onLocationResult(locationResult)

        val samples = collector.getAllSamples()
        assertEquals(1, samples.size)
        assertEquals(37.7749, samples[0].latitude, 0.0001)
        assertEquals(-122.4194, samples[0].longitude, 0.0001)
        assertEquals(10.0f, samples[0].accuracy)
    }

    @Test
    fun `getLastLocation returns most recent sample`() = runTest {
        collector = createCollectorWithPermission(granted = true)
        collector.startCollecting()

        // Simulate multiple location updates
        listOf(1000L, 2000L, 3000L).forEach { time ->
            val mockLocation = createMockLocation(
                latitude = 37.0 + time / 1000.0,
                longitude = -122.0,
                accuracy = 10.0f,
                time = time
            )
            val locationResult = LocationResult.create(listOf(mockLocation))
            locationCallbackSlot.captured.onLocationResult(locationResult)
        }

        val lastLocation = collector.getLastLocation()
        assertNotNull(lastLocation)
        assertEquals(40.0, lastLocation!!.latitude, 0.0001) // 37.0 + 3.0
    }

    @Test
    fun `getMetadataForChunk filters samples by time range`() = runTest {
        collector = createCollectorWithPermission(granted = true)
        collector.startCollecting()

        // Simulate location updates at different times
        listOf(1000L, 5000L, 10000L, 15000L).forEach { time ->
            val mockLocation = createMockLocation(
                latitude = 37.0,
                longitude = -122.0,
                accuracy = 10.0f,
                time = time
            )
            val locationResult = LocationResult.create(listOf(mockLocation))
            locationCallbackSlot.captured.onLocationResult(locationResult)
        }

        // Create a chunk that spans 4000ms to 12000ms
        val chunk = ChunkManager.CompletedChunk(
            file = File("/test/chunk.m4a"),
            chunkNumber = 1,
            startTime = ZonedDateTime.ofInstant(Instant.ofEpochMilli(4000L), ZoneId.systemDefault()),
            endTime = ZonedDateTime.ofInstant(Instant.ofEpochMilli(12000L), ZoneId.systemDefault()),
            sessionId = "test-session"
        )

        val chunkedSamples = collector.getMetadataForChunk(chunk)

        // Should only include samples at 5000ms and 10000ms
        assertEquals(2, chunkedSamples.size)
    }

    @Test
    fun `clearSamples removes all collected samples`() = runTest {
        collector = createCollectorWithPermission(granted = true)
        collector.startCollecting()

        val mockLocation = createMockLocation(
            latitude = 37.7749,
            longitude = -122.4194,
            accuracy = 10.0f,
            time = 1000L
        )
        val locationResult = LocationResult.create(listOf(mockLocation))
        locationCallbackSlot.captured.onLocationResult(locationResult)

        assertEquals(1, collector.getAllSamples().size)

        collector.clearSamples()

        assertEquals(0, collector.getAllSamples().size)
        assertNull(collector.getLastLocation())
    }

    @Test
    fun `default sampling interval is 60 seconds`() {
        assertEquals(60_000L, LocationMetadataCollector.DEFAULT_SAMPLING_INTERVAL_MS)
    }

    @Test
    fun `location sample includes optional fields when available`() = runTest {
        collector = createCollectorWithPermission(granted = true)
        collector.startCollecting()

        val mockLocation = createMockLocation(
            latitude = 37.7749,
            longitude = -122.4194,
            accuracy = 10.0f,
            time = 1000L,
            altitude = 100.0,
            speed = 5.0f,
            bearing = 180.0f
        )
        val locationResult = LocationResult.create(listOf(mockLocation))
        locationCallbackSlot.captured.onLocationResult(locationResult)

        val sample = collector.getLastLocation()!!
        assertEquals(100.0, sample.altitude!!, 0.01)
        assertEquals(5.0f, sample.speed!!)
        assertEquals(180.0f, sample.bearing!!)
    }

    private fun createCollectorWithPermission(
        granted: Boolean,
        permissionType: String = Manifest.permission.ACCESS_FINE_LOCATION
    ): LocationMetadataCollector {
        val finePermResult = if (granted && permissionType == Manifest.permission.ACCESS_FINE_LOCATION) {
            PackageManager.PERMISSION_GRANTED
        } else {
            PackageManager.PERMISSION_DENIED
        }
        val coarsePermResult = if (granted && permissionType == Manifest.permission.ACCESS_COARSE_LOCATION) {
            PackageManager.PERMISSION_GRANTED
        } else {
            PackageManager.PERMISSION_DENIED
        }

        every { mockContext.checkPermission(Manifest.permission.ACCESS_FINE_LOCATION, any(), any()) } returns finePermResult
        every { mockContext.checkPermission(Manifest.permission.ACCESS_COARSE_LOCATION, any(), any()) } returns coarsePermResult

        mockkStatic("androidx.core.content.ContextCompat")
        every {
            androidx.core.content.ContextCompat.checkSelfPermission(mockContext, Manifest.permission.ACCESS_FINE_LOCATION)
        } returns finePermResult
        every {
            androidx.core.content.ContextCompat.checkSelfPermission(mockContext, Manifest.permission.ACCESS_COARSE_LOCATION)
        } returns coarsePermResult

        return LocationMetadataCollector(mockContext)
    }

    private fun createMockLocation(
        latitude: Double,
        longitude: Double,
        accuracy: Float,
        time: Long,
        altitude: Double? = null,
        speed: Float? = null,
        bearing: Float? = null
    ): Location {
        val location = mockk<Location>(relaxed = true)
        every { location.latitude } returns latitude
        every { location.longitude } returns longitude
        every { location.accuracy } returns accuracy
        every { location.time } returns time
        every { location.provider } returns "fused"

        every { location.hasAltitude() } returns (altitude != null)
        every { location.altitude } returns (altitude ?: 0.0)

        every { location.hasSpeed() } returns (speed != null)
        every { location.speed } returns (speed ?: 0.0f)

        every { location.hasBearing() } returns (bearing != null)
        every { location.bearing } returns (bearing ?: 0.0f)

        return location
    }
}
