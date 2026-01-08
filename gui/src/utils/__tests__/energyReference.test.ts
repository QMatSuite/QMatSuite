/**
 * Unit tests for energy reference inference.
 */
import { describe, it, expect } from 'vitest';
import { inferEnergyReference } from '../energyReference';

describe('inferEnergyReference', () => {
  it('should return "unknown" for (min=-6.2, max=-1.1, Ef=5.27)', () => {
    // lead.bxsf band 1 case: values are negative, 0 not in range, Ef not in range
    // This band does NOT cross Fermi, so should use mid-range as iso
    const result = inferEnergyReference(-6.2, -1.1, 5.27);
    expect(result.reference).toBe('unknown');
    expect(result.effective_iso_default).toBeCloseTo((-6.2 + -1.1) / 2, 2);
    expect(result.iso_default_reason).toBe('C');
  });
  
  it('should return "absolute" for (min=0, max=10, Ef=5)', () => {
    // Case where Fermi is in the range
    const result = inferEnergyReference(0, 10, 5);
    expect(result.reference).toBe('absolute');
    expect(result.effective_iso_default).toBe(5);
    expect(result.iso_default_reason).toBe('A');
  });
  
  it('should return "absolute" for (min=1.16, max=12.65, Ef=5.27)', () => {
    // lead.bxsf band 2 case: Ef is in range
    const result = inferEnergyReference(1.1655, 12.6535, 5.2676);
    expect(result.reference).toBe('absolute');
    expect(result.effective_iso_default).toBe(5.2676);
    expect(result.iso_default_reason).toBe('A');
  });
  
  it('should return "unknown" for (min=-6, max=-1, Ef=undefined)', () => {
    const result = inferEnergyReference(-6, -1, undefined);
    expect(result.reference).toBe('unknown');
    expect(result.effective_iso_default).toBe(-3.5); // (min+max)/2
    expect(result.iso_default_reason).toBe('C');
  });
  
  it('should return "relative_to_fermi" when 0 in range and Ef is far', () => {
    // Values cross zero, Ef is far away
    const result = inferEnergyReference(-3, 2, 15);
    expect(result.reference).toBe('relative_to_fermi');
    expect(result.effective_iso_default).toBe(0);
    expect(result.iso_default_reason).toBe('B');
  });
  
  it('should return "absolute" when 0 in range but Ef is close', () => {
    // Values cross zero, but Ef is close to range (not far enough)
    const result = inferEnergyReference(-3, 2, 3);
    // Since Ef=3 is in range [-3,2]? No, it's > max, so rule A doesn't apply
    // Rule B: 0 is in range, but abs(3) = 3, and 2*range = 10, so 3 < 10, rule B doesn't apply
    // So should be C
    expect(result.reference).toBe('unknown');
    expect(result.iso_default_reason).toBe('C');
  });
  
  it('should handle boundary case: Ef = min', () => {
    const result = inferEnergyReference(5, 10, 5);
    expect(result.reference).toBe('absolute');
    expect(result.effective_iso_default).toBe(5);
    expect(result.iso_default_reason).toBe('A');
  });
  
  it('should handle boundary case: Ef = max', () => {
    const result = inferEnergyReference(5, 10, 10);
    expect(result.reference).toBe('absolute');
    expect(result.effective_iso_default).toBe(10);
    expect(result.iso_default_reason).toBe('A');
  });
});

