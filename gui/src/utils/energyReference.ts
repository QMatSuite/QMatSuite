/**
 * Energy reference inference for BXSF Fermi surface.
 * 
 * Given value range and Fermi energy, determine if values are:
 * - absolute energy E (reference="absolute"), iso=Ef
 * - relative to Fermi (E-Ef) (reference="relative_to_fermi"), iso=0
 * - unknown (reference="unknown"), iso=(min+max)/2
 */

export interface EnergyReferenceResult {
  reference: 'absolute' | 'relative_to_fermi' | 'unknown';
  effective_iso_default: number;
  iso_default_reason: 'A' | 'B' | 'C';
}

/**
 * Infer energy reference from value range and Fermi energy.
 * 
 * Rules:
 * A) If fermi_energy in [min,max] (inclusive): reference="absolute", iso=Ef
 * B) Else if 0 in [min,max] AND abs(Ef) >> (max-min) (e.g., abs(Ef) > 2*(max-min)):
 *    reference="relative_to_fermi", iso=0
 * C) Else: reference="unknown", iso=(min+max)/2
 */
export function inferEnergyReference(
  values_min: number,
  values_max: number,
  fermi_energy: number | undefined
): EnergyReferenceResult {
  const range = values_max - values_min;
  
  // Rule A: Fermi energy is within value range
  if (fermi_energy !== undefined) {
    if (values_min <= fermi_energy && fermi_energy <= values_max) {
      return {
        reference: 'absolute',
        effective_iso_default: fermi_energy,
        iso_default_reason: 'A',
      };
    }
  }
  
  // Rule B: 0 is in range AND Fermi is far from range
  if (values_min <= 0 && 0 <= values_max) {
    if (fermi_energy !== undefined) {
      const absEf = Math.abs(fermi_energy);
      // Check if Ef is "far" from range (more than 2x the range span)
      if (absEf > 2 * range) {
        return {
          reference: 'relative_to_fermi',
          effective_iso_default: 0,
          iso_default_reason: 'B',
        };
      }
    }
  }
  
  // Rule C: Unknown case
  const midRange = (values_min + values_max) / 2;
  return {
    reference: 'unknown',
    effective_iso_default: midRange,
    iso_default_reason: 'C',
  };
}

