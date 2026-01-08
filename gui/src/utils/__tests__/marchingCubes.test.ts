/**
 * Phase 3: Synthetic sphere field test
 * 
 * This test validates that Marching Cubes algorithm works correctly
 * on a known synthetic field (sphere).
 */
import { describe, it, expect } from 'vitest';
import { generateIsosurface } from '../marchingCubes';
import type { VolumeStats } from '../marchingCubes';

describe('Marching Cubes - Synthetic Sphere Field', () => {
  it('should generate sphere isosurface from synthetic distance field', () => {
    // Create a synthetic scalar field: distance from center - radius
    // iso=0 should produce a sphere shell
    const dims: [number, number, number] = [32, 32, 32];
    const nx = dims[0];
    const ny = dims[1];
    const nz = dims[2];
    
    // Grid spans [-10, 10] in each dimension (20 Å total)
    const gridSize = 20.0;
    const origin: [number, number, number] = [-10, -10, -10];
    const gridVectors: [[number, number, number], [number, number, number], [number, number, number]] = [
      [gridSize, 0, 0],
      [0, gridSize, 0],
      [0, 0, gridSize],
    ];
    
    // Sphere center at origin of grid coordinate system
    const sphereCenter = [0, 0, 0]; // World coordinates
    const sphereRadius = 5.0;
    
    // Create scalar field: value = distance(center) - radius
    // iso=0 means: distance = radius (sphere surface)
    const values = new Float32Array(nx * ny * nz);
    
    for (let k = 0; k < nz; k++) {
      for (let j = 0; j < ny; j++) {
        for (let i = 0; i < nx; i++) {
          // Grid to world coordinates
          // For step vectors: a = v1/(nx-1), etc.
          const stepX = gridSize / (nx - 1);
          const stepY = gridSize / (ny - 1);
          const stepZ = gridSize / (nz - 1);
          
          const worldX = origin[0] + i * stepX;
          const worldY = origin[1] + j * stepY;
          const worldZ = origin[2] + k * stepZ;
          
          // Distance from sphere center
          const dx = worldX - sphereCenter[0];
          const dy = worldY - sphereCenter[1];
          const dz = worldZ - sphereCenter[2];
          const distance = Math.sqrt(dx * dx + dy * dy + dz * dz);
          
          // Scalar = distance - radius (iso=0 gives sphere at radius)
          // FORTRAN order: idx = i + nx*(j + ny*k)
          const idx = i + nx * (j + ny * k);
          values[idx] = distance - sphereRadius;
        }
      }
    }
    
    // Generate isosurface at iso=0 (should be sphere surface)
    const isovalue = 0.0;
    const stats: { current: VolumeStats } = { current: {} as VolumeStats };
    
    const result = generateIsosurface(
      values,
      dims,
      origin,
      gridVectors,
      'fortran_i_fastest',
      isovalue,
      stats
    );
    
    // Assertions
    expect(result.positions.length % 3).toBe(0);
    expect(result.normals.length).toBe(result.positions.length);
    expect(result.indices.length % 3).toBe(0);
    
    // Should have triangles
    const numTriangles = result.indices.length / 3;
    expect(numTriangles).toBeGreaterThan(0);
    
    // All positions should be finite
    for (let i = 0; i < result.positions.length; i++) {
      expect(Number.isFinite(result.positions[i])).toBe(true);
    }
    
    // All normals should be finite
    for (let i = 0; i < result.normals.length; i++) {
      expect(Number.isFinite(result.normals[i])).toBe(true);
    }
    
    // Bbox is calculated from grid corners, so it should be the full grid range
    if (stats.current.bboxMin && stats.current.bboxMax) {
      // Grid bbox should match grid span
      expect(stats.current.bboxMin[0]).toBeCloseTo(origin[0], 2);
      expect(stats.current.bboxMin[1]).toBeCloseTo(origin[1], 2);
      expect(stats.current.bboxMin[2]).toBeCloseTo(origin[2], 2);
      expect(stats.current.bboxMax[0]).toBeCloseTo(origin[0] + gridSize, 2);
      expect(stats.current.bboxMax[1]).toBeCloseTo(origin[1] + gridSize, 2);
      expect(stats.current.bboxMax[2]).toBeCloseTo(origin[2] + gridSize, 2);
      
      // Max extent should be gridSize
      if (stats.current.maxExtent !== undefined) {
        expect(stats.current.maxExtent).toBeCloseTo(gridSize, 2);
      }
    }
    
    // Check mesh vertex bbox separately (actual sphere surface should be in [-5,5])
    let meshMinX = Infinity, meshMinY = Infinity, meshMinZ = Infinity;
    let meshMaxX = -Infinity, meshMaxY = -Infinity, meshMaxZ = -Infinity;
    for (let i = 0; i < result.positions.length; i += 3) {
      meshMinX = Math.min(meshMinX, result.positions[i]);
      meshMaxX = Math.max(meshMaxX, result.positions[i]);
      meshMinY = Math.min(meshMinY, result.positions[i + 1]);
      meshMaxY = Math.max(meshMaxY, result.positions[i + 1]);
      meshMinZ = Math.min(meshMinZ, result.positions[i + 2]);
      meshMaxZ = Math.max(meshMaxZ, result.positions[i + 2]);
    }
    
    // Mesh vertices (sphere surface) should be roughly in [-5,5] range
    expect(Math.abs(meshMinX)).toBeLessThan(6);
    expect(Math.abs(meshMaxX)).toBeLessThan(6);
    expect(Math.abs(meshMinY)).toBeLessThan(6);
    expect(Math.abs(meshMaxY)).toBeLessThan(6);
    expect(Math.abs(meshMinZ)).toBeLessThan(6);
    expect(Math.abs(meshMaxZ)).toBeLessThan(6);
    
    // Stats should show iso crossing
    expect(stats.current.nLess).toBeGreaterThan(0);
    expect(stats.current.nGreater).toBeGreaterThan(0);
    expect(stats.current.nActiveCubes).toBeGreaterThan(0);
  });
});

