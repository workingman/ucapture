/**
 * POST /v1/upload handler for multipart audio batch uploads.
 *
 * Parses multipart form data, validates all fields, stores artifacts in R2,
 * creates D1 batch record, and enqueues processing job.
 */

import type { Context } from 'hono';
import type { Env } from '../env.d.ts';
import { MetadataSchema, type Metadata } from '../utils/validation.ts';
import { ValidationError } from '../utils/errors.ts';
import type { BatchPriority } from '../types/batch.ts';
import { generateBatchId } from '../utils/batch-id.ts';
import {
  buildAudioPath,
  buildMetadataPath,
  buildImagePath,
  buildNotesPath,
} from '../storage/r2.ts';

/** Maximum audio file size: 50 MB. */
const MAX_AUDIO_SIZE_BYTES = 50 * 1024 * 1024;

/** Maximum image file size: 5 MB. */
const MAX_IMAGE_SIZE_BYTES = 5 * 1024 * 1024;

/** Maximum number of images per upload. */
const MAX_IMAGE_COUNT = 10;

/** Maximum total payload size: 100 MB. */
export const MAX_TOTAL_PAYLOAD_BYTES = 100 * 1024 * 1024;

/** Allowed audio file extensions. */
const ALLOWED_AUDIO_EXTENSIONS = ['.m4a'];

/** Allowed image file extensions. */
const ALLOWED_IMAGE_EXTENSIONS = ['.jpg', '.jpeg', '.png'];

/** Valid priority values. */
const VALID_PRIORITIES: BatchPriority[] = ['immediate', 'normal'];

/**
 * File-like interface for multipart form data entries.
 * Cloudflare Workers types define FormData.get() as string, but at runtime
 * file uploads arrive as File objects with name, size, stream(), and text().
 */
interface UploadedFile {
  readonly name: string;
  readonly size: number;
  stream(): ReadableStream;
  text(): Promise<string>;
}

/** Parsed and validated upload data returned by parseUpload. */
export interface ParsedUpload {
  readonly audio: UploadedFile;
  readonly metadata: Metadata;
  readonly metadataText: string;
  readonly images: UploadedFile[];
  readonly priority: BatchPriority;
}

/**
 * Parses and validates a multipart upload request.
 *
 * @param c - Hono context with Env bindings
 * @returns Parsed and validated upload data
 * @throws ValidationError on invalid input
 */
export async function parseUpload(
  c: Context<{ Bindings: Env; Variables: { user_id: string; email: string } }>,
): Promise<ParsedUpload> {
  // Check Content-Length for early rejection
  const contentLength = c.req.header('Content-Length');
  if (contentLength && parseInt(contentLength, 10) > MAX_TOTAL_PAYLOAD_BYTES) {
    throw new ValidationError('Total payload exceeds 100MB limit');
  }

  let formData: FormData;
  try {
    formData = await c.req.formData();
  } catch {
    throw new ValidationError('Invalid multipart form data');
  }

  const audio = validateAudio(formData);
  const { metadata, metadataText } = await validateMetadata(formData);
  const images = validateImages(formData);
  const priority = validatePriority(formData);

  return { audio, metadata, metadataText, images, priority };
}

/** Type guard: checks if a FormData entry is a file (has name and size). */
function isFile(entry: unknown): entry is UploadedFile {
  return (
    typeof entry === 'object' &&
    entry !== null &&
    'name' in entry &&
    'size' in entry &&
    'stream' in entry
  );
}

/**
 * Validates the required audio file field.
 *
 * @param formData - Parsed form data
 * @returns Validated audio file
 * @throws ValidationError if audio is missing, wrong type, or too large
 */
function validateAudio(formData: FormData): UploadedFile {
  const audio = formData.get('audio') as unknown;

  if (!audio || !isFile(audio)) {
    throw new ValidationError('Missing required field: audio');
  }

  const extension = getFileExtension(audio.name);
  if (!ALLOWED_AUDIO_EXTENSIONS.includes(extension)) {
    throw new ValidationError(
      `Invalid audio format: "${extension}". Allowed: ${ALLOWED_AUDIO_EXTENSIONS.join(', ')}`,
    );
  }

  if (audio.size > MAX_AUDIO_SIZE_BYTES) {
    throw new ValidationError('Audio file exceeds 50MB limit');
  }

  return audio;
}

/**
 * Validates the required metadata JSON file field.
 *
 * @param formData - Parsed form data
 * @returns Validated metadata object and raw text
 * @throws ValidationError if metadata is missing or invalid
 */
