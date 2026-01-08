import { describe, it, expect } from 'vitest';
import { gridToWorld, calculateBBox } from '../volumeCoordinates';
import type { VolumeMetadata } from '../volumeCoordinates';

describe('gridToWorld', () => {
  it('should map grid (0,0,0) to origin for nx=3', () => {
    const meta: VolumeMetadata = {
      grid_shape: [3, 3, 3],
      origin_cart: [0, 0, 0],
      grid_vectors_cart: [
        [10, 0, 0],  // v1: 10 Å in x
        [0, 10, 0],  // v2: 10 Å in y
        [0, 0, 10],  // v3: 10 Å in z
      ],
    };
    
    const [x, y, z] = gridToWorld(0, 0, 0, meta);
    expect(x).toBeCloseTo(0, 6);
    expect(y).toBeCloseTo(0, 6);
    expect(z).toBeCloseTo(0, 6);
  });
  
  it('should map grid (nx-1,0,0) to origin+v1 for nx=3', () => {
    const meta: VolumeMetadata = {
      grid_shape: [3, 3, 3],
      origin_cart: [0, 0, 0],
      grid_vectors_cart: [
        [10, 0, 0],  // v1: 10 Å
        [0, 10, 0],
        [0, 0, 10],
      ],
    };
    
    // i = nx-1 = 2, should map to origin + v1 = [10, 0, 0]
    const [x, y, z] = gridToWorld(2, 0, 0, meta);
    expect(x).toBeCloseTo(10, 6);
    expect(y).toBeCloseTo(0, 6);
    expect(z).toBeCloseTo(0, 6);
  });
  
  it('should map grid midpoint correctly', () => {
    const meta: VolumeMetadata = {
      grid_shape: [3, 3, 3],
      origin_cart: [0, 0, 0],
      grid_vectors_cart: [
        [10, 0, 0],
        [0, 10, 0],
        [0, 0, 10],
      ],
    };
    
    // i=1 (midpoint), should map to origin + 0.5*v1 = [5, 0, 0]
    const [x, y, z] = gridToWorld(1, 0, 0, meta);
    expect(x).toBeCloseTo(5, 6);
    expect(y).toBeCloseTo(0, 6);
    expect(z).toBeCloseTo(0, 6);
  });
  
  it('should handle non-zero origin', () => {
    const meta: VolumeMetadata = {
      grid_shape: [2, 2, 2],
      origin_cart: [5, 10, 15],
      grid_vectors_cart: [
        [10, 0, 0],
        [0, 10, 0],
        [0, 0, 10],
      ],
    };
    
    const [x, y, z] = gridToWorld(0, 0, 0, meta);
    expect(x).toBeCloseTo(5, 6);
    expect(y).toBeCloseTo(10, 6);
    expect(z).toBeCloseTo(15, 6);
    
    // (1,1,1) should map to origin + v1 + v2 + v3
    const [x2, y2, z2] = gridToWorld(1, 1, 1, meta);
    expect(x2).toBeCloseTo(15, 6); // 5 + 10
    expect(y2).toBeCloseTo(20, 6); // 10 + 10
    expect(z2).toBeCloseTo(25, 6); // 15 + 10
  });
});

describe('calculateBBox', () => {
  it('should calculate correct bbox for simple cubic grid', () => {
    const meta: VolumeMetadata = {
      grid_shape: [3, 3, 3],
      origin_cart: [0, 0, 0],
      grid_vectors_cart: [
        [10, 0, 0],
        [0, 10, 0],
        [0, 0, 10],
      ],
    };
    
    const bbox = calculateBBox(meta);
    
    expect(bbox.bboxMin[0]).toBeCloseTo(0, 6);
    expect(bbox.bboxMin[1]).toBeCloseTo(0, 6);
    expect(bbox.bboxMin[2]).toBeCloseTo(0, 6);
    
    expect(bbox.bboxMax[0]).toBeCloseTo(10, 6);
    expect(bbox.bboxMax[1]).toBeCloseTo(10, 6);
    expect(bbox.bboxMax[2]).toBeCloseTo(10, 6);
    
    expect(bbox.center[0]).toBeCloseTo(5, 6);
    expect(bbox.center[1]).toBeCloseTo(5, 6);
    expect(bbox.center[2]).toBeCloseTo(5, 6);
    
    expect(bbox.maxExtent).toBeCloseTo(10, 6);
  });
  
  it('should handle non-zero origin and non-orthogonal vectors', () => {
    const meta: VolumeMetadata = {
      grid_shape: [2, 2, 2],
      origin_cart: [1, 2, 3],
      grid_vectors_cart: [
        [5, 1, 0],   // v1 not aligned with x-axis
        [0, 5, 1],   // v2 not aligned with y-axis
        [1, 0, 5],   // v3 not aligned with z-axis
      ],
    };
    
    const bbox = calculateBBox(meta);
    
    // Bbox should encompass all 8 corners
    // Corner (0,0,0) = origin = [1, 2, 3]
    // Corner (1,1,1) = origin + v1 + v2 + v3 = [1+5+0+1, 2+1+5+0, 3+0+1+5] = [7, 8, 9]
    expect(bbox.bboxMin[0]).toBeLessThanOrEqual(1);
    expect(bbox.bboxMin[1]).toBeLessThanOrEqual(2);
    expect(bbox.bboxMin[2]).toBeLessThanOrEqual(3);
    
    expect(bbox.bboxMax[0]).toBeGreaterThanOrEqual(7);
    expect(bbox.bboxMax[1]).toBeGreaterThanOrEqual(8);
    expect(bbox.bboxMax[2]).toBeGreaterThanOrEqual(9);
    
    // Center should be midpoint
    expect(bbox.center[0]).toBeCloseTo((bbox.bboxMin[0] + bbox.bboxMax[0]) / 2, 6);
    expect(bbox.center[1]).toBeCloseTo((bbox.bboxMin[1] + bbox.bboxMax[1]) / 2, 6);
    expect(bbox.center[2]).toBeCloseTo((bbox.bboxMin[2] + bbox.bboxMax[2]) / 2, 6);
  });
});

