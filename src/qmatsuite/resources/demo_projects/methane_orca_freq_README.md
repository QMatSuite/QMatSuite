# Methane ORCA Frequency

SCF + numerical frequency calculation

## Overview

This demo demonstrates a CH4 SCF + Frequency calculation using ORCA.

**Molecule**: CH4  
**Method**: DFT  
**Basis**: def2-TZVP  
**Runtime**: 2-5 minutes

## What It Computes

- Single-point energy calculation

## Required Engine

- **ORCA**: Must be installed and available in PATH or configured in QMatSuite settings

## How to Run

### Via CLI

```bash
# Create project from demo
qms create-demo-project --demo-id methane_orca_freq

# Or specify target directory
qms create-demo-project /path/to/project --demo-id methane_orca_freq

# Run calculation
qms run calc methane-orca-freq
```

### Via GUI

1. Open QMatSuite GUI
2. Navigate to Demo Gallery
3. Select "Methane ORCA Frequency"
4. Click "Create Project"
5. Click "Run" on the calculation

## Expected Outputs

After running, you should find the following files in `calculations/*/raw/qc_chains/scf_*/`:

- `s_f.inp`
- `s_f.out`
- `s_f.property.txt`
- `s_f.hess`
- `scf.gbw`

## Output Files Description

- **`.out`**: ORCA text output with calculation details, energies, and convergence information
- **`.property.txt`**: Structured properties file (JSON-like format) with energies, geometries, and computed properties
- **`scf.gbw`**: ORCA wavefunction file (binary format)
- **`s_f.hess`**: Hessian matrix for frequency calculation

## Documentation Reference

This demo is based on ORCA documentation:
- Source: `tutorials/frequencies.html`

## Tags

orca, molecular, scf, frequency, vibrational, methane, tutorial

## Difficulty

**Intermediate** - SCF + numerical frequency calculation
