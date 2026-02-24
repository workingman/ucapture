/**
 * R2 path generation helpers for DR-safe file naming.
 *
 * All R2 artifacts are stored under:
 *   {user_id}/{batch_id}/{artifact_type}/{filename}
 */

/** Valid artifact types for R2 storage. */
export const ARTIFACT_TYPES = [
  'raw-audio',
  'metadata',
  'images',
  'notes',
  'cleaned-audio',
  'transcript',
] as const;

export type ArtifactType = typeof ARTIFACT_TYPES[number];

/** Result of parsing an R2 path back into its components. */
export interface ParsedR2Path {
  readonly userId: string;
  readonly batchId: string;
  readonly artifactType: ArtifactType;
  readonly filename: string;
}

/**
 * Builds an R2 storage path from its components.
 *
 * @param userId - Google OAuth sub claim (opaque string)
 * @param batchId - Batch ID in YYYYMMDD-HHMMSS-GMT-uuid4 format
 * @param artifactType - One of the 6 valid artifact types
 * @param filename - The file name (e.g., "recording.m4a")
 * @returns Full R2 path: {userId}/{batchId}/{artifactType}/{filename}
 *
 * @example
 * buildR2Path("107234567890", "20260222-143027-GMT-abc123", "raw-audio", "recording.m4a")
 * // => "107234567890/20260222-143027-GMT-abc123/raw-audio/recording.m4a"
 */
export function buildR2Path(
  userId: string,
  batchId: string,
  artifactType: ArtifactType,
  filename: string,
): string {
  validateSegment(userId, 'userId');
  validateSegment(batchId, 'batchId');
  validateSegment(filename, 'filename');
  validateArtifactType(artifactType);

  return `${userId}/${batchId}/${artifactType}/${filename}`;
}

/**
 * Parses an R2 path back into its components with validation.
 *
 * @param path - Full R2 path: {userId}/{batchId}/{artifactType}/{filename}
 * @returns Parsed components
 *
 * @example
 * parseR2Path("107234567890/20260222-143027-GMT-abc123/raw-audio/recording.m4a")
 * // => { userId: "107234567890", batchId: "20260222-143027-GMT-abc123", artifactType: "raw-audio", filename: "recording.m4a" }
 */
export function parseR2Path(path: string): ParsedR2Path {
  if (!path) {
    throw new Error('R2 path is required');
  }

  // Reject path traversal attempts
  if (path.includes('..')) {
    throw new Error('Path traversal detected: ".." is not allowed in R2 paths');
  }

  const segments = path.split('/');

  // batch_id contains hyphens but is a single segment; the path has exactly 4 logical parts:
  // userId / batchId (YYYYMMDD-HHMMSS-GMT-uuid) / artifactType / filename
  // batchId itself has the form: XXXXXXXX-XXXXXX-GMT-XXXXXXXX-XXXX-XXXX-XXXX-XXXXXXXXXXXX
  // That is 8 dashes in the batchId, so total segments when split by "/" should be >= 4.
  // But we need exactly: userId, then everything up to artifactType and filename.
  // Since batchId never contains "/", splitting by "/" gives exactly 4 segments minimum.

  if (segments.length < 4) {
    throw new Error(`Insufficient path segments: expected at least 4, got ${segments.length}`);
  }

  // For paths with more than 4 segments, the filename may contain slashes (unlikely but handle gracefully)
  const userId = segments[0];
  // batchId is segments[1] through segments[length-3] joined (handles edge cases)
  // Actually the batchId never contains "/", so it's always segments[1]
  // artifactType is segments[length-2], filename is segments[length-1]
  // For a standard 4-segment path: [userId, batchId, artifactType, filename]
  const batchId = segments[1];
  const artifactType = segments[2];
  const filename = segments.slice(3).join('/');

  validateSegment(userId, 'userId');
  validateSegment(batchId, 'batchId');
  validateSegment(filename, 'filename');
  validateArtifactType(artifactType);

  return {
    userId,
    batchId,
    artifactType: artifactType as ArtifactType,
    filename,
  };
}

/** Convenience: builds the R2 path for raw audio. */
export function buildAudioPath(userId: string, batchId: string): string {
  return buildR2Path(userId, batchId, 'raw-audio', 'recording.m4a');
}

/** Convenience: builds the R2 path for metadata JSON. */
export function buildMetadataPath(userId: string, batchId: string): string {
  return buildR2Path(userId, batchId, 'metadata', 'metadata.json');
}

/** Convenience: builds the R2 path for an image by index. */
export function buildImagePath(
  userId: string,
  batchId: string,
  index: number,
  filename: string,
): string {
  return buildR2Path(userId, batchId, 'images', `${index}-${filename}`);
}

/** Convenience: builds the R2 path for notes JSON. */
export function buildNotesPath(userId: string, batchId: string): string {
  return buildR2Path(userId, batchId, 'notes', 'notes.json');
}

/** Validates that a path segment is non-empty and contains no path traversal. */
function validateSegment(value: string, name: string): void {
  if (!value || value.trim() === '') {
    throw new Error(`${name} must not be empty`);
  }
  if (value.includes('..')) {
    throw new Error(`Path traversal detected: ".." is not allowed in ${name}`);
  }
}

/** Validates that the artifact type is one of the known types. */
function validateArtifactType(value: string): void {
  if (!ARTIFACT_TYPES.includes(value as ArtifactType)) {
    throw new Error(
      `Invalid artifact type: "${value}". Must be one of: ${ARTIFACT_TYPES.join(', ')}`,
    );
  }
}
