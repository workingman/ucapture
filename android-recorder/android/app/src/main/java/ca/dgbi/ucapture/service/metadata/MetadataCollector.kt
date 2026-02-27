package ca.dgbi.ucapture.service.metadata

import ca.dgbi.ucapture.service.ChunkManager
import kotlinx.coroutines.flow.Flow

/**
 * Interface for metadata collectors that gather contextual information
 * during audio recording sessions.
 *
 * Implementations collect different types of metadata (e.g. location)
 * and associate them with recording chunks.
 */
interface MetadataCollector<T> {

    /**
     * Unique identifier for this collector type.
     */
    val collectorId: String

    /**
     * Check if this collector is available and has required permissions.
     *
     * @return true if the collector can gather metadata
     */
    suspend fun isAvailable(): Boolean

    /**
     * Start collecting metadata for a recording session.
     *
     * Called when recording begins. The collector should begin
     * gathering metadata samples at appropriate intervals.
     */
    suspend fun startCollecting()

    /**
     * Stop collecting metadata.
     *
     * Called when recording stops. The collector should clean up
     * any resources and stop gathering samples.
     */
    suspend fun stopCollecting()

    /**
     * Get metadata collected for a specific chunk.
     *
     * @param chunk The chunk to get metadata for
     * @return List of metadata samples collected during the chunk's time range
     */
    suspend fun getMetadataForChunk(chunk: ChunkManager.CompletedChunk): List<T>

    /**
     * Flow of metadata samples as they are collected in real-time.
     *
     * Observers can use this to display live metadata in the UI.
     */
    val metadataFlow: Flow<T>
}

/**
 * Aggregates multiple metadata collectors and coordinates their lifecycle.
 */
class MetadataCollectorManager {

    private val collectors = mutableListOf<MetadataCollector<*>>()

    /**
     * Register a metadata collector.
     */
    fun register(collector: MetadataCollector<*>) {
        collectors.add(collector)
    }

    /**
     * Unregister a metadata collector.
     */
    fun unregister(collector: MetadataCollector<*>) {
        collectors.remove(collector)
    }

    /**
     * Get all registered collectors.
     */
    fun getCollectors(): List<MetadataCollector<*>> = collectors.toList()

    /**
     * Start all available collectors.
     */
    suspend fun startAll() {
        collectors.forEach { collector ->
            if (collector.isAvailable()) {
                collector.startCollecting()
            }
        }
    }

    /**
     * Stop all collectors.
     */
    suspend fun stopAll() {
        collectors.forEach { it.stopCollecting() }
    }

    /**
     * Collect metadata from all collectors for a completed chunk.
     *
     * @param chunk The completed chunk
     * @return Map of collector ID to list of metadata samples
     */
    suspend fun collectMetadataForChunk(chunk: ChunkManager.CompletedChunk): Map<String, List<*>> {
        return collectors.associate { collector ->
            collector.collectorId to collector.getMetadataForChunk(chunk)
        }
    }
}
