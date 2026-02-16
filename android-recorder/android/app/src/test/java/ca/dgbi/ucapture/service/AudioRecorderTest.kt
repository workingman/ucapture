package ca.dgbi.ucapture.service

import android.content.Context
import android.media.MediaRecorder
import io.mockk.every
import io.mockk.just
import io.mockk.mockk
import io.mockk.runs
import io.mockk.verify
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Before
import org.junit.Test
import java.io.File

class AudioRecorderTest {

    private lateinit var mockContext: Context
    private lateinit var mockMediaRecorder: MediaRecorder
    private lateinit var audioRecorder: TestableAudioRecorder
    private lateinit var tempFile: File

    @Before
    fun setUp() {
        mockContext = mockk(relaxed = true)
        mockMediaRecorder = mockk(relaxed = true)
        audioRecorder = TestableAudioRecorder(mockContext, mockMediaRecorder)
        tempFile = File.createTempFile("test_recording", ".m4a")
    }

    @Test
    fun `Quality enum has correct bitrate values`() {
        assertEquals(64_000, AudioRecorder.Quality.LOW.bitrate)
        assertEquals(128_000, AudioRecorder.Quality.MEDIUM.bitrate)
        assertEquals(256_000, AudioRecorder.Quality.HIGH.bitrate)
    }

    @Test
    fun `initial state is not recording`() {
        assertFalse(audioRecorder.isRecording)
        assertFalse(audioRecorder.isPausedState)
        assertNull(audioRecorder.outputFile)
    }

    @Test
    fun `start recording configures MediaRecorder correctly`() {
        every { mockMediaRecorder.prepare() } just runs
        every { mockMediaRecorder.start() } just runs

        val result = audioRecorder.start(tempFile, AudioRecorder.Quality.MEDIUM)

        assertTrue(result)
        assertTrue(audioRecorder.isRecording)
        assertFalse(audioRecorder.isPausedState)
        assertEquals(tempFile, audioRecorder.outputFile)

        verify { mockMediaRecorder.setAudioSource(MediaRecorder.AudioSource.MIC) }
        verify { mockMediaRecorder.setOutputFormat(MediaRecorder.OutputFormat.MPEG_4) }
        verify { mockMediaRecorder.setAudioEncoder(MediaRecorder.AudioEncoder.AAC) }
        verify { mockMediaRecorder.setAudioEncodingBitRate(128_000) }
        verify { mockMediaRecorder.setAudioSamplingRate(44100) }
        verify { mockMediaRecorder.setAudioChannels(1) }
        verify { mockMediaRecorder.prepare() }
        verify { mockMediaRecorder.start() }
    }

    @Test
    fun `start with LOW quality uses 64kbps`() {
        every { mockMediaRecorder.prepare() } just runs
        every { mockMediaRecorder.start() } just runs

        audioRecorder.start(tempFile, AudioRecorder.Quality.LOW)

        verify { mockMediaRecorder.setAudioEncodingBitRate(64_000) }
    }

    @Test
    fun `start with HIGH quality uses 256kbps`() {
        every { mockMediaRecorder.prepare() } just runs
        every { mockMediaRecorder.start() } just runs

        audioRecorder.start(tempFile, AudioRecorder.Quality.HIGH)

        verify { mockMediaRecorder.setAudioEncodingBitRate(256_000) }
    }

    @Test
    fun `start returns false if already recording`() {
        every { mockMediaRecorder.prepare() } just runs
        every { mockMediaRecorder.start() } just runs

        audioRecorder.start(tempFile, AudioRecorder.Quality.MEDIUM)
        val result = audioRecorder.start(tempFile, AudioRecorder.Quality.MEDIUM)

        assertFalse(result)
    }

    @Test
    fun `pause sets paused state`() {
        every { mockMediaRecorder.prepare() } just runs
        every { mockMediaRecorder.start() } just runs
        every { mockMediaRecorder.pause() } just runs

        audioRecorder.start(tempFile, AudioRecorder.Quality.MEDIUM)
        val result = audioRecorder.pause()

        assertTrue(result)
        assertFalse(audioRecorder.isRecording)
        assertTrue(audioRecorder.isPausedState)
        verify { mockMediaRecorder.pause() }
    }

    @Test
    fun `pause returns false if not recording`() {
        val result = audioRecorder.pause()

        assertFalse(result)
    }

    @Test
    fun `resume clears paused state`() {
        every { mockMediaRecorder.prepare() } just runs
        every { mockMediaRecorder.start() } just runs
        every { mockMediaRecorder.pause() } just runs
        every { mockMediaRecorder.resume() } just runs

        audioRecorder.start(tempFile, AudioRecorder.Quality.MEDIUM)
        audioRecorder.pause()
        val result = audioRecorder.resume()

        assertTrue(result)
        assertTrue(audioRecorder.isRecording)
        assertFalse(audioRecorder.isPausedState)
        verify { mockMediaRecorder.resume() }
    }

    @Test
    fun `resume returns false if not paused`() {
        every { mockMediaRecorder.prepare() } just runs
        every { mockMediaRecorder.start() } just runs

        audioRecorder.start(tempFile, AudioRecorder.Quality.MEDIUM)
        val result = audioRecorder.resume()

        assertFalse(result)
    }

    @Test
    fun `stop returns file and resets state`() {
        every { mockMediaRecorder.prepare() } just runs
        every { mockMediaRecorder.start() } just runs
        every { mockMediaRecorder.stop() } just runs
        every { mockMediaRecorder.release() } just runs

        audioRecorder.start(tempFile, AudioRecorder.Quality.MEDIUM)
        val result = audioRecorder.stop()

        assertEquals(tempFile, result)
        assertFalse(audioRecorder.isRecording)
        assertFalse(audioRecorder.isPausedState)
        assertNull(audioRecorder.outputFile)
        verify { mockMediaRecorder.stop() }
        verify { mockMediaRecorder.release() }
    }

    @Test
    fun `stop returns null if not recording`() {
        val result = audioRecorder.stop()

        assertNull(result)
    }

    @Test
    fun `stop resumes before stopping if paused`() {
        every { mockMediaRecorder.prepare() } just runs
        every { mockMediaRecorder.start() } just runs
        every { mockMediaRecorder.pause() } just runs
        every { mockMediaRecorder.resume() } just runs
        every { mockMediaRecorder.stop() } just runs
        every { mockMediaRecorder.release() } just runs

        audioRecorder.start(tempFile, AudioRecorder.Quality.MEDIUM)
        audioRecorder.pause()
        audioRecorder.stop()

        verify { mockMediaRecorder.resume() }
        verify { mockMediaRecorder.stop() }
    }

    /**
     * Testable subclass that allows injecting a mock MediaRecorder
     */
    class TestableAudioRecorder(
        context: Context,
        private val mockRecorder: MediaRecorder
    ) : AudioRecorder(context) {
        override fun createMediaRecorderInstance(): MediaRecorder = mockRecorder
    }
}
