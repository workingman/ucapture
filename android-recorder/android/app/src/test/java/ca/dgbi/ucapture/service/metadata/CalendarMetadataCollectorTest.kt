package ca.dgbi.ucapture.service.metadata

import android.Manifest
import android.content.ContentResolver
import android.content.Context
import android.content.pm.PackageManager
import ca.dgbi.ucapture.service.ChunkManager
import io.mockk.every
import io.mockk.mockk
import io.mockk.mockkStatic
import io.mockk.unmockkAll
import kotlinx.coroutines.ExperimentalCoroutinesApi
import kotlinx.coroutines.test.runTest
import org.junit.After
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Before
import org.junit.Test
import java.io.File
import java.time.Instant
import java.time.ZoneId
import java.time.ZonedDateTime

/**
 * Unit tests for CalendarMetadataCollector.
 *
 * Note: Tests that require actual CalendarContract queries are skipped here
 * because CalendarContract constants (like CONTENT_URI) aren't available
 * in unit tests. Those should be covered in instrumented tests.
 */
@OptIn(ExperimentalCoroutinesApi::class)
class CalendarMetadataCollectorTest {

    private lateinit var mockContext: Context
    private lateinit var mockContentResolver: ContentResolver
    private lateinit var collector: CalendarMetadataCollector

    @Before
    fun setUp() {
        mockContext = mockk(relaxed = true)
        mockContentResolver = mockk(relaxed = true)
        every { mockContext.contentResolver } returns mockContentResolver
    }

    @After
    fun tearDown() {
        unmockkAll()
    }

    @Test
    fun `collectorId returns calendar`() {
        collector = createCollectorWithPermission(granted = true)
        assertEquals("calendar", collector.collectorId)
    }

    @Test
    fun `isAvailable returns true when calendar permission granted`() = runTest {
        collector = createCollectorWithPermission(granted = true)
        assertTrue(collector.isAvailable())
    }

    @Test
    fun `isAvailable returns false when calendar permission denied`() = runTest {
        collector = createCollectorWithPermission(granted = false)
        assertFalse(collector.isAvailable())
    }

    @Test
    fun `startCollecting sets collecting state`() = runTest {
        collector = createCollectorWithPermission(granted = true)

        assertFalse(collector.isCurrentlyCollecting())

        collector.startCollecting()

        assertTrue(collector.isCurrentlyCollecting())
    }

    @Test
    fun `stopCollecting clears collecting state`() = runTest {
        collector = createCollectorWithPermission(granted = true)

        collector.startCollecting()
        collector.stopCollecting()

        assertFalse(collector.isCurrentlyCollecting())
    }

    @Test
    fun `getMetadataForChunk returns empty list when no permission`() = runTest {
        collector = createCollectorWithPermission(granted = false)
        collector.startCollecting()

        val chunk = createTestChunk()
        val events = collector.getMetadataForChunk(chunk)

        assertTrue(events.isEmpty())
    }

    @Test
    fun `clearCache removes all cached entries`() = runTest {
        collector = createCollectorWithPermission(granted = true)

        // Manually verify clearCache works
        // Note: Can't test cache population without CalendarContract
        assertEquals(0, collector.getCacheSize())
        collector.clearCache()
        assertEquals(0, collector.getCacheSize())
    }

    @Test
    fun `startCollecting while already collecting is no-op`() = runTest {
        collector = createCollectorWithPermission(granted = true)

        collector.startCollecting()
        assertTrue(collector.isCurrentlyCollecting())

        // Second startCollecting should be a no-op (not throw)
        collector.startCollecting()
        assertTrue(collector.isCurrentlyCollecting())
    }

    @Test
    fun `stopCollecting while not collecting is no-op`() = runTest {
        collector = createCollectorWithPermission(granted = true)

        assertFalse(collector.isCurrentlyCollecting())

        // Should not throw
        collector.stopCollecting()

        assertFalse(collector.isCurrentlyCollecting())
    }

    private fun createCollectorWithPermission(granted: Boolean): CalendarMetadataCollector {
        val permResult = if (granted) PackageManager.PERMISSION_GRANTED else PackageManager.PERMISSION_DENIED

        mockkStatic("androidx.core.content.ContextCompat")
        every {
            androidx.core.content.ContextCompat.checkSelfPermission(mockContext, Manifest.permission.READ_CALENDAR)
        } returns permResult

        return CalendarMetadataCollector(mockContext)
    }

    private fun createTestChunk(
        filePath: String = "/test/chunk.m4a",
        startTime: Long = 0L,
        endTime: Long = 60000L
    ): ChunkManager.CompletedChunk {
        return ChunkManager.CompletedChunk(
            file = File(filePath),
            chunkNumber = 1,
            startTime = ZonedDateTime.ofInstant(Instant.ofEpochMilli(startTime), ZoneId.systemDefault()),
            endTime = ZonedDateTime.ofInstant(Instant.ofEpochMilli(endTime), ZoneId.systemDefault()),
            sessionId = "test-session"
        )
    }
}