async function validateMetadata(
  formData: FormData,
): Promise<{ metadata: Metadata; metadataText: string }> {
  const metadataField = formData.get('metadata') as unknown;

  if (!metadataField || !isFile(metadataField)) {
    throw new ValidationError('Missing required field: metadata');
  }

  const metadataText = await metadataField.text();

  let parsed: unknown;
  try {
    parsed = JSON.parse(metadataText);
  } catch {
    throw new ValidationError('Invalid metadata: not valid JSON');
  }

  const result = MetadataSchema.safeParse(parsed);

  if (!result.success) {
    const details = result.error.issues
      .map((issue) => `${issue.path.join('.')}: ${issue.message}`)
      .join('; ');
    throw new ValidationError('Invalid metadata', details);
  }

  return { metadata: result.data, metadataText };
}

/**
 * Validates optional image file fields.
 *
 * @param formData - Parsed form data
 * @returns Array of validated image files
 * @throws ValidationError if too many images or wrong type/size
 */
function validateImages(formData: FormData): UploadedFile[] {
  const imageEntries = formData.getAll('images') as unknown[];
  const images = imageEntries.filter(isFile);

  if (images.length > MAX_IMAGE_COUNT) {
    throw new ValidationError(
      `Too many images: ${images.length}. Maximum: ${MAX_IMAGE_COUNT}`,
    );
  }

  for (const image of images) {
    const extension = getFileExtension(image.name);
    if (!ALLOWED_IMAGE_EXTENSIONS.includes(extension)) {
      throw new ValidationError(
        `Invalid image format for "${image.name}": "${extension}". Allowed: ${ALLOWED_IMAGE_EXTENSIONS.join(', ')}`,
      );
    }

    if (image.size > MAX_IMAGE_SIZE_BYTES) {
      throw new ValidationError(
        `Image "${image.name}" exceeds 5MB limit`,
      );
    }
  }

  return images;
}

/**
 * Validates the optional priority field.
 *
 * @param formData - Parsed form data
 * @returns Validated priority (defaults to "normal")
 * @throws ValidationError if priority value is invalid
 */
function validatePriority(formData: FormData): BatchPriority {
  const priorityField = formData.get('priority');

  if (!priorityField) {
    return 'normal';
  }

  const priority = String(priorityField);

  if (!VALID_PRIORITIES.includes(priority as BatchPriority)) {
    throw new ValidationError(
      `Invalid priority: "${priority}". Allowed: ${VALID_PRIORITIES.join(', ')}`,
    );
  }

  return priority as BatchPriority;
}

/** Extracts the lowercase file extension from a filename. */
function getFileExtension(filename: string): string {
  const lastDot = filename.lastIndexOf('.');
  if (lastDot === -1) return '';
  return filename.slice(lastDot).toLowerCase();
}

/** R2 paths for all stored artifacts. */
export interface StoredArtifacts {
  readonly batchId: string;
  readonly audioPath: string;
  readonly metadataPath: string;
  readonly imagePaths: string[];
  readonly notesPath: string | null;
}

/**
 * Stores all upload artifacts to R2 and returns the paths.
 *
 * Audio is streamed via ReadableStream to avoid buffering.
 * Metadata and notes are stored as text.
 *
 * @param bucket - R2 bucket binding
 * @param userId - Authenticated user's Google sub claim
 * @param parsed - Validated upload data from parseUpload
 * @returns Paths of all stored artifacts and the generated batch ID
 */
export async function storeArtifacts(
  bucket: R2Bucket,
  userId: string,
  parsed: ParsedUpload,
): Promise<StoredArtifacts> {
  const batchId = generateBatchId(parsed.metadata.recording.started_at);

  // Stream audio to R2 (avoids buffering large files)
  const audioPath = buildAudioPath(userId, batchId);
  await bucket.put(audioPath, parsed.audio.stream());

  // Store metadata JSON as text
  const metadataPath = buildMetadataPath(userId, batchId);
  await bucket.put(metadataPath, parsed.metadataText);

  // Store images
  const imagePaths: string[] = [];
  for (let i = 0; i < parsed.images.length; i++) {
    const image = parsed.images[i];
    const imagePath = buildImagePath(userId, batchId, i, image.name);
    await bucket.put(imagePath, image.stream());
    imagePaths.push(imagePath);
  }

  // Store notes as separate JSON if present in metadata
  let notesPath: string | null = null;
  if (parsed.metadata.notes && parsed.metadata.notes.length > 0) {
    notesPath = buildNotesPath(userId, batchId);
    await bucket.put(notesPath, JSON.stringify(parsed.metadata.notes));
  }

  return { batchId, audioPath, metadataPath, imagePaths, notesPath };
}
