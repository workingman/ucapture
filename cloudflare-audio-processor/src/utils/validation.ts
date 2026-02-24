/**
 * Zod schemas for request validation.
 *
 * MetadataSchema validates the JSON sidecar uploaded by the Android app.
 * Matches TDD section 3.3 (Metadata JSON Schema).
 */

import { z } from 'zod';

/** ISO 8601 date string validator. */
const isoDateString = z.string().refine(
  (val) => !isNaN(new Date(val).getTime()),
  { message: 'Must be a valid ISO 8601 date string' },
);

/** Recording section -- required in every metadata sidecar. */
const RecordingSchema = z.object({
  started_at: isoDateString,
  ended_at: isoDateString,
  duration_seconds: z.number().nonnegative({ message: 'duration_seconds must not be negative' }),
  audio_format: z.string(),
  sample_rate: z.number().positive(),
  channels: z.number().int().positive(),
  bitrate: z.number().positive(),
  file_size_bytes: z.number().int().nonnegative(),
});

/** Optional location data captured during recording. */
const LocationSchema = z.object({
  latitude: z.number().min(-90).max(90),
  longitude: z.number().min(-180).max(180),
  accuracy_meters: z.number().nonnegative(),
  captured_at: isoDateString,
  address: z.string().optional(),
});

/** Optional calendar event context. */
const CalendarSchema = z.object({
  event_id: z.string().optional(),
  event_title: z.string().optional(),
  attendees: z.array(z.string()).optional(),
});

/** Image metadata for images captured during recording. */
const ImageItemSchema = z.object({
  filename: z.string(),
  captured_at: isoDateString,
  size_bytes: z.number().int().nonnegative(),
});

/** Note metadata for text notes attached during recording. */
const NoteItemSchema = z.object({
  text: z.string(),
  created_at: isoDateString,
});

/** Device information -- required in every metadata sidecar. */
const DeviceSchema = z.object({
  model: z.string(),
  os_version: z.string(),
  app_version: z.string(),
});

/**
 * Full metadata sidecar schema matching TDD section 3.3.
 *
 * Required sections: recording, device.
 * Optional sections: location, calendar, images, notes.
 */
export const MetadataSchema = z.object({
  recording: RecordingSchema,
  location: LocationSchema.optional(),
  calendar: CalendarSchema.optional(),
  images: z.array(ImageItemSchema).optional(),
  notes: z.array(NoteItemSchema).optional(),
  device: DeviceSchema,
});

/** Inferred TypeScript type from the Zod MetadataSchema. */
export type Metadata = z.infer<typeof MetadataSchema>;

/** Valid batch statuses for query filtering. */
const batchStatusEnum = z.enum(['uploaded', 'processing', 'completed', 'failed']);

/**
 * Zod schema for GET /v1/batches query parameters.
 *
 * All fields are optional strings from the URL; numeric fields are coerced.
 */
export const BatchListQuerySchema = z.object({
  status: batchStatusEnum.optional(),
  start_date: z.string().refine(
    (val) => !isNaN(new Date(val).getTime()),
    { message: 'start_date must be a valid ISO 8601 date string' },
  ).optional(),
  end_date: z.string().refine(
    (val) => !isNaN(new Date(val).getTime()),
    { message: 'end_date must be a valid ISO 8601 date string' },
  ).optional(),
  limit: z.coerce.number().int().min(1).max(100).default(50),
  offset: z.coerce.number().int().min(0).default(0),
});

/** Inferred TypeScript type from BatchListQuerySchema. */
export type BatchListQuery = z.infer<typeof BatchListQuerySchema>;
