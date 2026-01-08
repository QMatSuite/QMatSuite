/**
 * Phase 0 contract validation tests.
 * 
 * These tests validate that the volume data contract is enforced correctly.
 */
import { describe, it, expect } from 'vitest';

/**
 * Validate volume contract: values.length must equal nx*ny*nz
 * This is the Phase 0 contract enforced in marchingCubes.ts
 */
function validateVolumeContract(
  valuesLen: number,
  dims: [number, number, number]
): void {
  const expected = dims[0] * dims[1] * dims[2];
  if (valuesLen !== expected) {
    throw new Error(
      `Phase 0 validation failed: values.length (${valuesLen}) != nx*ny*nz (${expected}) ` +
      `for dims=[${dims.join(',')}]`
    );
  }
}

describe('validateVolumeContract', () => {
  it('should throw for mismatch: 1000 vs [40,40,40]', () => {
    expect(() => {
      validateVolumeContract(1000, [40, 40, 40]);
    }).toThrow('Phase 0 validation failed');
  });
  
  it('should pass for match: 1000 vs [10,10,10]', () => {
    expect(() => {
      validateVolumeContract(1000, [10, 10, 10]);
    }).not.toThrow();
  });
  
  it('should pass for match: 64000 vs [40,40,40]', () => {
    expect(() => {
      validateVolumeContract(64000, [40, 40, 40]);
    }).not.toThrow();
  });
  
  it('should throw for mismatch: 64000 vs [10,10,10]', () => {
    expect(() => {
      validateVolumeContract(64000, [10, 10, 10]);
    }).toThrow('Phase 0 validation failed');
  });
  
  it('should handle edge cases: 1 vs [1,1,1]', () => {
    expect(() => {
      validateVolumeContract(1, [1, 1, 1]);
    }).not.toThrow();
  });
  
  it('should handle edge cases: 0 vs [0,0,0]', () => {
    expect(() => {
      validateVolumeContract(0, [0, 0, 0]);
    }).not.toThrow();
  });
});

