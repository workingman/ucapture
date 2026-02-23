import { describe, it, expect } from 'vitest';
import { MetadataSchema } from '../src/utils/validation.ts';

/** Complete metadata fixture with all optional sections. */
const FULL_METADATA = {
  recording: {
    started_at: '2026-02-22T14:30:27Z',
    ended_at: '2026-02-22T15:00:00Z',
    duration_seconds: 1773,
    audio_format: 'm4a',
    sample_rate: 44100,
    channels: 1,
    bitrate: 128000,
    file_size_bytes: 5242880,
  },
  location: {
    latitude: 49.2827,
    longitude: -123.1207,
    accuracy_meters: 10,
    captured_at: '2026-02-22T14:30:27Z',
    address: '123 Main St, Vancouver, BC',
  },
  calendar: {
    event_id: 'cal-event-123',
    event_title: 'Team Standup',
    attendees: ['alice@example.com', 'bob@example.com'],
  },
  images: [
    { filename: 'whiteboard.jpg', captured_at: '2026-02-22T14:35:00Z', size_bytes: 204800 },
  ],
  notes: [
    { text: 'Action item: follow up with design team', created_at: '2026-02-22T14:40:00Z' },
  ],
  device: {
    model: 'Pixel 8 Pro',
    os_version: 'Android 15',
    app_version: '1.0.0',
  },
};

/** Minimal valid metadata with only required sections. */
const MINIMAL_METADATA = {
  recording: {
    started_at: '2026-02-22T14:30:27Z',
    ended_at: '2026-02-22T15:00:00Z',
    duration_seconds: 1773,
    audio_format: 'm4a',
    sample_rate: 44100,
    channels: 1,
    bitrate: 128000,
    file_size_bytes: 5242880,
  },
  device: {
    model: 'Pixel 8 Pro',
    os_version: 'Android 15',
    app_version: '1.0.0',
  },
};

describe('MetadataSchema', () => {
  it('parses complete metadata with all optional sections', () => {
    const result = MetadataSchema.safeParse(FULL_METADATA);
    expect(result.success).toBe(true);
    if (result.success) {
      expect(result.data.recording.started_at).toBe('2026-02-22T14:30:27Z');
      expect(result.data.location?.latitude).toBe(49.2827);
      expect(result.data.calendar?.event_title).toBe('Team Standup');
      expect(result.data.images).toHaveLength(1);
      expect(result.data.notes).toHaveLength(1);
      expect(result.data.device.model).toBe('Pixel 8 Pro');
    }
  });

  it('parses minimal metadata with only recording + device', () => {
    const result = MetadataSchema.safeParse(MINIMAL_METADATA);
    expect(result.success).toBe(true);
    if (result.success) {
      expect(result.data.location).toBeUndefined();
      expect(result.data.calendar).toBeUndefined();
      expect(result.data.images).toBeUndefined();
      expect(result.data.notes).toBeUndefined();
    }
  });

  it('rejects missing recording.started_at', () => {
    const invalid = {
      ...MINIMAL_METADATA,
      recording: { ...MINIMAL_METADATA.recording, started_at: undefined },
    };
    const result = MetadataSchema.safeParse(invalid);
    expect(result.success).toBe(false);
  });

  it('rejects missing device section entirely', () => {
    const { device: _, ...noDevice } = MINIMAL_METADATA;
    const result = MetadataSchema.safeParse(noDevice);
    expect(result.success).toBe(false);
  });

  it('rejects negative duration_seconds', () => {
    const invalid = {
      ...MINIMAL_METADATA,
      recording: { ...MINIMAL_METADATA.recording, duration_seconds: -1 },
    };
    const result = MetadataSchema.safeParse(invalid);
    expect(result.success).toBe(false);
    if (!result.success) {
      const durationError = result.error.issues.find(
        (issue) => issue.path.includes('duration_seconds'),
      );
      expect(durationError).toBeDefined();
    }
  });

  it('rejects invalid ISO date in recording.started_at', () => {
    const invalid = {
      ...MINIMAL_METADATA,
      recording: { ...MINIMAL_METADATA.recording, started_at: 'not-a-date' },
    };
    const result = MetadataSchema.safeParse(invalid);
    expect(result.success).toBe(false);
  });
});
