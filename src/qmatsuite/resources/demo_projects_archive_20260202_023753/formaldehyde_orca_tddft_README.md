# Formaldehyde ORCA TDDFT

SCF + TDDFT excited states calculation

## Overview

This demo demonstrates a CH2O SCF + TDDFT calculation using ORCA.

**Molecule**: CH2O  
**Method**: DFT  
**Basis**: def2-SVP  
**Runtime**: 1-3 minutes

## What It Computes

- Single-point energy calculation
- Excited states via TDDFT

## Required Engine

- **ORCA**: Must be installed and available in PATH or configured in QMatSuite settings

## How to Run

### Via CLI

```bash
# Create project from demo
qms create-demo-project --demo-id formaldehyde_orca_tddft

# Or specify target directory
qms create-demo-project /path/to/project --demo-id formaldehyde_orca_tddft

# Run calculation
qms run calc formaldehyde-orca-tddft
```

### Via GUI

1. Open QMatSuite GUI
2. Navigate to Demo Gallery
3. Select "Formaldehyde ORCA TDDFT"
4. Click "Create Project"
5. Click "Run" on the calculation

## Expected Outputs

After running, you should find the following files in `calculations/*/raw/qc_chains/scf_*/`:

- `s_t.inp`
- `s_t.out`
- `s_t.property.txt`
- `scf.gbw`

## Output Files Description

- **`.out`**: ORCA text output with calculation details, energies, and convergence information
- **`.property.txt`**: Structured properties file (JSON-like format) with energies, geometries, and computed properties
- **`scf.gbw`**: ORCA wavefunction file (binary format)

## Documentation Reference

This demo is based on ORCA documentation:
- Source: `tutorials/tddft.html`

## Tags

orca, molecular, scf, tddft, excited_states, formaldehyde, tutorial

## Difficulty

**Intermediate** - SCF + TDDFT excited states calculation
