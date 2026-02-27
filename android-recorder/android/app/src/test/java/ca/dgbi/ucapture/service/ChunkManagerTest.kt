package ca.dgbi.ucapture.service

import app.cash.turbine.test
import kotlinx.coroutines.ExperimentalCoroutinesApi
import kotlinx.coroutines.test.runTest
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Before
import org.junit.Rule
import org.junit.Test
import org.junit.rules.TemporaryFolder
import java.io.File

@OptIn(ExperimentalCoroutinesApi::class)
class ChunkManagerTest {

    @get:Rule
    val tempFolder = TemporaryFolder()

    private lateinit var chunkManager: ChunkManager
    private lateinit var recordingsDir: File

    @Before
    fun setUp() {
        chunkManager = ChunkManager()
        recordingsDir = tempFolder.newFolder("recordings")
        chunkManager.configure(recordingsDir)
    }

    @Test
    fun `startNewSession creates first chunk with number 1`() {
        val chunk = chunkManager.startNewSession()

        assertEquals(1, chunk.chunkNumber)
        assertNotNull(chunk.sessionId)
        assertNotNull(chunk.startTime)
        assertTrue(chunk.file.name.startsWith("ucap-"))
        assertTrue(chunk.file.name.endsWith("-001.m4a"))
    }

    @Test
    fun `chunk file is created in recordings directory`() {
        val chunk = chunkManager.startNewSession()

        assertEquals(recordingsDir, chunk.file.parentFile)
    }

    @Test
    fun `currentChunkInfo returns current chunk`() {
        assertNull(chunkManager.currentChunkInfo)

        val chunk = chunkManager.startNewSession()

        assertEquals(chunk, chunkManager.currentChunkInfo)
    }

    @Test
    fun `currentChunkNumber returns chunk number`() {
        assertEquals(0, chunkManager.currentChunkNumber)

        chunkManager.startNewSession()

        assertEquals(1, chunkManager.currentChunkNumber)
    }

    @Test
    fun `completeCurrentChunk returns completed chunk info`() {
        chunkManager.startNewSession()

        val completed = chunkManager.completeCurrentChunk()

        assertNotNull(completed)
        assertEquals(1, completed!!.chunkNumber)
        assertNotNull(completed.endTime)
        assertTrue(completed.endTime >= completed.startTime)
    }

    @Test
    fun `completeCurrentChunk returns null when no active chunk`() {
        val completed = chunkManager.completeCurrentChunk()

        assertNull(completed)
    }

    @Test
    fun `endSession stops timer and returns completed chunk`() {
        chunkManager.startNewSession()

        val completed = chunkManager.endSession()

        assertNotNull(completed)
        assertNull(chunkManager.currentChunkInfo)
    }

    @Test
    fun `reset clears current chunk`() {
        chunkManager.startNewSession()

        chunkManager.reset()

        assertNull(chunkManager.currentChunkInfo)
        assertEquals(0, chunkManager.currentChunkNumber)
    }

    @Test
    fun `configure clamps chunk duration to minimum`() {
        // Below minimum - should not crash
        chunkManager.configure(recordingsDir, 1)
        chunkManager.startNewSession()
        assertNotNull(chunkManager.currentChunkInfo)
    }

    @Test
    fun `configure clamps chunk duration to maximum`() {
        // Above maximum - should not crash
        chunkManager.configure(recordingsDir, 500)
        chunkManager.startNewSession()
        assertNotNull(chunkManager.currentChunkInfo)
    }

    @Test
    fun `chunk filenames include session ID and chunk number`() {
        val chunk = chunkManager.startNewSession()
        val sessionId = chunk.sessionId

        assertTrue(chunk.file.name.contains(sessionId))
        assertTrue(chunk.file.name.contains("-001"))
    }

    @Test
    fun `chunk filename includes timezone`() {
        val chunk = chunkManager.startNewSession()

        // Should have timezone like PST, PDT, EST, etc.
        val filename = chunk.file.name
        assertTrue(
            "Filename should contain timezone: $filename",
            filename.matches(Regex(".*-[A-Z]{2,4}-\\d{3}\\.m4a"))
        )
    }

    @Test
    fun `completedChunks flow emits when chunk is completed`() = runTest {
        chunkManager.startNewSession()

        chunkManager.completedChunks.test {
            chunkManager.completeCurrentChunk()

            val completed = awaitItem()
            assertEquals(1, completed.chunkNumber)
        }
    }

    @Test
    fun `completed chunk has same session ID as original`() {
        val chunk = chunkManager.startNewSession()
        val completed = chunkManager.completeCurrentChunk()

        assertEquals(chunk.sessionId, completed!!.sessionId)
    }

    @Test
    fun `completed chunk file is renamed to end-time based name`() {
        chunkManager.startNewSession()
        val completed = chunkManager.completeCurrentChunk()

        val filename = completed!!.file.name
        assertTrue(
            "Completed chunk filename should use end-time format without chunk number: $filename",
            filename.matches(Regex("ucap-\\d{8}-\\d{6}-[A-Z]{2,5}\\.m4a"))
        )
        assertEquals(recordingsDir, completed.file.parentFile)
    }

    @Test
    fun `stopChunkTimer can be called when no timer is running`() {
        // Should not throw
        chunkManager.stopChunkTimer()
    }

    @Test
    fun `multiple sessions create independent session IDs`() {
        val chunk1 = chunkManager.startNewSession()
        chunkManager.endSession()

        // Small delay to ensure different timestamp
        Thread.sleep(1100)

        val chunk2 = chunkManager.startNewSession()

        assertTrue(
            "Session IDs should be different: ${chunk1.sessionId} vs ${chunk2.sessionId}",
            chunk1.sessionId != chunk2.sessionId
        )
    }

    @Test
    fun `completedChunks channel never drops emissions`() = runTest {
        // Emit many chunks without a collector — Channel.UNLIMITED should buffer all
        val chunks = mutableListOf<ChunkManager.CompletedChunk>()
        repeat(20) { i ->
            chunkManager.startNewSession()
            chunkManager.completeCurrentChunk()
            // Reset to allow new session (endSession already called completeCurrentChunk,
            // so use reset + startNewSession for subsequent iterations)
            chunkManager.reset()
        }

        // Now collect — all 20 should be available
        chunkManager.completedChunks.test {
            repeat(20) {
                val item = awaitItem()
                chunks.add(item)
            }
        }

        assertEquals(20, chunks.size)
    }
}
