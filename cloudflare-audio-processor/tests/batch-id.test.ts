import { describe, it, expect } from 'vitest';
import { generateBatchId, parseBatchId } from '../src/utils/batch-id.ts';

describe('generateBatchId', () => {
  it('produces correct format from UTC ISO string', () => {
    const id = generateBatchId('2026-02-22T14:30:27Z');
    expect(id).toMatch(/^20260222-143027-GMT-[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/);
  });

  it('normalizes timezone offsets to GMT', () => {
    // PST is UTC-8, so 06:30:27-08:00 => 14:30:27 UTC
    const id = generateBatchId('2026-02-22T06:30:27-08:00');
    expect(id).toMatch(/^20260222-143027-GMT-/);
  });

  it('produces unique IDs for the same input (UUID uniqueness)', () => {
    const id1 = generateBatchId('2026-02-22T14:30:27Z');
    const id2 = generateBatchId('2026-02-22T14:30:27Z');
    expect(id1).not.toBe(id2);
    // Timestamps match, UUIDs differ
    expect(id1.slice(0, 20)).toBe(id2.slice(0, 20));
  });

  it('throws descriptive error for invalid date string', () => {
    expect(() => generateBatchId('not-a-date')).toThrow('Invalid ISO 8601 date: "not-a-date"');
  });

  it('throws descriptive error for empty string', () => {
    expect(() => generateBatchId('')).toThrow('recordingStartedAt is required');
  });
});

describe('parseBatchId', () => {
  it('round-trips with generateBatchId', () => {
    const iso = '2026-02-22T14:30:27Z';
    const id = generateBatchId(iso);
    const parsed = parseBatchId(id);

    expect(parsed.recordingStartedAt.toISOString()).toBe('2026-02-22T14:30:27.000Z');
    expect(parsed.uuid).toMatch(/^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/);
  });

  it('throws for invalid batch ID format', () => {
    expect(() => parseBatchId('invalid-format')).toThrow('Invalid batch ID format');
  });

  it('throws for empty batch ID', () => {
    expect(() => parseBatchId('')).toThrow('batchId is required');
  });
});
