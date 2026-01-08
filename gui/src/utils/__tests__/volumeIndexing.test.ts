import { describe, it, expect } from 'vitest';
import { flatIndex, getValue } from '../volumeIndexing';

describe('flatIndex', () => {
  describe('FORTRAN order (i-fastest)', () => {
    it('should compute correct indices for small 3D array', () => {
      const dims: [number, number, number] = [2, 3, 4];
      
      // For FORTRAN: idx = i + nx*(j + ny*k)
      // Test (0,0,0): 0 + 2*(0 + 3*0) = 0
      expect(flatIndex(0, 0, 0, dims, 'fortran_i_fastest')).toBe(0);
      
      // Test (1,0,0): 1 + 2*(0 + 3*0) = 1
      expect(flatIndex(1, 0, 0, dims, 'fortran_i_fastest')).toBe(1);
      
      // Test (0,1,0): 0 + 2*(1 + 3*0) = 2
      expect(flatIndex(0, 1, 0, dims, 'fortran_i_fastest')).toBe(2);
      
      // Test (1,1,0): 1 + 2*(1 + 3*0) = 3
      expect(flatIndex(1, 1, 0, dims, 'fortran_i_fastest')).toBe(3);
      
      // Test (0,0,1): 0 + 2*(0 + 3*1) = 6
      expect(flatIndex(0, 0, 1, dims, 'fortran_i_fastest')).toBe(6);
      
      // Test (1,2,3): 1 + 2*(2 + 3*3) = 1 + 2*11 = 23
      expect(flatIndex(1, 2, 3, dims, 'fortran_i_fastest')).toBe(23);
    });
    
    it('should cover all indices in sequence', () => {
      const dims: [number, number, number] = [2, 3, 4];
      const total = dims[0] * dims[1] * dims[2]; // 24
      
      const indices = new Set<number>();
      for (let k = 0; k < dims[2]; k++) {
        for (let j = 0; j < dims[1]; j++) {
          for (let i = 0; i < dims[0]; i++) {
            const idx = flatIndex(i, j, k, dims, 'fortran_i_fastest');
            expect(idx).toBeGreaterThanOrEqual(0);
            expect(idx).toBeLessThan(total);
            indices.add(idx);
          }
        }
      }
      
      // All 24 indices should be unique
      expect(indices.size).toBe(total);
    });
  });
  
  describe('C order (k-fastest)', () => {
    it('should compute correct indices for small 3D array', () => {
      const dims: [number, number, number] = [2, 3, 4];
      
      // For C: idx = k + nz*(j + ny*i)
      // Test (0,0,0): 0 + 4*(0 + 3*0) = 0
      expect(flatIndex(0, 0, 0, dims, 'c_k_fastest')).toBe(0);
      
      // Test (0,0,1): 1 + 4*(0 + 3*0) = 1
      expect(flatIndex(0, 0, 1, dims, 'c_k_fastest')).toBe(1);
      
      // Test (0,0,3): 3 + 4*(0 + 3*0) = 3
      expect(flatIndex(0, 0, 3, dims, 'c_k_fastest')).toBe(3);
      
      // Test (0,1,0): 0 + 4*(1 + 3*0) = 4
      expect(flatIndex(0, 1, 0, dims, 'c_k_fastest')).toBe(4);
      
      // Test (1,2,3): 3 + 4*(2 + 3*1) = 3 + 4*5 = 23
      expect(flatIndex(1, 2, 3, dims, 'c_k_fastest')).toBe(23);
    });
    
    it('should cover all indices in sequence', () => {
      const dims: [number, number, number] = [2, 3, 4];
      const total = dims[0] * dims[1] * dims[2]; // 24
      
      const indices = new Set<number>();
      for (let i = 0; i < dims[0]; i++) {
        for (let j = 0; j < dims[1]; j++) {
          for (let k = 0; k < dims[2]; k++) {
            const idx = flatIndex(i, j, k, dims, 'c_k_fastest');
            expect(idx).toBeGreaterThanOrEqual(0);
            expect(idx).toBeLessThan(total);
            indices.add(idx);
          }
        }
      }
      
      // All 24 indices should be unique
      expect(indices.size).toBe(total);
    });
  });
  
  it('should throw on invalid data_order', () => {
    const dims: [number, number, number] = [2, 3, 4];
    expect(() => {
      flatIndex(0, 0, 0, dims, 'invalid' as any);
    }).toThrow("Invalid data_order");
  });
});

describe('getValue', () => {
  it('should retrieve correct values for FORTRAN order', () => {
    const dims: [number, number, number] = [2, 3, 4];
    // Create array [0, 1, 2, ..., 23]
    const values = new Float32Array(Array.from({ length: 24 }, (_, i) => i));
    
    // (0,0,0) should map to index 0
    expect(getValue(0, 0, 0, dims, 'fortran_i_fastest', values)).toBe(0);
    
    // (1,0,0) should map to index 1
    expect(getValue(1, 0, 0, dims, 'fortran_i_fastest', values)).toBe(1);
    
    // (0,1,0) should map to index 2
    expect(getValue(0, 1, 0, dims, 'fortran_i_fastest', values)).toBe(2);
    
    // (1,2,3) should map to index 23
    expect(getValue(1, 2, 3, dims, 'fortran_i_fastest', values)).toBe(23);
  });
  
  it('should retrieve correct values for C order', () => {
    const dims: [number, number, number] = [2, 3, 4];
    // Create array [0, 1, 2, ..., 23]
    const values = new Float32Array(Array.from({ length: 24 }, (_, i) => i));
    
    // (0,0,0) should map to index 0
    expect(getValue(0, 0, 0, dims, 'c_k_fastest', values)).toBe(0);
    
    // (0,0,1) should map to index 1
    expect(getValue(0, 0, 1, dims, 'c_k_fastest', values)).toBe(1);
    
    // (0,1,0) should map to index 4
    expect(getValue(0, 1, 0, dims, 'c_k_fastest', values)).toBe(4);
    
    // (1,2,3) should map to index 23
    expect(getValue(1, 2, 3, dims, 'c_k_fastest', values)).toBe(23);
  });
  
  it('should throw on out of bounds', () => {
    const dims: [number, number, number] = [2, 3, 4];
    const values = new Float32Array(24);
    
    expect(() => {
      getValue(2, 0, 0, dims, 'fortran_i_fastest', values); // i >= nx
    }).toThrow('out of bounds');
    
    expect(() => {
      getValue(0, 3, 0, dims, 'fortran_i_fastest', values); // j >= ny
    }).toThrow('out of bounds');
    
    expect(() => {
      getValue(0, 0, 4, dims, 'fortran_i_fastest', values); // k >= nz
    }).toThrow('out of bounds');
    
    expect(() => {
      getValue(-1, 0, 0, dims, 'fortran_i_fastest', values); // i < 0
    }).toThrow('out of bounds');
  });
});

