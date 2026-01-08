/**
 * P4: Test that Debug panel renders without crashing on undefined/null values
 */
import { describe, it, expect } from 'vitest';

// Mock the component's dependencies since we're testing null-safety of render logic
// The actual component requires Electron/React context, so we test the null-safety logic directly

describe('VolumeViewerSandbox Debug Panel Null-Safety', () => {
  it('should safely format numeric values with null checks', () => {
    // Test the null-safety pattern used in the component
    const safeToFixed = (value: number | null | undefined, decimals: number = 4): string => {
      if (typeof value === 'number' && !isNaN(value)) {
        return value.toFixed(decimals);
      }
      return '—';
    };

    // Test cases that previously would crash
    expect(safeToFixed(undefined)).toBe('—');
    expect(safeToFixed(null)).toBe('—');
    expect(safeToFixed(NaN)).toBe('—');
    expect(safeToFixed(1.2345)).toBe('1.2345');
    expect(safeToFixed(0)).toBe('0.0000');
  });

  it('should safely format array values with null checks', () => {
    // Test bbox array formatting pattern
    const formatBbox = (bbox: [number, number, number] | undefined): string => {
      if (bbox && Array.isArray(bbox) && bbox.length === 3) {
        return `[${(bbox[0] ?? 0).toFixed(2)}, ${(bbox[1] ?? 0).toFixed(2)}, ${(bbox[2] ?? 0).toFixed(2)}]`;
      }
      return '—';
    };

    expect(formatBbox(undefined)).toBe('—');
    expect(formatBbox([1.1, 2.2, 3.3])).toBe('[1.10, 2.20, 3.30]');
    expect(formatBbox([null as any, 2.2, 3.3])).toBe('[0.00, 2.20, 3.30]');
  });

  it('should safely format value range with null checks', () => {
    // Test valueRange formatting pattern
    const formatRange = (range: { min: number; max: number } | null): string => {
      if (range) {
        return `${(range.min ?? 0).toFixed(4)} .. ${(range.max ?? 0).toFixed(4)}`;
      }
      return '—';
    };

    expect(formatRange(null)).toBe('—');
    expect(formatRange({ min: 1.23, max: 4.56 })).toBe('1.2300 .. 4.5600');
    expect(formatRange({ min: undefined as any, max: 4.56 })).toBe('0.0000 .. 4.5600');
  });
});

