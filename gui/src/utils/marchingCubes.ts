/**
 * Marching Cubes - Standard Implementation
 * 
 * Generates triangle mesh from volumetric data at a given isovalue.
 * 
 * Uses standard Marching Cubes algorithm with complete 256-case lookup tables.
 * 
 * Standard corner numbering (8 corners):
 * 0: (i, j, k)
 * 1: (i+1, j, k)
 * 2: (i+1, j+1, k)
 * 3: (i, j+1, k)
 * 4: (i, j, k+1)
 * 5: (i+1, j, k+1)
 * 6: (i+1, j+1, k+1)
 * 7: (i, j+1, k+1)
 * 
 * Standard edge numbering (12 edges):
 * 0: 0-1, 1: 1-2, 2: 2-3, 3: 3-0  (bottom face)
 * 4: 4-5, 5: 5-6, 6: 6-7, 7: 7-4  (top face)
 * 8: 0-4, 9: 1-5, 10: 2-6, 11: 3-7  (vertical)
 * 
 * Lookup tables source: Standard Marching Cubes algorithm (Lorensen & Cline, 1987)
 * These tables are in the public domain and widely published.
 * 
 * Assumptions:
 * - Regular Cartesian grid (grid_vectors approximately orthogonal)
 * - Supports FORTRAN (i-fastest) and C (k-fastest) data order
 * 
 * TODO (future):
 * - Non-orthogonal grid_vectors support
 * - Vertex deduplication
 * - Normal smoothing
 */

import * as THREE from 'three';

// Marching Cubes lookup tables (standard MC33)
// Edge table: which edges are intersected for each cube configuration (256 cases)
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

