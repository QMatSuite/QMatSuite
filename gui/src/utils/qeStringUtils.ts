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

