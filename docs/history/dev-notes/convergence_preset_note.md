# Convergence Preset Developer Note

## Overview

The `convergence` preset controls SCF convergence strategy parameters for pw.x-based calculations. It provides 4 profiles (fast, normal, robust, very_robust) that adjust mixing parameters and maximum iteration limits.

## Key Design Decisions

### Parameter Ownership

**Convergence preset controls ONLY:**
- `ELECTRONS.mixing_beta` (float)
- `ELECTRONS.electron_maxstep` (int)
- `ELECTRONS.mixing_mode` (string)
- `ELECTRONS.mixing_ndim` (int)
- `ELECTRONS.diagonalization` (string)

**Convergence preset does NOT control:**
- `ELECTRONS.conv_thr` - This belongs to the `precision` dimension (per Constitution §12.1: key ownership uniqueness)

### Fixed Ladder Values

The following values are fixed and must not be changed:

- **mixing_beta ladder**: 0.7, 0.4, 0.2, 0.1 (for fast, normal, robust, very_robust)
- **electron_maxstep ladder**: 100, 150, 200, 250 (for fast, normal, robust, very_robust)

Rationale: If not converged within ≤250 steps, treat as non-converging (do not exceed 250).

### Scope

The convergence preset applies to all pw-based step types:
- scf, nscf, relax, vc-relax, bands_pw, md, vc-md

This is implemented via `CONVERGENCE_VARIANT` in `variants_registry.py` with `applies_to_step_types` matching all pw.x executable steps.

### Profiles

| Profile | mixing_beta | electron_maxstep | mixing_mode | mixing_ndim | diagonalization |
|---------|-------------|------------------|-------------|-------------|-----------------|
| fast | 0.7 | 100 | plain | 8 | david |
| normal | 0.4 | 150 | plain | 8 | david |
| robust | 0.2 | 200 | TF | 10 | rmm-davidson |
| very_robust | 0.1 | 250 | local-TF | 12 | cg |

## Implementation Files

- `src/quantumvitas/presets/dimensions.py`: `ConvergenceOption` enum
- `src/quantumvitas/presets/paramspace.py`: `build_convergence_paramspace()` function
- `src/quantumvitas/presets/spaces_registry.py`: Registration in `SPACES` dict
- `src/quantumvitas/presets/variants_registry.py`: `CONVERGENCE_VARIANT` definition
- `src/quantumvitas/presets/catalog.py`: UI labels, descriptions, defaults, order
- `src/quantumvitas/presets/integration.py`: Convergence handling in `apply_presets_to_step()`

## Tests

See `tests/unit/test_preset_integration.py::TestConvergencePreset`:
- Each profile produces exact patch values
- Patch contains no extraneous keys
- Convergence patch never sets conv_thr
- Convergence + precision coexist correctly (conv_thr only from precision)
- Scope test: all pw step types receive convergence patch

## UI Discovery

The convergence preset is automatically discoverable by the UI via the `get_preset_catalog` RPC handler. No custom UI code is required - the catalog system automatically includes convergence in the dimensions list.

