/**
 * Phase 2: Grid-to-world coordinate transformation
 * 
 * Correctly maps grid indices (i,j,k) to world coordinates (x,y,z) in Å.
 */

export interface VolumeMetadata {
  grid_shape: [number, number, number];
  origin_cart: [number, number, number];
  grid_vectors_cart: [[number, number, number], [number, number, number], [number, number, number]];
}

/**
 * Convert grid coordinate (i,j,k) to world coordinate (x,y,z).
 * 
 * For XSF DATAGRID_3D:
 * - grid_vectors represent the full grid box edge vectors
 * - Step vectors: a = v1/(nx-1), b = v2/(ny-1), c = v3/(nz-1)
 * - world = origin + i*a + j*b + k*c
 * 
 * For BXSF BANDGRID_3D:
 * - Same formula (nx-1 denominator ensures endpoints match)
 * 
 * @param i,j,k Grid coordinates (0-indexed, valid range: 0 to nx-1, ny-1, nz-1)
 * @param meta Volume metadata
 * @returns World coordinates [x, y, z] in Å
 */
export function gridToWorld(
  i: number,
  j: number,
  k: number,
  meta: VolumeMetadata
): [number, number, number] {
  const [nx, ny, nz] = meta.grid_shape;
  const [ox, oy, oz] = meta.origin_cart;
  const [v1, v2, v3] = meta.grid_vectors_cart;
  
  // Step vectors: divide full edge vectors by (n-1) to get per-grid-step vectors
  // This ensures that i=0 maps to origin and i=nx-1 maps to origin+v1
  const ax = v1[0] / (nx - 1);
  const ay = v1[1] / (nx - 1);
  const az = v1[2] / (nx - 1);
  
  const bx = v2[0] / (ny - 1);
  const by = v2[1] / (ny - 1);
  const bz = v2[2] / (ny - 1);
  
  const cx = v3[0] / (nz - 1);
  const cy = v3[1] / (nz - 1);
  const cz = v3[2] / (nz - 1);
  
  // World = origin + i*a + j*b + k*c
  return [
    ox + i * ax + j * bx + k * cx,
    oy + i * ay + j * by + k * cy,
    oz + i * az + j * bz + k * cz,
  ];
}

/**
 * Calculate bounding box from grid corners (8 corners).
 * 
 * @param meta Volume metadata
 * @returns {bboxMin, bboxMax, center, maxExtent}
 */
export function calculateBBox(meta: VolumeMetadata): {
  bboxMin: [number, number, number];
  bboxMax: [number, number, number];
  center: [number, number, number];
  maxExtent: number;
} {
  const [nx, ny, nz] = meta.grid_shape;
  
  // 8 corners of the grid
  const corners: Array<[number, number, number]> = [
    [0, 0, 0],
    [nx - 1, 0, 0],
    [nx - 1, ny - 1, 0],
    [0, ny - 1, 0],
    [0, 0, nz - 1],
    [nx - 1, 0, nz - 1],
    [nx - 1, ny - 1, nz - 1],
    [0, ny - 1, nz - 1],
  ];
  
  let minX = Infinity, minY = Infinity, minZ = Infinity;
  let maxX = -Infinity, maxY = -Infinity, maxZ = -Infinity;
  
  for (const [i, j, k] of corners) {
    const [x, y, z] = gridToWorld(i, j, k, meta);
    minX = Math.min(minX, x);
    minY = Math.min(minY, y);
    minZ = Math.min(minZ, z);
    maxX = Math.max(maxX, x);
    maxY = Math.max(maxY, y);
    maxZ = Math.max(maxZ, z);
  }
  
  const bboxMin: [number, number, number] = [minX, minY, minZ];
  const bboxMax: [number, number, number] = [maxX, maxY, maxZ];
  const center: [number, number, number] = [
    (minX + maxX) / 2,
    (minY + maxY) / 2,
    (minZ + maxZ) / 2,
  ];
  const maxExtent = Math.max(maxX - minX, maxY - minY, maxZ - minZ);
  
  return { bboxMin, bboxMax, center, maxExtent };
}

