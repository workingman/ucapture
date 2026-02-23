import { v4 as uuidv4 } from 'uuid';

/**
 * Batch ID format: YYYYMMDD-HHMMSS-GMT-{uuid4}
 * Uses recording start time from metadata, normalized to UTC.
 * Critical for DR recovery -- the timestamp encodes when the recording began.
 *
 * @param recordingStartedAt - ISO 8601 date string of when recording started
 * @returns Batch ID in format YYYYMMDD-HHMMSS-GMT-{uuid4}
 *
 * @example
 * generateBatchId("2026-02-22T14:30:27Z")
 * // => "20260222-143027-GMT-a1b2c3d4-e5f6-7890-abcd-ef1234567890"
 */
export function generateBatchId(recordingStartedAt: string): string {
  if (!recordingStartedAt) {
    throw new Error('recordingStartedAt is required');
  }

  const date = new Date(recordingStartedAt);

  if (isNaN(date.getTime())) {
    throw new Error(`Invalid ISO 8601 date: "${recordingStartedAt}"`);
  }

  const year = date.getUTCFullYear().toString();
  const month = (date.getUTCMonth() + 1).toString().padStart(2, '0');
  const day = date.getUTCDate().toString().padStart(2, '0');
  const hours = date.getUTCHours().toString().padStart(2, '0');
  const minutes = date.getUTCMinutes().toString().padStart(2, '0');
  const seconds = date.getUTCSeconds().toString().padStart(2, '0');

  const timestamp = `${year}${month}${day}-${hours}${minutes}${seconds}-GMT`;
  const uuid = uuidv4();

  return `${timestamp}-${uuid}`;
}

/** Result of parsing a batch ID back into its components. */
export interface ParsedBatchId {
  readonly recordingStartedAt: Date;
  readonly uuid: string;
}

/**
 * Parses a batch ID back into its recording start time and UUID.
 *
 * @param batchId - Batch ID in format YYYYMMDD-HHMMSS-GMT-{uuid4}
 * @returns Parsed components: recordingStartedAt (Date) and uuid (string)
 *
 * @example
 * parseBatchId("20260222-143027-GMT-a1b2c3d4-e5f6-7890-abcd-ef1234567890")
 * // => { recordingStartedAt: Date("2026-02-22T14:30:27Z"), uuid: "a1b2c3d4-e5f6-7890-abcd-ef1234567890" }
 */
export function parseBatchId(batchId: string): ParsedBatchId {
  if (!batchId) {
    throw new Error('batchId is required');
  }

  // Format: YYYYMMDD-HHMMSS-GMT-{uuid4}
  // uuid4 format: xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx
  const pattern = /^(\d{4})(\d{2})(\d{2})-(\d{2})(\d{2})(\d{2})-GMT-([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})$/;
  const match = batchId.match(pattern);

  if (!match) {
    throw new Error(`Invalid batch ID format: "${batchId}"`);
  }

  const [, year, month, day, hours, minutes, seconds, uuid] = match;
  const isoString = `${year}-${month}-${day}T${hours}:${minutes}:${seconds}Z`;
  const recordingStartedAt = new Date(isoString);

  if (isNaN(recordingStartedAt.getTime())) {
    throw new Error(`Invalid date components in batch ID: "${batchId}"`);
  }

  return { recordingStartedAt, uuid };
}