// Triangle table: edge indices forming triangles for each cube configuration (256 cases)
// Each case is an array of edge indices (triplets form triangles, -1 terminates)
// Source: Standard Marching Cubes lookup table (widely published, public domain)
const TRI_TABLE: Int16Array[] = (() => {
  const table: Int16Array[] = [];
  // Initialize all 256 cases with empty arrays (will be filled with standard table)
  for (let i = 0; i < 256; i++) {
    table[i] = new Int16Array([-1]);
  }
  
  // Standard Marching Cubes triangulation table (complete 256 cases)
  // Format: [edge0, edge1, edge2, edge3, edge4, edge5, ...] where each triplet forms a triangle, -1 terminates
  table[0] = new Int16Array([-1]);
  table[1] = new Int16Array([0, 8, 3, -1]);
  table[2] = new Int16Array([0, 1, 9, -1]);
  table[3] = new Int16Array([1, 8, 3, 9, 8, 1, -1]);
  table[4] = new Int16Array([1, 2, 10, -1]);
  table[5] = new Int16Array([0, 8, 3, 1, 2, 10, -1]);
  table[6] = new Int16Array([9, 2, 10, 0, 2, 9, -1]);
  table[7] = new Int16Array([2, 8, 3, 2, 10, 8, 10, 9, 8, -1]);
  table[8] = new Int16Array([3, 11, 2, -1]);
  table[9] = new Int16Array([0, 11, 2, 8, 11, 0, -1]);
  table[10] = new Int16Array([1, 9, 0, 2, 3, 11, -1]);
  table[11] = new Int16Array([1, 11, 2, 1, 9, 11, 9, 8, 11, -1]);
  table[12] = new Int16Array([3, 10, 1, 11, 10, 3, -1]);
  table[13] = new Int16Array([0, 10, 1, 0, 8, 10, 8, 11, 10, -1]);
  table[14] = new Int16Array([3, 9, 0, 3, 11, 9, 11, 10, 9, -1]);
  table[15] = new Int16Array([9, 8, 10, 10, 8, 11, -1]);
  table[16] = new Int16Array([4, 7, 8, -1]);
  table[17] = new Int16Array([4, 3, 0, 7, 3, 4, -1]);
  table[18] = new Int16Array([0, 1, 9, 8, 4, 7, -1]);
  table[19] = new Int16Array([4, 1, 9, 4, 7, 1, 7, 3, 1, -1]);
  table[20] = new Int16Array([1, 2, 10, 8, 4, 7, -1]);
  table[21] = new Int16Array([3, 4, 7, 3, 0, 4, 1, 2, 10, -1]);
  table[22] = new Int16Array([9, 2, 10, 9, 0, 2, 8, 4, 7, -1]);
  table[23] = new Int16Array([2, 10, 9, 2, 9, 7, 2, 7, 3, 7, 9, 4, -1]);
  table[24] = new Int16Array([8, 4, 7, 3, 11, 2, -1]);
  table[25] = new Int16Array([11, 4, 7, 11, 2, 4, 2, 0, 4, -1]);
  table[26] = new Int16Array([9, 0, 1, 8, 4, 7, 2, 3, 11, -1]);
  table[27] = new Int16Array([4, 7, 11, 9, 4, 11, 9, 11, 2, 9, 2, 1, -1]);
  table[28] = new Int16Array([3, 10, 1, 3, 11, 10, 7, 8, 4, -1]);
  table[29] = new Int16Array([1, 11, 10, 1, 4, 11, 1, 0, 4, 7, 11, 4, -1]);
  table[30] = new Int16Array([4, 7, 8, 9, 0, 11, 9, 11, 10, 11, 0, 3, -1]);
  table[31] = new Int16Array([4, 7, 11, 4, 11, 9, 9, 11, 10, -1]);
  table[32] = new Int16Array([9, 5, 4, -1]);
  table[33] = new Int16Array([9, 5, 4, 0, 8, 3, -1]);
  table[34] = new Int16Array([0, 5, 4, 1, 5, 0, -1]);
  table[35] = new Int16Array([8, 5, 4, 8, 3, 5, 3, 1, 5, -1]);
  table[36] = new Int16Array([1, 2, 10, 9, 5, 4, -1]);
  table[37] = new Int16Array([3, 0, 8, 1, 2, 10, 4, 9, 5, -1]);
  table[38] = new Int16Array([5, 2, 10, 5, 4, 2, 4, 0, 2, -1]);
  table[39] = new Int16Array([2, 10, 5, 3, 2, 5, 3, 5, 4, 3, 4, 8, -1]);
  table[40] = new Int16Array([9, 5, 4, 2, 3, 11, -1]);
  table[41] = new Int16Array([0, 11, 2, 0, 8, 11, 4, 9, 5, -1]);
  table[42] = new Int16Array([0, 5, 4, 0, 1, 5, 2, 3, 11, -1]);
  table[43] = new Int16Array([2, 1, 5, 2, 5, 8, 2, 8, 11, 4, 8, 5, -1]);
  table[44] = new Int16Array([10, 3, 11, 10, 1, 3, 9, 5, 4, -1]);
  table[45] = new Int16Array([4, 9, 5, 0, 8, 1, 8, 10, 1, 8, 11, 10, -1]);
  table[46] = new Int16Array([5, 4, 0, 5, 0, 11, 5, 11, 10, 11, 0, 3, -1]);
  table[47] = new Int16Array([5, 4, 8, 5, 8, 10, 10, 8, 11, -1]);
  table[48] = new Int16Array([9, 7, 8, 5, 7, 9, -1]);
  table[49] = new Int16Array([9, 3, 0, 9, 5, 3, 5, 7, 3, -1]);
  table[50] = new Int16Array([0, 7, 8, 0, 1, 7, 1, 5, 7, -1]);
  table[51] = new Int16Array([1, 5, 3, 3, 5, 7, -1]);
  table[52] = new Int16Array([9, 7, 8, 9, 5, 7, 10, 1, 2, -1]);
  table[53] = new Int16Array([10, 1, 2, 9, 5, 0, 5, 3, 0, 5, 7, 3, -1]);
  table[54] = new Int16Array([8, 0, 2, 8, 2, 5, 8, 5, 7, 10, 5, 2, -1]);
  table[55] = new Int16Array([2, 10, 5, 2, 5, 3, 3, 5, 7, -1]);
  table[56] = new Int16Array([7, 9, 5, 7, 8, 9, 3, 11, 2, -1]);
  table[57] = new Int16Array([9, 5, 7, 9, 7, 2, 9, 2, 0, 2, 7, 11, -1]);
  table[58] = new Int16Array([2, 3, 11, 0, 1, 5, 0, 5, 7, 0, 7, 8, -1]);
  table[59] = new Int16Array([11, 2, 1, 11, 1, 7, 7, 1, 5, -1]);
  table[60] = new Int16Array([9, 5, 8, 8, 5, 7, 10, 1, 3, 10, 3, 11, -1]);
  table[61] = new Int16Array([5, 7, 0, 5, 0, 9, 7, 11, 0, 1, 0, 10, 11, 10, 0, -1]);
  table[62] = new Int16Array([11, 10, 0, 11, 0, 3, 10, 5, 0, 8, 0, 7, 5, 7, 0, -1]);
  table[63] = new Int16Array([11, 10, 5, 7, 11, 5, -1]);
  table[64] = new Int16Array([10, 6, 5, -1]);
  table[65] = new Int16Array([0, 8, 3, 5, 10, 6, -1]);
  table[66] = new Int16Array([9, 0, 1, 5, 10, 6, -1]);
  table[67] = new Int16Array([1, 8, 3, 1, 9, 8, 5, 10, 6, -1]);
  table[68] = new Int16Array([1, 6, 5, 2, 6, 1, -1]);
  table[69] = new Int16Array([1, 6, 5, 1, 2, 6, 3, 0, 8, -1]);
  table[70] = new Int16Array([9, 6, 5, 9, 0, 6, 0, 2, 6, -1]);
  table[71] = new Int16Array([5, 9, 8, 5, 8, 2, 5, 2, 6, 3, 2, 8, -1]);
  table[72] = new Int16Array([2, 3, 11, 10, 6, 5, -1]);
  table[73] = new Int16Array([11, 0, 8, 11, 2, 0, 10, 6, 5, -1]);
  table[74] = new Int16Array([0, 1, 9, 2, 3, 11, 5, 10, 6, -1]);
  table[75] = new Int16Array([5, 10, 6, 1, 9, 2, 9, 11, 2, 9, 8, 11, -1]);
  table[76] = new Int16Array([6, 3, 11, 6, 5, 3, 5, 1, 3, -1]);
  table[77] = new Int16Array([0, 8, 11, 0, 11, 5, 0, 5, 1, 5, 11, 6, -1]);
  table[78] = new Int16Array([3, 11, 6, 0, 3, 6, 0, 6, 5, 0, 5, 9, -1]);
  table[79] = new Int16Array([6, 5, 9, 6, 9, 11, 11, 9, 8, -1]);
  table[80] = new Int16Array([5, 10, 6, 4, 7, 8, -1]);
  table[81] = new Int16Array([4, 3, 0, 4, 7, 3, 6, 5, 10, -1]);
  table[82] = new Int16Array([1, 9, 0, 5, 10, 6, 8, 4, 7, -1]);
  table[83] = new Int16Array([10, 6, 5, 1, 9, 7, 1, 7, 3, 7, 9, 4, -1]);
  table[84] = new Int16Array([6, 1, 2, 6, 5, 1, 4, 7, 8, -1]);
  table[85] = new Int16Array([1, 2, 5, 5, 2, 6, 3, 0, 4, 3, 4, 7, -1]);
  table[86] = new Int16Array([8, 4, 7, 9, 0, 5, 0, 6, 5, 0, 2, 6, -1]);
  table[87] = new Int16Array([7, 3, 9, 7, 9, 4, 3, 2, 9, 5, 9, 6, 2, 6, 9, -1]);
  table[88] = new Int16Array([3, 11, 2, 7, 8, 4, 10, 6, 5, -1]);
  table[89] = new Int16Array([5, 10, 6, 4, 7, 2, 4, 2, 0, 2, 7, 11, -1]);
  table[90] = new Int16Array([0, 1, 9, 4, 7, 8, 2, 3, 11, 5, 10, 6, -1]);
  table[91] = new Int16Array([9, 2, 1, 9, 11, 2, 9, 4, 11, 7, 11, 4, 5, 10, 6, -1]);
  table[92] = new Int16Array([8, 4, 7, 3, 11, 5, 3, 5, 1, 5, 11, 6, -1]);
  table[93] = new Int16Array([5, 1, 11, 5, 11, 6, 1, 0, 11, 7, 11, 4, 0, 4, 11, -1]);
  table[94] = new Int16Array([0, 5, 9, 0, 6, 5, 0, 3, 6, 11, 6, 3, 8, 4, 7, -1]);
  table[95] = new Int16Array([6, 5, 9, 6, 9, 11, 4, 7, 9, 7, 11, 9, -1]);
  table[96] = new Int16Array([10, 4, 9, 6, 4, 10, -1]);
  table[97] = new Int16Array([4, 10, 6, 4, 9, 10, 0, 8, 3, -1]);
  table[98] = new Int16Array([10, 0, 1, 10, 6, 0, 6, 4, 0, -1]);
  table[99] = new Int16Array([8, 3, 1, 8, 1, 6, 8, 6, 4, 6, 1, 10, -1]);
  table[100] = new Int16Array([1, 4, 9, 1, 2, 4, 2, 6, 4, -1]);
  table[101] = new Int16Array([3, 0, 8, 1, 2, 9, 2, 4, 9, 2, 6, 4, -1]);
  table[102] = new Int16Array([0, 2, 4, 4, 2, 6, -1]);
  table[103] = new Int16Array([8, 3, 2, 8, 2, 4, 4, 2, 6, -1]);
  table[104] = new Int16Array([10, 4, 9, 10, 6, 4, 11, 2, 3, -1]);
  table[105] = new Int16Array([0, 8, 2, 2, 8, 11, 4, 9, 10, 4, 10, 6, -1]);
  table[106] = new Int16Array([3, 11, 2, 0, 1, 6, 0, 6, 4, 6, 1, 10, -1]);
  table[107] = new Int16Array([6, 4, 1, 6, 1, 10, 4, 8, 1, 2, 1, 11, 8, 11, 1, -1]);
  table[108] = new Int16Array([9, 6, 4, 9, 3, 6, 9, 1, 3, 11, 6, 3, -1]);
  table[109] = new Int16Array([8, 11, 1, 8, 1, 0, 11, 6, 1, 9, 1, 4, 6, 4, 1, -1]);
  table[110] = new Int16Array([3, 11, 6, 3, 6, 0, 0, 6, 4, -1]);
  table[111] = new Int16Array([6, 4, 8, 11, 6, 8, -1]);
  table[112] = new Int16Array([7, 10, 6, 7, 8, 10, 8, 9, 10, -1]);
  table[113] = new Int16Array([0, 7, 3, 0, 10, 7, 0, 9, 10, 6, 7, 10, -1]);
  table[114] = new Int16Array([10, 6, 7, 1, 10, 7, 1, 7, 8, 1, 8, 0, -1]);
  table[115] = new Int16Array([10, 6, 7, 10, 7, 1, 1, 7, 3, -1]);
  table[116] = new Int16Array([1, 2, 6, 1, 6, 8, 1, 8, 9, 8, 6, 7, -1]);
  table[117] = new Int16Array([2, 6, 9, 2, 9, 1, 6, 7, 9, 0, 9, 3, 7, 3, 9, -1]);
  table[118] = new Int16Array([7, 8, 0, 7, 0, 6, 6, 0, 2, -1]);
  table[119] = new Int16Array([7, 3, 2, 6, 7, 2, -1]);
  table[120] = new Int16Array([2, 3, 11, 10, 6, 8, 10, 8, 9, 8, 6, 7, -1]);
  table[121] = new Int16Array([2, 0, 7, 2, 7, 11, 0, 9, 7, 6, 7, 10, 9, 10, 7, -1]);
  table[122] = new Int16Array([1, 8, 0, 1, 7, 8, 1, 10, 7, 6, 7, 10, 2, 3, 11, -1]);
  table[123] = new Int16Array([11, 2, 1, 11, 1, 7, 10, 6, 1, 6, 7, 1, -1]);
  table[124] = new Int16Array([8, 9, 6, 8, 6, 7, 9, 1, 6, 11, 6, 3, 1, 3, 6, -1]);
  table[125] = new Int16Array([0, 9, 1, 11, 6, 7, -1]);
  table[126] = new Int16Array([7, 8, 0, 7, 0, 6, 3, 11, 0, 11, 6, 0, -1]);
  table[127] = new Int16Array([7, 11, 6, -1]);
  table[128] = new Int16Array([7, 6, 11, -1]);
  table[129] = new Int16Array([3, 0, 8, 11, 7, 6, -1]);
  table[130] = new Int16Array([0, 1, 9, 11, 7, 6, -1]);
  table[131] = new Int16Array([8, 1, 9, 8, 3, 1, 11, 7, 6, -1]);
  table[132] = new Int16Array([10, 1, 2, 6, 11, 7, -1]);
  table[133] = new Int16Array([1, 2, 10, 3, 0, 8, 6, 11, 7, -1]);
  table[134] = new Int16Array([2, 9, 0, 2, 10, 9, 6, 11, 7, -1]);
  table[135] = new Int16Array([6, 11, 7, 2, 10, 3, 10, 8, 3, 10, 9, 8, -1]);
  table[136] = new Int16Array([7, 2, 3, 6, 2, 7, -1]);
  table[137] = new Int16Array([7, 0, 8, 7, 6, 0, 6, 2, 0, -1]);
  table[138] = new Int16Array([2, 7, 6, 2, 3, 7, 0, 1, 9, -1]);
  table[139] = new Int16Array([1, 6, 2, 1, 8, 6, 1, 9, 8, 8, 7, 6, -1]);
  table[140] = new Int16Array([10, 7, 6, 10, 1, 7, 1, 3, 7, -1]);
  table[141] = new Int16Array([10, 7, 6, 1, 7, 10, 1, 8, 7, 1, 0, 8, -1]);
  table[142] = new Int16Array([0, 3, 7, 0, 7, 10, 0, 10, 9, 6, 10, 7, -1]);
  table[143] = new Int16Array([7, 6, 10, 7, 10, 8, 8, 10, 9, -1]);
  table[144] = new Int16Array([6, 8, 4, 11, 8, 6, -1]);
  table[145] = new Int16Array([3, 6, 11, 3, 0, 6, 0, 4, 6, -1]);
  table[146] = new Int16Array([8, 6, 11, 8, 4, 6, 9, 0, 1, -1]);
  table[147] = new Int16Array([9, 4, 6, 9, 6, 3, 9, 3, 1, 11, 3, 6, -1]);
  table[148] = new Int16Array([6, 8, 4, 6, 11, 8, 2, 10, 1, -1]);
  table[149] = new Int16Array([1, 2, 10, 3, 0, 11, 0, 6, 11, 0, 4, 6, -1]);
  table[150] = new Int16Array([4, 11, 8, 4, 6, 11, 0, 2, 9, 2, 10, 9, -1]);
  table[151] = new Int16Array([10, 9, 3, 10, 3, 2, 9, 4, 3, 11, 3, 6, 4, 6, 3, -1]);
  table[152] = new Int16Array([8, 2, 3, 8, 4, 2, 4, 6, 2, -1]);
  table[153] = new Int16Array([0, 4, 2, 4, 6, 2, -1]);
  table[154] = new Int16Array([1, 9, 0, 2, 3, 4, 2, 4, 6, 4, 3, 8, -1]);
  table[155] = new Int16Array([1, 9, 4, 1, 4, 2, 2, 4, 6, -1]);
  table[156] = new Int16Array([8, 1, 3, 8, 6, 1, 8, 4, 6, 6, 10, 1, -1]);
  table[157] = new Int16Array([10, 1, 0, 10, 0, 6, 6, 0, 4, -1]);
  table[158] = new Int16Array([4, 6, 3, 4, 3, 8, 6, 10, 3, 0, 3, 9, 10, 9, 3, -1]);
  table[159] = new Int16Array([10, 9, 4, 6, 10, 4, -1]);
  table[160] = new Int16Array([4, 9, 5, 7, 6, 11, -1]);
  table[161] = new Int16Array([0, 8, 3, 4, 9, 5, 11, 7, 6, -1]);
  table[162] = new Int16Array([5, 0, 1, 5, 4, 0, 7, 6, 11, -1]);
  table[163] = new Int16Array([11, 7, 6, 8, 3, 4, 3, 5, 4, 3, 1, 5, -1]);
  table[164] = new Int16Array([9, 5, 4, 10, 1, 2, 7, 6, 11, -1]);
  table[165] = new Int16Array([6, 11, 7, 1, 2, 10, 0, 8, 3, 4, 9, 5, -1]);
  table[166] = new Int16Array([7, 6, 11, 5, 4, 10, 4, 2, 10, 4, 0, 2, -1]);
  table[167] = new Int16Array([3, 4, 8, 3, 5, 4, 3, 2, 5, 10, 5, 2, 11, 7, 6, -1]);
  table[168] = new Int16Array([7, 2, 3, 7, 6, 2, 5, 4, 9, -1]);
  table[169] = new Int16Array([9, 5, 4, 0, 8, 6, 0, 6, 2, 6, 8, 7, -1]);
  table[170] = new Int16Array([3, 6, 2, 3, 7, 6, 1, 5, 0, 5, 4, 0, -1]);
  table[171] = new Int16Array([6, 2, 8, 6, 8, 7, 2, 1, 8, 4, 8, 5, 1, 5, 8, -1]);
  table[172] = new Int16Array([9, 5, 4, 10, 1, 6, 1, 7, 6, 1, 3, 7, -1]);
  table[173] = new Int16Array([1, 6, 10, 1, 7, 6, 1, 0, 7, 8, 7, 0, 9, 5, 4, -1]);
  table[174] = new Int16Array([4, 0, 10, 4, 10, 5, 0, 3, 10, 6, 10, 7, 3, 7, 10, -1]);
  table[175] = new Int16Array([7, 6, 10, 7, 10, 8, 5, 4, 10, 4, 8, 10, -1]);
  table[176] = new Int16Array([6, 9, 5, 6, 11, 9, 11, 8, 9, -1]);
  table[177] = new Int16Array([3, 6, 11, 0, 6, 3, 0, 5, 6, 0, 9, 5, -1]);
  table[178] = new Int16Array([0, 11, 8, 0, 5, 11, 0, 1, 5, 5, 6, 11, -1]);
  table[179] = new Int16Array([6, 11, 3, 6, 3, 5, 5, 3, 1, -1]);
  table[180] = new Int16Array([1, 2, 10, 9, 5, 11, 9, 11, 8, 11, 5, 6, -1]);
  table[181] = new Int16Array([0, 11, 3, 0, 6, 11, 0, 9, 6, 5, 6, 9, 1, 2, 10, -1]);
  table[182] = new Int16Array([11, 8, 5, 11, 5, 6, 8, 0, 5, 10, 5, 2, 0, 2, 5, -1]);
  table[183] = new Int16Array([6, 11, 3, 6, 3, 5, 2, 10, 3, 10, 5, 3, -1]);
  table[184] = new Int16Array([5, 8, 9, 5, 2, 8, 5, 6, 2, 3, 8, 2, -1]);
  table[185] = new Int16Array([9, 5, 6, 9, 6, 0, 0, 6, 2, -1]);
  table[186] = new Int16Array([1, 5, 8, 1, 8, 0, 5, 6, 8, 3, 8, 2, 6, 2, 8, -1]);
  table[187] = new Int16Array([1, 5, 6, 2, 1, 6, -1]);
  table[188] = new Int16Array([1, 3, 6, 1, 6, 10, 3, 8, 6, 5, 6, 9, 8, 9, 6, -1]);
  table[189] = new Int16Array([10, 1, 0, 10, 0, 6, 9, 5, 0, 5, 6, 0, -1]);
  table[190] = new Int16Array([0, 3, 8, 5, 6, 10, -1]);
  table[191] = new Int16Array([10, 5, 6, -1]);
  table[192] = new Int16Array([11, 5, 10, 7, 5, 11, -1]);
  table[193] = new Int16Array([11, 5, 10, 11, 7, 5, 8, 3, 0, -1]);
  table[194] = new Int16Array([5, 11, 7, 5, 10, 11, 1, 9, 0, -1]);
  table[195] = new Int16Array([10, 7, 5, 10, 11, 7, 9, 8, 1, 8, 3, 1, -1]);
  table[196] = new Int16Array([11, 1, 2, 11, 7, 1, 7, 5, 1, -1]);
  table[197] = new Int16Array([0, 8, 3, 1, 2, 7, 1, 7, 5, 7, 2, 11, -1]);
  table[198] = new Int16Array([9, 7, 5, 9, 2, 7, 9, 0, 2, 2, 11, 7, -1]);
  table[199] = new Int16Array([7, 5, 2, 7, 2, 11, 5, 9, 2, 3, 2, 8, 9, 8, 2, -1]);
  table[200] = new Int16Array([2, 5, 10, 2, 3, 5, 3, 7, 5, -1]);
  table[201] = new Int16Array([8, 2, 0, 8, 5, 2, 8, 7, 5, 10, 2, 5, -1]);
  table[202] = new Int16Array([9, 0, 1, 5, 10, 3, 5, 3, 7, 3, 10, 2, -1]);
  table[203] = new Int16Array([9, 8, 2, 9, 2, 1, 8, 7, 2, 10, 2, 5, 7, 5, 2, -1]);
  table[204] = new Int16Array([1, 3, 5, 3, 7, 5, -1]);
  table[205] = new Int16Array([0, 8, 7, 0, 7, 1, 1, 7, 5, -1]);
  table[206] = new Int16Array([9, 0, 3, 9, 3, 5, 5, 3, 7, -1]);
  table[207] = new Int16Array([9, 8, 7, 5, 9, 7, -1]);
  table[208] = new Int16Array([5, 8, 4, 5, 10, 8, 10, 11, 8, -1]);
  table[209] = new Int16Array([5, 0, 4, 5, 11, 0, 5, 10, 11, 11, 3, 0, -1]);
  table[210] = new Int16Array([0, 1, 9, 8, 4, 10, 8, 10, 11, 10, 4, 5, -1]);
  table[211] = new Int16Array([10, 11, 4, 10, 4, 5, 11, 3, 4, 9, 4, 1, 3, 1, 4, -1]);
  table[212] = new Int16Array([2, 5, 1, 2, 8, 5, 2, 11, 8, 4, 5, 8, -1]);
  table[213] = new Int16Array([0, 4, 11, 0, 11, 3, 4, 5, 11, 2, 11, 1, 5, 1, 11, -1]);
  table[214] = new Int16Array([0, 2, 5, 0, 5, 9, 2, 11, 5, 4, 5, 8, 11, 8, 5, -1]);
  table[215] = new Int16Array([9, 4, 5, 2, 11, 3, -1]);
  table[216] = new Int16Array([2, 5, 10, 3, 5, 2, 3, 4, 5, 3, 8, 4, -1]);
  table[217] = new Int16Array([5, 10, 2, 5, 2, 4, 4, 2, 0, -1]);
  table[218] = new Int16Array([3, 10, 2, 3, 5, 10, 3, 8, 5, 4, 5, 8, 0, 1, 9, -1]);
  table[219] = new Int16Array([5, 10, 2, 5, 2, 4, 1, 9, 2, 9, 4, 2, -1]);
  table[220] = new Int16Array([8, 4, 5, 8, 5, 3, 3, 5, 1, -1]);
  table[221] = new Int16Array([0, 4, 5, 1, 0, 5, -1]);
  table[222] = new Int16Array([8, 4, 5, 8, 5, 3, 9, 0, 5, 0, 3, 5, -1]);
  table[223] = new Int16Array([9, 4, 5, -1]);
  table[224] = new Int16Array([4, 11, 7, 4, 9, 11, 9, 10, 11, -1]);
  table[225] = new Int16Array([0, 8, 3, 4, 9, 7, 9, 11, 7, 9, 10, 11, -1]);
  table[226] = new Int16Array([1, 10, 11, 1, 11, 4, 1, 4, 0, 7, 4, 11, -1]);
  table[227] = new Int16Array([3, 1, 4, 3, 4, 8, 1, 10, 4, 7, 4, 11, 10, 11, 4, -1]);
  table[228] = new Int16Array([4, 11, 7, 9, 11, 4, 9, 2, 11, 9, 1, 2, -1]);
  table[229] = new Int16Array([9, 7, 4, 9, 11, 7, 9, 1, 11, 2, 11, 1, 0, 8, 3, -1]);
  table[230] = new Int16Array([11, 7, 4, 11, 4, 2, 2, 4, 0, -1]);
  table[231] = new Int16Array([11, 7, 4, 11, 4, 2, 8, 3, 4, 3, 2, 4, -1]);
  table[232] = new Int16Array([2, 9, 10, 2, 7, 9, 2, 3, 7, 7, 4, 9, -1]);
  table[233] = new Int16Array([9, 10, 7, 9, 7, 4, 10, 2, 7, 8, 7, 0, 2, 0, 7, -1]);
  table[234] = new Int16Array([3, 7, 10, 3, 10, 2, 7, 4, 10, 1, 10, 0, 4, 0, 10, -1]);
  table[235] = new Int16Array([1, 10, 2, 8, 7, 4, -1]);
  table[236] = new Int16Array([4, 9, 1, 4, 1, 7, 7, 1, 3, -1]);
  table[237] = new Int16Array([4, 9, 1, 4, 1, 7, 0, 8, 1, 8, 7, 1, -1]);
  table[238] = new Int16Array([4, 0, 3, 7, 4, 3, -1]);
  table[239] = new Int16Array([4, 8, 7, -1]);
  table[240] = new Int16Array([9, 10, 8, 10, 11, 8, -1]);
  table[241] = new Int16Array([3, 0, 9, 3, 9, 11, 11, 9, 10, -1]);
  table[242] = new Int16Array([0, 1, 10, 0, 10, 8, 8, 10, 11, -1]);
  table[243] = new Int16Array([3, 1, 10, 11, 3, 10, -1]);
  table[244] = new Int16Array([1, 2, 11, 1, 11, 9, 9, 11, 8, -1]);
  table[245] = new Int16Array([3, 0, 9, 3, 9, 11, 1, 2, 9, 2, 11, 9, -1]);
  table[246] = new Int16Array([0, 2, 11, 8, 0, 11, -1]);
  table[247] = new Int16Array([3, 2, 11, -1]);
  table[248] = new Int16Array([2, 3, 8, 2, 8, 10, 10, 8, 9, -1]);
  table[249] = new Int16Array([9, 10, 2, 0, 9, 2, -1]);
  table[250] = new Int16Array([2, 3, 8, 2, 8, 10, 0, 1, 8, 1, 10, 8, -1]);
  table[251] = new Int16Array([1, 10, 2, -1]);
  table[252] = new Int16Array([1, 3, 8, 9, 1, 8, -1]);
  table[253] = new Int16Array([0, 9, 1, -1]);
  table[254] = new Int16Array([0, 3, 8, -1]);
  table[255] = new Int16Array([-1]);
  
  return table;
})();

