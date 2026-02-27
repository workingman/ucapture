package ca.dgbi.ucapture.data.local.relation

import androidx.room.Embedded
import androidx.room.Relation
import ca.dgbi.ucapture.data.local.entity.LocationSampleEntity
import ca.dgbi.ucapture.data.local.entity.RecordingEntity

/**
 * Room relation class that loads a recording with all its associated metadata.
 *
 * Used with @Transaction queries to fetch recording + location samples
 * in a single operation.
 */
data class RecordingWithMetadata(
    @Embedded
    val recording: RecordingEntity,

    @Relation(
        parentColumn = "id",
        entityColumn = "recording_id"
    )
    val locationSamples: List<LocationSampleEntity>
)
