/**
 * Marching Cubes - MVP Implementation
 * 
 * Generates triangle mesh from volumetric data at a given isovalue.
 * 
 * Assumptions (MVP):
 * - Regular Cartesian grid (grid_vectors近似正交)
 * - 支持 FORTRAN (i-fastest) 和 C (k-fastest) data order
 * 
 * TODO (future):
 * - 非正交grid_vectors支持
 * - Vertex deduplication
 * - Normal smoothing
 */

import * as THREE from 'three';

// Marching Cubes lookup tables (classic MC33 simplified)
// Edge table: which edges are intersected for each cube configuration
const EDGE_TABLE = new Uint16Array([
  0x0, 0x109, 0x203, 0x30a, 0x406, 0x50f, 0x605, 0x70c,
  0x80c, 0x905, 0xa0f, 0xb06, 0xc0a, 0xd03, 0xe09, 0xf00,
  0x190, 0x99, 0x393, 0x29a, 0x596, 0x49f, 0x795, 0x69c,
  0x99c, 0x895, 0xb9f, 0xa96, 0xd9a, 0xc93, 0xf99, 0xe90,
  0x230, 0x339, 0x33, 0x13a, 0x636, 0x73f, 0x435, 0x53c,
  0xa3c, 0xb35, 0x83f, 0x936, 0xe3a, 0xf33, 0xc39, 0xd30,
  0x3a0, 0x2a9, 0x1a3, 0xaa, 0x7a6, 0x6af, 0x5a5, 0x4ac,
  0xbac, 0xaa5, 0x9af, 0x8a6, 0xfaa, 0xea3, 0xda9, 0xca0,
  0x460, 0x569, 0x663, 0x76a, 0x66, 0x16f, 0x265, 0x36c,
  0xc6c, 0xd65, 0xe6f, 0xf66, 0x86a, 0x963, 0xa69, 0xb60,
  0x5f0, 0x4f9, 0x7f3, 0x6fa, 0x1f6, 0xff, 0x3f5, 0x2fc,
  0xdfc, 0xcf5, 0xfff, 0xef6, 0x9fa, 0x8f3, 0xbf9, 0xaf0,
  0x650, 0x759, 0x453, 0x55a, 0x256, 0x35f, 0x55, 0x15c,
  0xe5c, 0xf55, 0xc5f, 0xd56, 0xa5a, 0xb53, 0x859, 0x950,
  0x7c0, 0x6c9, 0x5c3, 0x4ca, 0x3c6, 0x2cf, 0x1c5, 0xcc,
  0xfcc, 0xec5, 0xdcf, 0xcc6, 0xbca, 0xac3, 0x9c9, 0x8c0,
  0x8c0, 0x9c9, 0xac3, 0xbca, 0xcc6, 0xdcf, 0xec5, 0xfcc,
  0xcc, 0x1c5, 0x2cf, 0x3c6, 0x4ca, 0x5c3, 0x6c9, 0x7c0,
  0x950, 0x859, 0xb53, 0xa5a, 0xd56, 0xc5f, 0xf55, 0xe5c,
  0x15c, 0x55, 0x35f, 0x256, 0x55a, 0x453, 0x759, 0x650,
  0xaf0, 0xbf9, 0x8f3, 0x9fa, 0xef6, 0xfff, 0xcf5, 0xdfc,
  0x2fc, 0x3f5, 0xff, 0x1f6, 0x6fa, 0x7f3, 0x4f9, 0x5f0,
  0xb60, 0xa69, 0x963, 0x86a, 0xf66, 0xe6f, 0xd65, 0xc6c,
  0x36c, 0x265, 0x16f, 0x66, 0x76a, 0x663, 0x569, 0x460,
  0xca0, 0xda9, 0xea3, 0xfaa, 0x8a6, 0x9af, 0xaa5, 0xbac,
  0x4ac, 0x5a5, 0x6af, 0x7a6, 0xaa, 0x1a3, 0x2a9, 0x3a0,
  0xd30, 0xc39, 0xf33, 0xe3a, 0x936, 0x83f, 0xb35, 0xa3c,
  0x53c, 0x435, 0x73f, 0x636, 0x13a, 0x33, 0x339, 0x230,
  0xe90, 0xf99, 0xc93, 0xd9a, 0xa96, 0xb9f, 0x895, 0x99c,
  0x69c, 0x795, 0x49f, 0x596, 0x29a, 0x393, 0x99, 0x190,
  0xf00, 0xe09, 0xd03, 0xc0a, 0xb06, 0xa0f, 0x905, 0x80c,
  0x70c, 0x605, 0x50f, 0x406, 0x30a, 0x203, 0x109, 0x0
]);

