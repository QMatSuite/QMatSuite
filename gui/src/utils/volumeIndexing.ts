/**
 * Phase 1: Centralized index calculation functions
 * 
 * These functions enforce the contract between data_order and flat index calculation.
 * All code must use these functions - no scattered index calculations.
 */

/**
 * Calculate flat index from (i,j,k) grid coordinates based on data order.
 * 
 * @param i,j,k Grid coordinates (0-indexed)
 * @param dims [nx, ny, nz] dimensions
 * @param dataOrder "fortran_i_fastest" or "c_k_fastest"
 * @returns Flat index into 1D array
 * @throws Error if dataOrder is invalid
 */
export function flatIndex(
  i: number,
  j: number,
  k: number,
  dims: [number, number, number],
  dataOrder: 'fortran_i_fastest' | 'c_k_fastest'
): number {
  const [nx, ny, nz] = dims;
  
  if (dataOrder === 'fortran_i_fastest') {
    // FORTRAN order: i-fastest (column-major)
    // idx = i + nx*(j + ny*k)
    return i + nx * (j + ny * k);
  } else if (dataOrder === 'c_k_fastest') {
    // C order: k-fastest (row-major)
    // idx = k + nz*(j + ny*i)
    return k + nz * (j + ny * i);
  } else {
    throw new Error(`Invalid data_order: ${dataOrder}. Must be 'fortran_i_fastest' or 'c_k_fastest'`);
  }
}

/**
 * Get value at grid coordinate (i,j,k) with bounds checking.
 * 
 * @param i,j,k Grid coordinates (0-indexed)
 * @param dims [nx, ny, nz] dimensions
 * @param dataOrder Data order
 * @param values Flat array of values
 * @returns Value at (i,j,k)
 * @throws Error if out of bounds or value is undefined
 */
export function getValue(
  i: number,
  j: number,
  k: number,
  dims: [number, number, number],
  dataOrder: 'fortran_i_fastest' | 'c_k_fastest',
  values: Float32Array | number[]
): number {
  const [nx, ny, nz] = dims;
  
  // Bounds check
  if (i < 0 || i >= nx || j < 0 || j >= ny || k < 0 || k >= nz) {
    const flatIdx = flatIndex(i, j, k, dims, dataOrder);
    throw new Error(
      `Grid coordinate out of bounds: (i=${i}, j=${j}, k=${k}) with dims=[${nx},${ny},${nz}], ` +
      `flatIdx=${flatIdx}, data_order=${dataOrder}`
    );
  }
  
  const idx = flatIndex(i, j, k, dims, dataOrder);
  const value = values[idx];
  
  if (value === undefined || value === null) {
    throw new Error(
      `Value at (i=${i}, j=${j}, k=${k}) is undefined. ` +
      `flatIdx=${idx}, values.length=${values.length}, data_order=${dataOrder}`
    );
  }
  
  return value;
}

