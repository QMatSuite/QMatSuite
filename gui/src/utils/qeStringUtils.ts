/**
 * QE String Utilities - Normalization and quoting helpers for QE parameter values
 * 
 * QE CHARACTER parameters often appear with quotes in input files (e.g., 'scf').
 * These utilities help normalize values for comparison while preserving original
 * representation in YAML storage.
 */

/**
 * Normalize a QE scalar value for comparison.
 * 
 * - Trims whitespace
 * - If value is wrapped in single quotes '...': returns inner content
 * - If value is wrapped in double quotes "...": returns inner content
 * - Otherwise returns value as-is
 * 
 * NOTE: This is scalar-only. Does not attempt to parse arrays or complex structures.
 * 
 * @param value - The string value to normalize
 * @returns Normalized value (unquoted, trimmed)
 * 
 * @example
 * normalizeQeScalar("'scf'") => "scf"
 * normalizeQeScalar('"nscf"') => "nscf"
 * normalizeQeScalar("  .true.  ") => ".true."
 * normalizeQeScalar("scf") => "scf"
 */
export function normalizeQeScalar(value: string): string {
  if (!value) return value;
  
  let trimmed = value.trim();
  
  // Check for single quotes: '...'
  if (trimmed.length >= 2 && trimmed.startsWith("'") && trimmed.endsWith("'")) {
    return trimmed.slice(1, -1);
  }
  
  // Check for double quotes: "..."
  if (trimmed.length >= 2 && trimmed.startsWith('"') && trimmed.endsWith('"')) {
    return trimmed.slice(1, -1);
  }
  
  return trimmed;
}

/**
 * Check if a value is quoted (single or double quotes).
 * 
 * @param value - The string value to check
 * @returns true if value is wrapped in quotes
 */
export function isQuoted(value: string): boolean {
  if (!value) return false;
  
  const trimmed = value.trim();
  return (
    (trimmed.length >= 2 && trimmed.startsWith("'") && trimmed.endsWith("'")) ||
    (trimmed.length >= 2 && trimmed.startsWith('"') && trimmed.endsWith('"'))
  );
}

/**
 * Wrap a value in single quotes for QE CHARACTER parameters.
 * 
 * For now, assumes enum tokens don't contain quotes. If needed later,
 * can add escaping for single quotes inside the value.
 * 
 * @param value - The value to quote
 * @returns Value wrapped in single quotes: 'value'
 * 
 * @example
 * quoteSingle("scf") => "'scf'"
 */
export function quoteSingle(value: string): string {
  return `'${value}'`;
}

/**
 * Display a scalar value for UI (strip quotes, trim).
 * 
 * This is the canonical function for displaying QE parameter values in the UI.
 * Always use this instead of directly displaying raw YAML values.
 * 
 * @param value - The string value to display
 * @returns Display-friendly value (unquoted, trimmed)
 * 
 * @example
 * displayScalar("'scf'") => "scf"
 * displayScalar("  .true.  ") => ".true."
 */
export function displayScalar(value: string): string {
  return normalizeQeScalar(value);
}

/**
 * Store an enum selection value for YAML (quote only when CHARACTER type).
 * 
 * This is the canonical function for storing enum selections from UI dropdowns.
 * Ensures correct quoting based on parameter type metadata.
 * 
 * @param value - The selected enum value (unquoted, e.g., "scf")
 * @param meta - Parameter metadata (must have type and enum fields)
 * @returns Value formatted for YAML storage
 * 
 * @example
 * storeEnumSelection("scf", {type: "CHARACTER", enum: ["scf", "nscf"]}) => "'scf'"
 * storeEnumSelection("scf", {type: "INTEGER", enum: [1, 2]}) => "scf" (as string)
 */
export function storeEnumSelection(value: string, meta: { type: string | null; enum?: unknown[] | null }): string {
  if (!value) return value;
  
  // Quote only for CHARACTER type enums
  if (meta.type?.toUpperCase() === 'CHARACTER' && meta.enum && meta.enum.length > 0) {
    return quoteSingle(value);
  }
  
  // For other types, return as-is (will be stored as string per string-only rule)
  return value;
}

/**
 * Convert a boolean to canonical QE logical value.
 * 
 * This is the canonical function for storing logical (TRUE/FALSE) values.
 * Always returns ".true." or ".false." as strings.
 * 
 * @param value - Boolean value
 * @returns Canonical QE logical string: ".true." or ".false."
 * 
 * @example
 * canonicalLogicalSelection(true) => ".true."
 * canonicalLogicalSelection(false) => ".false."
 */
export function canonicalLogicalSelection(value: boolean): string {
  return value ? '.true.' : '.false.';
}

