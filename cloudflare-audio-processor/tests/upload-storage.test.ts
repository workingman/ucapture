import { describe, it, expect, vi, beforeEach } from 'vitest';
import { storeArtifacts, type ParsedUpload } from '../src/handlers/upload.ts';
import type { Metadata } from '../src/utils/validation.ts';

/** Creates a mock R2 bucket that records put() calls. */
function createMockR2Bucket(): R2Bucket & { putCalls: Array<{ key: string; value: unknown }> } {
  const putCalls: Array<{ key: string; value: unknown }> = [];

  return {
    putCalls,
    put: vi.fn(async (key: string, value: unknown) => {
      putCalls.push({ key, value });
      return {} as R2Object;
    }),
    get: vi.fn(),
    head: vi.fn(),
    delete: vi.fn(),
    list: vi.fn(),
    createMultipartUpload: vi.fn(),
    resumeMultipartUpload: vi.fn(),
  } as unknown as R2Bucket & { putCalls: Array<{ key: string; value: unknown }> };
}

/** Creates a mock uploaded file. */
function createMockFile(name: string, content: string): {
  readonly name: string;
  readonly size: number;
  stream(): ReadableStream;
  text(): Promise<string>;
} {
  const encoder = new TextEncoder();
  const bytes = encoder.encode(content);
  return {
    name,
    size: bytes.length,
    stream: () => new ReadableStream({
      start(controller) {
        controller.enqueue(bytes);
        controller.close();
      },
    }),
    text: async () => content,
  };
}

/** Builds a valid metadata object for testing. */
function buildTestMetadata(options: { withNotes?: boolean; withImages?: boolean } = {}): Metadata {
  const base: Metadata = {
    recording: {
      started_at: '2026-02-22T14:30:00Z',
      ended_at: '2026-02-22T14:45:00Z',
      duration_seconds: 900,
      audio_format: 'aac',
      sample_rate: 44100,
      channels: 1,
      bitrate: 128000,
      file_size_bytes: 1024000,
    },
    device: {
      model: 'Pixel 7',
      os_version: 'Android 14',
      app_version: '1.0.0',
    },
  };

  if (options.withNotes) {
    base.notes = [
      { text: 'Meeting with client', created_at: '2026-02-22T14:35:00Z' },
    ];
  }

  if (options.withImages) {
    base.images = [
      { filename: 'whiteboard.jpg', captured_at: '2026-02-22T14:32:00Z', size_bytes: 500000 },
    ];
  }

  return base;
}

describe('storeArtifacts', () => {
  let bucket: ReturnType<typeof createMockR2Bucket>;

  beforeEach(() => {
    bucket = createMockR2Bucket();
  });

  it('stores audio and metadata to correct R2 paths', async () => {
    const parsed: ParsedUpload = {
      audio: createMockFile('recording.m4a', 'audio-data'),
      metadata: buildTestMetadata(),
      metadataText: JSON.stringify(buildTestMetadata()),
      images: [],
      priority: 'normal',
    };

    const result = await storeArtifacts(bucket, '107234567890', parsed);

    // Verify batch ID was generated from recording start time
    expect(result.batchId).toMatch(/^20260222-143000-GMT-/);

    // Verify audio path follows DR-safe convention
    expect(result.audioPath).toBe(`107234567890/${result.batchId}/raw-audio/recording.m4a`);

    // Verify metadata path
    expect(result.metadataPath).toBe(`107234567890/${result.batchId}/metadata/metadata.json`);

    // Verify R2 put was called for audio and metadata
    expect(bucket.putCalls).toHaveLength(2);
    expect(bucket.putCalls[0].key).toBe(result.audioPath);
    expect(bucket.putCalls[1].key).toBe(result.metadataPath);
  });

  it('stores images under correct R2 paths', async () => {
    const parsed: ParsedUpload = {
      audio: createMockFile('recording.m4a', 'audio-data'),
      metadata: buildTestMetadata({ withImages: true }),
      metadataText: JSON.stringify(buildTestMetadata({ withImages: true })),
      images: [
        createMockFile('whiteboard.jpg', 'image-data-1'),
        createMockFile('notes.png', 'image-data-2'),
      ],
      priority: 'normal',
    };

    const result = await storeArtifacts(bucket, '107234567890', parsed);

    expect(result.imagePaths).toHaveLength(2);
    expect(result.imagePaths[0]).toBe(`107234567890/${result.batchId}/images/0-whiteboard.jpg`);
    expect(result.imagePaths[1]).toBe(`107234567890/${result.batchId}/images/1-notes.png`);

    // audio + metadata + 2 images = 4 puts
    expect(bucket.putCalls).toHaveLength(4);
  });

  it('stores notes.json when metadata contains notes', async () => {
    const parsed: ParsedUpload = {
      audio: createMockFile('recording.m4a', 'audio-data'),
      metadata: buildTestMetadata({ withNotes: true }),
      metadataText: JSON.stringify(buildTestMetadata({ withNotes: true })),
      images: [],
      priority: 'normal',
    };

    const result = await storeArtifacts(bucket, '107234567890', parsed);

    expect(result.notesPath).toBe(`107234567890/${result.batchId}/notes/notes.json`);

    // audio + metadata + notes = 3 puts
    expect(bucket.putCalls).toHaveLength(3);
    expect(bucket.putCalls[2].key).toBe(result.notesPath);
  });

  it('uses user_id from parameter (not from request body)', async () => {
    const parsed: ParsedUpload = {
      audio: createMockFile('recording.m4a', 'audio-data'),
      metadata: buildTestMetadata(),
      metadataText: JSON.stringify(buildTestMetadata()),
      images: [],
      priority: 'normal',
    };

    const authUserId = 'auth-user-99999';
    const result = await storeArtifacts(bucket, authUserId, parsed);

    // All paths should start with the auth user ID
    expect(result.audioPath).toMatch(new RegExp(`^${authUserId}/`));
    expect(result.metadataPath).toMatch(new RegExp(`^${authUserId}/`));
  });
});
