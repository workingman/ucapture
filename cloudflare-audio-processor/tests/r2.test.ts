import { describe, it, expect } from 'vitest';
import { buildR2Path, parseR2Path, ARTIFACT_TYPES } from '../src/storage/r2.ts';
import type { ArtifactType } from '../src/storage/r2.ts';

describe('buildR2Path', () => {
  it('constructs correct path for all 6 artifact types', () => {
    const types: ArtifactType[] = ['raw-audio', 'metadata', 'images', 'notes', 'cleaned-audio', 'transcript'];
    for (const type of types) {
      const path = buildR2Path('user123', 'batch456', type, 'file.ext');
      expect(path).toBe(`user123/batch456/${type}/file.ext`);
    }
    expect(types.length).toBe(ARTIFACT_TYPES.length);
  });

  it('rejects path traversal in userId', () => {
    expect(() => buildR2Path('../etc', 'batch', 'raw-audio', 'file.m4a'))
      .toThrow('Path traversal detected');
  });

  it('rejects empty segments', () => {
    expect(() => buildR2Path('', 'batch', 'raw-audio', 'file.m4a'))
      .toThrow('userId must not be empty');
    expect(() => buildR2Path('user', '', 'raw-audio', 'file.m4a'))
      .toThrow('batchId must not be empty');
    expect(() => buildR2Path('user', 'batch', 'raw-audio', ''))
      .toThrow('filename must not be empty');
  });

  it('rejects invalid artifact type', () => {
    expect(() => buildR2Path('user', 'batch', 'invalid-type' as ArtifactType, 'file.m4a'))
      .toThrow('Invalid artifact type: "invalid-type"');
  });
});

describe('parseR2Path', () => {
  it('round-trips with buildR2Path', () => {
    const original = { userId: 'user123', batchId: 'batch456', artifactType: 'raw-audio' as const, filename: 'recording.m4a' };
    const path = buildR2Path(original.userId, original.batchId, original.artifactType, original.filename);
    const parsed = parseR2Path(path);
    expect(parsed).toEqual(original);
  });

  it('rejects path traversal attempts', () => {
    expect(() => parseR2Path('user/../admin/batch/raw-audio/file.m4a'))
      .toThrow('Path traversal detected');
  });

  it('rejects insufficient segments', () => {
    expect(() => parseR2Path('user/batch'))
      .toThrow('Insufficient path segments');
  });

  it('rejects invalid artifact type in path', () => {
    expect(() => parseR2Path('user/batch/not-a-type/file.m4a'))
      .toThrow('Invalid artifact type');
  });
});
