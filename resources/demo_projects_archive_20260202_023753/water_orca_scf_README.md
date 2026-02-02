# Water ORCA SCF Single Point

B3LYP/def2-SVP DFT calculation on water molecule

## Overview

This demo demonstrates a H2O B3LYP Single Point calculation using ORCA.

**Molecule**: H2O  
**Method**: DFT  
**Basis**: def2-SVP  
**Runtime**: 10-30 seconds

## What It Computes

- Single-point energy calculation

## Required Engine

- **ORCA**: Must be installed and available in PATH or configured in QMatSuite settings

## How to Run

### Via CLI

```bash
# Create project from demo
qv create-demo-project --demo-id water_orca_scf

# Or specify target directory
qv create-demo-project /path/to/project --demo-id water_orca_scf

# Run calculation
qv run calc water-orca-scf
```

### Via GUI

1. Open QMatSuite GUI
2. Navigate to Demo Gallery
3. Select "Water ORCA SCF Single Point"
4. Click "Create Project"
5. Click "Run" on the calculation

## Expected Outputs

After running, you should find the following files in `calculations/*/raw/qc_chains/scf_*/`:

- `s.inp`
- `s.out`
- `s.property.txt`
- `scf.gbw`

## Output Files Description

- **`.out`**: ORCA text output with calculation details, energies, and convergence information
- **`.property.txt`**: Structured properties file (JSON-like format) with energies, geometries, and computed properties
- **`scf.gbw`**: ORCA wavefunction file (binary format)

## Documentation Reference

This demo is based on ORCA documentation:
- Source: `manual/quickstartguide/hellowater.html`

## Tags

orca, molecular, scf, dft, water, tutorial

## Difficulty

**Beginner** - B3LYP/def2-SVP DFT calculation on water molecule