// Triangle table: which triangles to generate for each configuration
// (Simplified - only storing edge indices, not full triangulation)
// For MVP, we'll use a simpler approach: interpolate edges and generate triangles

interface MarchingCubesResult {
  positions: Float32Array;
  normals: Float32Array;
  indices: Uint32Array;
}

/**
 * Generate isosurface mesh using Marching Cubes algorithm
 */
export function generateIsosurface(
  values: Float32Array,
  dims: [number, number, number],
  origin: [number, number, number],
  gridVectors: [[number, number, number], [number, number, number], [number, number, number]],
  dataOrder: 'fortran_i_fastest' | 'c_k_fastest',
  isovalue: number
): MarchingCubesResult {
  const [nx, ny, nz] = dims;
  const vertices: number[] = [];
  const normals: number[] = [];
  
  // Helper: get value at (i, j, k)
  const getValue = (i: number, j: number, k: number): number => {
    if (i < 0 || i >= nx || j < 0 || j >= ny || k < 0 || k >= nz) {
      return 0;
    }
    const index = dataOrder === 'fortran_i_fastest'
      ? i + nx * (j + ny * k)  // FORTRAN: i-fastest
      : k + nz * (j + ny * i);  // C: k-fastest
    return values[index];
  };
  
  // Helper: interpolate vertex position between two grid points
  const interpolate = (
    p1: [number, number, number],
    p2: [number, number, number],
    v1: number,
    v2: number
  ): [number, number, number] => {
    if (Math.abs(v1 - v2) < 1e-10) {
      return p1;
    }
    const t = (isovalue - v1) / (v2 - v1);
    return [
      p1[0] + t * (p2[0] - p1[0]),
      p1[1] + t * (p2[1] - p1[1]),
      p1[2] + t * (p2[2] - p1[2]),
    ];
  };
  
  // Helper: compute grid point position in Cartesian space
  const getPosition = (i: number, j: number, k: number): [number, number, number] => {
    // MVP: Assume grid_vectors are axis-aligned (or nearly so)
    // position = origin + i*vx + j*vy + k*vz
    return [
      origin[0] + i * gridVectors[0][0] + j * gridVectors[1][0] + k * gridVectors[2][0],
      origin[1] + i * gridVectors[0][1] + j * gridVectors[1][1] + k * gridVectors[2][1],
      origin[2] + i * gridVectors[0][2] + j * gridVectors[1][2] + k * gridVectors[2][2],
    ];
  };
  
  // March through all cubes
  for (let k = 0; k < nz - 1; k++) {
    for (let j = 0; j < ny - 1; j++) {
      for (let i = 0; i < nx - 1; i++) {
        // Get 8 corner values
        const v = [
          getValue(i, j, k),
          getValue(i + 1, j, k),
          getValue(i + 1, j + 1, k),
          getValue(i, j + 1, k),
          getValue(i, j, k + 1),
          getValue(i + 1, j, k + 1),
          getValue(i + 1, j + 1, k + 1),
          getValue(i, j + 1, k + 1),
        ];
        
        // Compute cube index (which corners are inside)
        let cubeIndex = 0;
        for (let c = 0; c < 8; c++) {
          if (v[c] < isovalue) cubeIndex |= (1 << c);
        }
        
        // Skip if cube is entirely inside or outside
        if (cubeIndex === 0 || cubeIndex === 255) continue;
        
        // Get edge intersections
        const edgeFlags = EDGE_TABLE[cubeIndex];
        if (edgeFlags === 0) continue;
        
        // Compute positions of 8 corners
        const p = [
          getPosition(i, j, k),
          getPosition(i + 1, j, k),
          getPosition(i + 1, j + 1, k),
          getPosition(i, j + 1, k),
          getPosition(i, j, k + 1),
          getPosition(i + 1, j, k + 1),
          getPosition(i + 1, j + 1, k + 1),
          getPosition(i, j + 1, k + 1),
        ];
        
        // Interpolate edge vertices (12 edges)
        const edgeVertices: Array<[number, number, number]> = [];
        const edgeConnections = [
          [0, 1], [1, 2], [2, 3], [3, 0],  // bottom face
          [4, 5], [5, 6], [6, 7], [7, 4],  // top face
          [0, 4], [1, 5], [2, 6], [3, 7],  // vertical edges
        ];
        
        for (let e = 0; e < 12; e++) {
          if (edgeFlags & (1 << e)) {
            const [c1, c2] = edgeConnections[e];
            edgeVertices[e] = interpolate(p[c1], p[c2], v[c1], v[c2]);
          }
        }
        
        // Generate triangles (simplified triangulation)
        // For MVP, use a basic triangulation based on cube configuration
        // This is a simplified version - full MC33 has 256 cases
        const triangles = getTriangles(cubeIndex, edgeVertices);
        
        for (const tri of triangles) {
          for (const vertex of tri) {
            vertices.push(vertex[0], vertex[1], vertex[2]);
          }
          
          // Compute face normal (simple cross product)
          const v1 = new THREE.Vector3(tri[1][0] - tri[0][0], tri[1][1] - tri[0][1], tri[1][2] - tri[0][2]);
          const v2 = new THREE.Vector3(tri[2][0] - tri[0][0], tri[2][1] - tri[0][1], tri[2][2] - tri[0][2]);
          const normal = new THREE.Vector3().crossVectors(v1, v2).normalize();
          
          // Same normal for all 3 vertices (flat shading for MVP)
          for (let n = 0; n < 3; n++) {
            normals.push(normal.x, normal.y, normal.z);
          }
        }
      }
    }
  }
  
  // Generate indices (trivial since we're not deduplicating)
  const numVertices = vertices.length / 3;
  const indices = new Uint32Array(numVertices);
  for (let i = 0; i < numVertices; i++) {
    indices[i] = i;
  }
  
  // Sanity guard: validate mesh output
  
  // Check positions length
  if (vertices.length % 3 !== 0) {
    throw new Error(`Invalid mesh: positions length ${vertices.length} is not divisible by 3`);
  }
  
  // Check normals match positions
  if (normals.length !== vertices.length) {
    throw new Error(`Invalid mesh: normals length ${normals.length} != positions length ${vertices.length}`);
  }
  
  // Check indices length
  if (indices.length % 3 !== 0) {
    throw new Error(`Invalid mesh: indices length ${indices.length} is not divisible by 3`);
  }
  
  // Check indices are in valid range
  if (indices.length > 0) {
    const maxIndex = Math.max(...Array.from(indices));
    if (maxIndex >= numVertices) {
      throw new Error(`Invalid mesh: max index ${maxIndex} >= numVertices ${numVertices}`);
    }
  }
  
  // Check for NaN/Infinity in positions
  for (let i = 0; i < vertices.length; i++) {
    if (!isFinite(vertices[i])) {
      throw new Error(`Invalid mesh: non-finite value at positions[${i}]: ${vertices[i]}`);
    }
  }
  
  // Check for NaN/Infinity in normals
  for (let i = 0; i < normals.length; i++) {
    if (!isFinite(normals[i])) {
      throw new Error(`Invalid mesh: non-finite value at normals[${i}]: ${normals[i]}`);
    }
  }
  
  return {
    positions: new Float32Array(vertices),
    normals: new Float32Array(normals),
    indices,
  };
}

/**
 * Get triangles for a cube configuration (simplified)
 * Returns array of triangles, each triangle is 3 vertices
 */
function getTriangles(
  _cubeIndex: number,
  edgeVertices: Array<[number, number, number]>
): Array<Array<[number, number, number]>> {
  // Simplified triangulation table (only a few common cases for MVP)
  // Full MC33 would have all 256 cases
  const triangles: Array<Array<[number, number, number]>> = [];
  
  // Basic triangulation based on edge flags
  // This is a VERY simplified version - just to get something working
  const edges: number[] = [];
  for (let e = 0; e < 12; e++) {
    if (edgeVertices[e]) {
      edges.push(e);
    }
  }
  
  // Generate triangles from edges (fan triangulation)
  if (edges.length >= 3) {
    for (let i = 1; i < edges.length - 1; i++) {
      triangles.push([
        edgeVertices[edges[0]],
        edgeVertices[edges[i]],
        edgeVertices[edges[i + 1]],
      ]);
    }
  }
  
  return triangles;
}

