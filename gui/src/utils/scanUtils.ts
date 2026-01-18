/**
 * Utility functions for parameter scan feature.
 * 
 * Handles detection and manipulation of ScanRef values and parameter_scan definitions.
 */

/**
 * Check if a value is a ScanRef dict: {scan_ref: "<id>"}
 */
export function isScanRef(value: unknown): value is { scan_ref: string } {
  if (typeof value !== 'object' || value === null || Array.isArray(value)) {
    return false;
  }
  const obj = value as Record<string, unknown>;
  const keys = Object.keys(obj);
  return keys.length === 1 && keys[0] === 'scan_ref' && typeof obj.scan_ref === 'string' && obj.scan_ref.length > 0;
}

/**
 * Extract scan_id from a ScanRef value.
 */
export function getScanId(value: unknown): string | null {
  if (isScanRef(value)) {
    return value.scan_ref;
  }
  return null;
}

/**
 * Check if a value is a leaf scalar or simple list (allowed for scanning).
 */
export function isLeafValue(value: unknown): boolean {
  if (value === null || value === undefined) {
    return true;
  }
  if (typeof value === 'string' || typeof value === 'number' || typeof value === 'boolean') {
    return true;
  }
  if (Array.isArray(value)) {
    // Simple list: all items are scalars
    return value.every(item => 
      item === null || 
      typeof item === 'string' || 
      typeof item === 'number' || 
      typeof item === 'boolean'
    );
  }
  return false;
}

/**
 * Generate a new scan_id that doesn't conflict with existing ones.
 */
export function generateScanId(existingIds: string[]): string {
  let counter = 1;
  let scanId = `scan${String(counter).padStart(3, '0')}`;
  while (existingIds.includes(scanId)) {
    counter++;
    scanId = `scan${String(counter).padStart(3, '0')}`;
  }
  return scanId;
}

/**
 * Find all ScanRefs in parameters and return their scan_ids.
 */
export function findReferencedScanIds(
  parameters: Record<string, Record<string, unknown>>,
  cards?: Record<string, Record<string, unknown>>
): Set<string> {
  const scanIds = new Set<string>();
  
  // Check parameters
  for (const namelistParams of Object.values(parameters)) {
    for (const value of Object.values(namelistParams)) {
      const scanId = getScanId(value);
      if (scanId) {
        scanIds.add(scanId);
      }
    }
  }
  
  // Check cards
  if (cards) {
    for (const cardData of Object.values(cards)) {
      for (const value of Object.values(cardData)) {
        const scanId = getScanId(value);
        if (scanId) {
          scanIds.add(scanId);
        }
      }
    }
  }
  
  return scanIds;
}

/**
 * Count total scan combinations (naive product - upper bound).
 */
export function countScanCombinations(
  parameter_scan?: Record<string, { values: unknown[] }>
): number {
  if (!parameter_scan || Object.keys(parameter_scan).length === 0) {
    return 0;
  }
  
  let combinations = 1;
  for (const scanDef of Object.values(parameter_scan)) {
    const count = scanDef.values?.length || 0;
    if (count > 0) {
      combinations *= count;
    }
  }
  
  return combinations;
}