interface MarchingCubesResult {
  positions: Float32Array;
  normals: Float32Array;
  indices: Uint32Array;
}

/**
 * Generate isosurface mesh using Marching Cubes algorithm
 */
export interface VolumeStats {
  nNaN: number;
  nInf: number;
  nLess: number;
  nGreater: number;
  nEq: number;
  nActiveCubes: number; // cubes with cubeIndex != 0 && != 255
  bboxMin?: [number, number, number];
  bboxMax?: [number, number, number];
  center?: [number, number, number];
  maxExtent?: number;
  cubeIndexStats?: {
    totalCells: number;
    activeCells: number;
    cubeIndex0: number;
    cubeIndex255: number;
    topCubeIndexes: Array<{ index: number; count: number }>;
  };
  sampleActiveCube?: {
    cell: [number, number, number];
    corners: Array<{ coords: [number, number, number]; flatIdx: number; value: number }>;
    cubeIndex: number;
  } | null;
}

export function generateIsosurface(
  values: Float32Array,
  dims: [number, number, number],
  origin: [number, number, number],
  gridVectors: [[number, number, number], [number, number, number], [number, number, number]],
  dataOrder: 'fortran_i_fastest' | 'c_k_fastest',
  isovalue: number,
  stats?: { current: VolumeStats }
): MarchingCubesResult {
  const [nx, ny, nz] = dims;
  const vertices: number[] = [];
  const normals: number[] = [];
  
  // Initialize stats if provided
  if (stats) {
    stats.current = {
      nNaN: 0,
      nInf: 0,
      nLess: 0,
      nGreater: 0,
      nEq: 0,
      nActiveCubes: 0,
      cubeIndexStats: {
        totalCells: 0,
        activeCells: 0,
        cubeIndex0: 0,
        cubeIndex255: 0,
        topCubeIndexes: [],
      },
      sampleActiveCube: null,
    };
  }
  
  // CubeIndex frequency map
  const cubeIndexFreq = new Map<number, number>();
  
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
  
  // Safe interpolation function to prevent NaN/Inf
  const safeInterp = (iso: number, v1: number, v2: number): number => {
    const denom = v2 - v1;
    if (!Number.isFinite(denom) || Math.abs(denom) < 1e-12) {
      return 0.5; // midpoint
    }
    let t = (iso - v1) / denom;
    if (!Number.isFinite(t)) {
      t = 0.5;
    }
    if (t < 0) t = 0;
    if (t > 1) t = 1;
    return t;
  };
  
  // Helper: interpolate vertex position between two grid points
  const interpolate = (
    p1: [number, number, number],
    p2: [number, number, number],
    v1: number,
    v2: number
  ): [number, number, number] => {
    const t = safeInterp(isovalue, v1, v2);
    const x = p1[0] + t * (p2[0] - p1[0]);
    const y = p1[1] + t * (p2[1] - p1[1]);
    const z = p1[2] + t * (p2[2] - p1[2]);
    
    // Fallback to midpoint if any component is non-finite
    if (!Number.isFinite(x) || !Number.isFinite(y) || !Number.isFinite(z)) {
      return [
        (p1[0] + p2[0]) / 2,
        (p1[1] + p2[1]) / 2,
        (p1[2] + p2[2]) / 2,
      ];
    }
    
    return [x, y, z];
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
  
  // Compute stats for all values (once, before marching)
  if (stats) {
    for (let idx = 0; idx < values.length; idx++) {
      const v = values[idx];
      if (!Number.isFinite(v)) {
        if (Number.isNaN(v)) {
          stats.current.nNaN++;
        } else {
          stats.current.nInf++;
        }
      } else {
        if (v < isovalue) {
          stats.current.nLess++;
        } else if (v > isovalue) {
          stats.current.nGreater++;
        } else {
          stats.current.nEq++;
        }
      }
    }
  }
  
  let debugFallbackCount = 0;
  let sampleActiveCubeCollected = false;
  let triTableLogPrinted = false; // P3: Only print once
  
  // March through all cubes
  for (let k = 0; k < nz - 1; k++) {
    for (let j = 0; j < ny - 1; j++) {
      for (let i = 0; i < nx - 1; i++) {
        // Get 8 corner values
        // Corner order (standard Marching Cubes):
        // 0: (i, j, k)
        // 1: (i+1, j, k)
        // 2: (i+1, j+1, k)
        // 3: (i, j+1, k)
        // 4: (i, j, k+1)
        // 5: (i+1, j, k+1)
        // 6: (i+1, j+1, k+1)
        // 7: (i, j+1, k+1)
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
        // Bit order: corner 0 = bit 0, corner 1 = bit 1, ..., corner 7 = bit 7
        let cubeIndex = 0;
        for (let c = 0; c < 8; c++) {
          if (v[c] < isovalue) cubeIndex |= (1 << c);
        }
        
        // Collect cubeIndex statistics
        if (stats) {
          stats.current.cubeIndexStats!.totalCells++;
          const count = cubeIndexFreq.get(cubeIndex) || 0;
          cubeIndexFreq.set(cubeIndex, count + 1);
          
          if (cubeIndex === 0) {
            stats.current.cubeIndexStats!.cubeIndex0++;
          } else if (cubeIndex === 255) {
            stats.current.cubeIndexStats!.cubeIndex255++;
          } else {
            stats.current.cubeIndexStats!.activeCells++;
            stats.current.nActiveCubes++;
            
            // Collect sample active cube (first 5 encountered, store the last one)
            // Step B: Check corner indices are adjacent
            if (!sampleActiveCubeCollected || stats.current.nActiveCubes <= 5) {
              const cornerCoords: Array<[number, number, number]> = [
                [i, j, k],
                [i + 1, j, k],
                [i + 1, j + 1, k],
                [i, j + 1, k],
                [i, j, k + 1],
                [i + 1, j, k + 1],
                [i + 1, j + 1, k + 1],
                [i, j + 1, k + 1],
              ];
              
              const cornersWithIdx = cornerCoords.map((coords, idx) => {
                const flatIdx = dataOrder === 'fortran_i_fastest'
                  ? coords[0] + nx * (coords[1] + ny * coords[2])
                  : coords[2] + nz * (coords[1] + ny * coords[0]);
                
                // Step B: Verify corner coords are adjacent (only i/i+1, j/j+1, k/k+1)
                const validCorner = 
                  (coords[0] === i || coords[0] === i + 1) &&
                  (coords[1] === j || coords[1] === j + 1) &&
                  (coords[2] === k || coords[2] === k + 1);
                
                if (!validCorner && stats.current.nActiveCubes <= 5) {
                  console.warn(`[Step B] Invalid corner coords at cube (${i},${j},${k}) corner ${idx}: expected (${i}|${i+1}, ${j}|${j+1}, ${k}|${k+1}), got (${coords[0]},${coords[1]},${coords[2]})`);
                }
                
                return {
                  coords,
                  flatIdx,
                  value: v[idx],
                };
              });
              
              stats.current.sampleActiveCube = {
                cell: [i, j, k],
                corners: cornersWithIdx,
                cubeIndex,
              };
              
              if (stats.current.nActiveCubes <= 5) {
                console.log(`[Step B] Active cube ${stats.current.nActiveCubes}: cell (${i},${j},${k}), cubeIndex=${cubeIndex}`);
                cornersWithIdx.forEach((corner, idx) => {
                  console.log(`  Corner ${idx}: (${corner.coords[0]},${corner.coords[1]},${corner.coords[2]}), flatIdx=${corner.flatIdx}, value=${corner.value.toFixed(4)}`);
                });
              }
              
              if (!sampleActiveCubeCollected) {
                sampleActiveCubeCollected = true;
              }
            }
          }
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
        // Standard edge-to-corner mapping:
        // 0: corner 0-1, 1: corner 1-2, 2: corner 2-3, 3: corner 3-0  (bottom face)
        // 4: corner 4-5, 5: corner 5-6, 6: corner 6-7, 7: corner 7-4  (top face)
        // 8: corner 0-4, 9: corner 1-5, 10: corner 2-6, 11: corner 3-7  (vertical)
        const edgeVertices: Array<[number, number, number] | null> = new Array(12).fill(null);
        const edgeConnections = [
          [0, 1], [1, 2], [2, 3], [3, 0],  // bottom face
          [4, 5], [5, 6], [6, 7], [7, 4],  // top face
          [0, 4], [1, 5], [2, 6], [3, 7],  // vertical edges
        ];
        
        for (let e = 0; e < 12; e++) {
          if (edgeFlags & (1 << e)) {
            const [c1, c2] = edgeConnections[e];
            const interpolated = interpolate(p[c1], p[c2], v[c1], v[c2]);
            // Check if interpolation produced NaN/Inf and fallback to midpoint
            if (!Number.isFinite(interpolated[0]) || !Number.isFinite(interpolated[1]) || !Number.isFinite(interpolated[2])) {
              debugFallbackCount++;
              edgeVertices[e] = [
                (p[c1][0] + p[c2][0]) / 2,
                (p[c1][1] + p[c2][1]) / 2,
                (p[c1][2] + p[c2][2]) / 2,
              ];
            } else {
              edgeVertices[e] = interpolated;
            }
          }
        }
        
        // Generate triangles using standard Marching Cubes triTable
        const triangles = getTrianglesStandard(cubeIndex, edgeVertices);
        
        // P3: Print triTable usage proof (once for first active cube)
        if (!triTableLogPrinted && cubeIndex !== 0 && cubeIndex !== 255) {
          const triCase = TRI_TABLE[cubeIndex];
          const first12Edges = Array.from(triCase.slice(0, Math.min(12, triCase.length))).map(v => v === -1 ? 'END' : String(v));
          console.log(`[P3 triTable Proof] First active cube: cubeIndex=${cubeIndex}, triTable[${cubeIndex}] = [${first12Edges.join(', ')}]`);
          console.log(`[P3 triTable Proof] Generated triangles=${triangles.length} for this cube, total vertices so far=${vertices.length / 3}`);
          triTableLogPrinted = true;
        }
        
        for (let triIdx = 0; triIdx < triangles.length; triIdx++) {
          const tri = triangles[triIdx];
          const v0 = tri[0];
          const v1 = tri[1];
          const v2 = tri[2];
          vertices.push(v0[0], v0[1], v0[2], v1[0], v1[1], v1[2], v2[0], v2[1], v2[2]);
          
          // Compute face normal (simple cross product)
          const vec1 = new THREE.Vector3(v1[0] - v0[0], v1[1] - v0[1], v1[2] - v0[2]);
          const vec2 = new THREE.Vector3(v2[0] - v0[0], v2[1] - v0[1], v2[2] - v0[2]);
          const normal = new THREE.Vector3().crossVectors(vec1, vec2).normalize();
          
          // Same normal for all 3 vertices (flat shading for MVP)
          normals.push(normal.x, normal.y, normal.z, normal.x, normal.y, normal.z, normal.x, normal.y, normal.z);
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
  
  // Guard: if iso crosses range but no triangles, throw error
  if (stats && stats.current.nLess > 0 && stats.current.nGreater > 0) {
    const numTriangles = indices.length / 3;
    if (numTriangles === 0) {
      throw new Error(
        `MC produced 0 triangles despite iso crossing range. ` +
        `nLess=${stats.current.nLess} nGreater=${stats.current.nGreater} ` +
        `nActiveCubes=${stats.current.nActiveCubes} debugFallbackCount=${debugFallbackCount}`
      );
    }
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
  
  // Compute bbox (Step A)
  if (vertices.length > 0 && stats) {
    let bboxMinX = Infinity, bboxMinY = Infinity, bboxMinZ = Infinity;
    let bboxMaxX = -Infinity, bboxMaxY = -Infinity, bboxMaxZ = -Infinity;
    
    for (let i = 0; i < vertices.length; i += 3) {
      bboxMinX = Math.min(bboxMinX, vertices[i]);
      bboxMaxX = Math.max(bboxMaxX, vertices[i]);
      bboxMinY = Math.min(bboxMinY, vertices[i + 1]);
      bboxMaxY = Math.max(bboxMaxY, vertices[i + 1]);
      bboxMinZ = Math.min(bboxMinZ, vertices[i + 2]);
      bboxMaxZ = Math.max(bboxMaxZ, vertices[i + 2]);
    }
    
    stats.current.bboxMin = [bboxMinX, bboxMinY, bboxMinZ];
    stats.current.bboxMax = [bboxMaxX, bboxMaxY, bboxMaxZ];
    stats.current.center = [
      (bboxMinX + bboxMaxX) / 2,
      (bboxMinY + bboxMaxY) / 2,
      (bboxMinZ + bboxMaxZ) / 2,
    ];
    stats.current.maxExtent = Math.max(
      bboxMaxX - bboxMinX,
      bboxMaxY - bboxMinY,
      bboxMaxZ - bboxMinZ
    );
    
    // Log Step A bbox
    console.log(`[Step A] Mesh bbox: min=[${bboxMinX.toFixed(2)}, ${bboxMinY.toFixed(2)}, ${bboxMinZ.toFixed(2)}], max=[${bboxMaxX.toFixed(2)}, ${bboxMaxY.toFixed(2)}, ${bboxMaxZ.toFixed(2)}], center=[${stats.current.center[0].toFixed(2)}, ${stats.current.center[1].toFixed(2)}, ${stats.current.center[2].toFixed(2)}], maxExtent=${stats.current.maxExtent.toFixed(2)}`);
  }
  
  // Finalize cubeIndex statistics (Step C)
  if (stats && stats.current.cubeIndexStats) {
    const sorted = Array.from(cubeIndexFreq.entries())
      .sort((a, b) => b[1] - a[1])
      .slice(0, 10);
    stats.current.cubeIndexStats.topCubeIndexes = sorted.map(([index, count]) => ({ index, count }));
    
    // Log Step C stats
    console.log(`[Step C] CubeIndex distribution:`);
    console.log(`  totalCells: ${stats.current.cubeIndexStats.totalCells}`);
    console.log(`  activeCells: ${stats.current.cubeIndexStats.activeCells}`);
    console.log(`  cubeIndex==0: ${stats.current.cubeIndexStats.cubeIndex0}`);
    console.log(`  cubeIndex==255: ${stats.current.cubeIndexStats.cubeIndex255}`);
    console.log(`  Top 5 cubeIndexes: ${sorted.slice(0, 5).map(([idx, cnt]) => `${idx}(${cnt})`).join(', ')}`);
    
    // P3: Log final vertex/triangle counts
    const finalVertexCount = vertices.length / 3;
    const finalTriangleCount = indices.length / 3;
    console.log(`[P3 triTable Proof] Final counts: vertexCount=${finalVertexCount}, triangleCount=${finalTriangleCount}, indexCount=${indices.length}`);
  }
  
  return {
    positions: new Float32Array(vertices),
    normals: new Float32Array(normals),
    indices,
  };
}

/**
 * Get triangles for a cube configuration using standard Marching Cubes triTable
 * Returns array of triangles, each triangle is an array of 3 vertices (each vertex is [x,y,z])
 */
type Triangle = [[number, number, number], [number, number, number], [number, number, number]];

function getTrianglesStandard(
  cubeIndex: number,
  edgeVertices: Array<[number, number, number] | null>
): Triangle[] {
  const triangles: Triangle[] = [];
  const triCase = TRI_TABLE[cubeIndex];
  
  // triCase contains edge indices in triplets, -1 terminates
  for (let i = 0; i < triCase.length && triCase[i] !== -1; i += 3) {
    const e0: number = triCase[i] as number;
    const e1: number = triCase[i + 1] as number;
    const e2: number = triCase[i + 2] as number;
    
    // All three edges must have valid vertices
    const v0 = edgeVertices[e0];
    const v1 = edgeVertices[e1];
    const v2 = edgeVertices[e2];
    if (v0 && v1 && v2) {
      triangles.push([v0, v1, v2]);
    }
  }
  
  return triangles;
}

