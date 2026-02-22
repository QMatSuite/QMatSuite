# Engine Code Inventory

**Document Version**: 1.0
**Date**: 2026-01-20

---

## 1. Overview

This document provides a complete inventory of engine-specific code across QMatSuite, organized by engine family. Each entry includes:

- File path and line numbers
- Coupling type (isolated, kernel-embedded, cross-engine)
- Migration complexity assessment

---

## 2. Engine File Locations

### 2.1 Quantum ESPRESSO (QE)

**Family**: `qe`
**Pattern**: Directory-state recipe (shared outdir, prefix namespacing)

| File | Lines | Purpose | Coupling |
|------|-------|---------|----------|
| `src/qmatsuite/core/qe/` | (directory) | QE-specific modules | **Isolated** |
| `src/qmatsuite/core/qe/input_file.py` | all | Input file generation | Isolated |
| `src/qmatsuite/core/qe/output_parser.py` | all | Output parsing | Isolated |
| `src/qmatsuite/core/qe/pw_pseudopotentials.py` | all | Pseudopotential handling | Isolated |
| `src/qmatsuite/core/qe/structure_parser.py` | all | Structure I/O | Isolated |
| `src/qmatsuite/execution/handlers.py` | 68-190 | `qe_step_handler` | **Kernel-embedded** |
| `src/qmatsuite/execution/recipes.py` | 45-240 | `QERecipe` class | Kernel-embedded |
| `src/qmatsuite/workflow/registry.py` | 50-180 | QE step types | Registry (good) |

**Coupling Notes**:
- QE is the oldest engine with deepest kernel integration
- `core/qe/` directory is well-isolated
- Recipe and handler are embedded in shared modules
- Many other files have QE-specific fallback logic

### 2.2 VASP

**Family**: `vasp`
**Pattern**: Per-step workdir recipe (isolated directories, cleanup between steps)

| File | Lines | Purpose | Coupling |
|------|-------|---------|----------|
| `src/qmatsuite/engine/vasp_engine.py` | all | Engine class | **Isolated** |
| `src/qmatsuite/execution/vasp_staging.py` | all | Input staging | **Isolated** |
| `src/qmatsuite/execution/handlers.py` | 330-450 | `vasp_step_handler` | Kernel-embedded |
| `src/qmatsuite/execution/recipes.py` | 560-680 | `VASPRecipe` class | Kernel-embedded |
| `src/qmatsuite/execution/reference_resolver.py` | all | SCF reference finding | **VASP-specific** |
| `src/qmatsuite/workflow/registry.py` | 220-280 | VASP step types | Registry (good) |
| `src/qmatsuite/calculation/step_done.py` | 145-160 | `VASP_STEP_TYPES` set | **Kernel-embedded** |

**Coupling Notes**:
- Engine class is well-isolated in `engine/` directory
- `vasp_staging.py` is isolated but tightly coupled to VASP semantics
- `reference_resolver.py` appears generic but is VASP-specific (CHGCAR/WAVECAR)
- Hardcoded `VASP_STEP_TYPES` set in kernel code

### 2.3 ORCA

**Family**: `orca`
**Pattern**: Strong-chain recipe (namespace folders, chain continuations)

| File | Lines | Purpose | Coupling |
|------|-------|---------|----------|
| `src/qmatsuite/engine/orca_engine.py` | all | Engine class | **Isolated** |
| `src/qmatsuite/engine/orca_writer.py` | all | Input generation | Isolated |
| `src/qmatsuite/engine/orca_parser.py` | all | Output parsing | Isolated |
| `src/qmatsuite/execution/handlers.py` | 860-1020 | `orca_chain_handler` | Kernel-embedded |
| `src/qmatsuite/execution/recipes.py` | 410-520 | `ORCARecipe` class | Kernel-embedded |
| `src/qmatsuite/workflow/registry.py` | 320-380 | ORCA step types | Registry (good) |
| `src/qmatsuite/calculation/structure_steps.py` | 758-770 | `ORCA_STEP_TYPES` set | **Kernel-embedded** |

**Coupling Notes**:
- Engine code well-isolated in `engine/` directory
- Chain handler pattern shared with PySCF
- Hardcoded step type sets in kernel code

### 2.4 PySCF

**Family**: `pyscf`
**Pattern**: Weak-chain recipe (namespace folders, looser coupling)

| File | Lines | Purpose | Coupling |
|------|-------|---------|----------|
| `src/qmatsuite/engine/pyscf_engine.py` | all | Engine class | **Isolated** |
| `src/qmatsuite/engine/pyscf_writer.py` | all | Input generation | Isolated |
| `src/qmatsuite/engine/pyscf_parser.py` | all | Output parsing | Isolated |
| `src/qmatsuite/execution/handlers.py` | 720-850 | `pyscf_chain_handler` | Kernel-embedded |
| `src/qmatsuite/execution/recipes.py` | 300-400 | `PySCFRecipe` class | Kernel-embedded |
| `src/qmatsuite/workflow/registry.py` | 400-460 | PySCF step types | Registry (good) |
| `src/qmatsuite/calculation/structure_steps.py` | 758-765 | `PYSCF_STEP_TYPES` set | **Kernel-embedded** |

**Coupling Notes**:
- Engine code well-isolated
- Shares chain pattern with ORCA
- Hardcoded step type sets in kernel code

### 2.5 LAMMPS

**Family**: `lammps`
**Pattern**: Per-step workdir recipe (isolated directories, artifact accumulation)

| File | Lines | Purpose | Coupling |
|------|-------|---------|----------|
| `src/qmatsuite/engine/lammps_engine.py` | all | Engine class + restart resolution | **Isolated** |
| `src/qmatsuite/execution/handlers.py` | 480-620 | `lammps_step_handler` | Kernel-embedded |
| `src/qmatsuite/execution/recipes.py` | 700-780 | `LAMMPSRecipe` class | Kernel-embedded |
| `src/qmatsuite/workflow/registry.py` | 480-520 | LAMMPS step types | Registry (good) |
| `src/qmatsuite/calculation/structure_steps.py` | 772-775 | `LAMMPS_STEP_TYPES` set | **Kernel-embedded** |
| `src/qmatsuite/calculation/step_done.py` | 165-175 | `LAMMPS_STEP_TYPES` set | **Kernel-embedded** |

**Coupling Notes**:
- Engine class is well-isolated
- Contains restart artifact resolution logic
- Hardcoded step type sets in multiple kernel files

### 2.6 CP2K

**Family**: `cp2k`
**Pattern**: Per-step workdir recipe (isolated directories, artifact accumulation)

| File | Lines | Purpose | Coupling |
|------|-------|---------|----------|
| `src/qmatsuite/engine/cp2k_engine.py` | all | Engine class | **Isolated** |
| `src/qmatsuite/engine/cp2k_writer.py` | all | Input generation | Isolated |
| `src/qmatsuite/engine/cp2k_parser.py` | all | Output parsing | Isolated |
| `src/qmatsuite/execution/handlers.py` | 1100-1250 | `cp2k_step_handler` | Kernel-embedded |
| `src/qmatsuite/execution/recipes.py` | 800-900 | `CP2KRecipe` class | Kernel-embedded |
| `src/qmatsuite/workflow/registry.py` | 540-600 | CP2K step types | Registry (good) |
| `src/qmatsuite/calculation/structure_steps.py` | 778-780 | `CP2K_STEP_TYPES` set | **Kernel-embedded** |

**Coupling Notes**:
- Engine code well-isolated (follows LAMMPS pattern)
- Handler and recipe in shared kernel modules
- Hardcoded step type set in kernel code

### 2.7 Wannier90

**Family**: `w90`
**Pattern**: Chain recipe (QE-coupled)

| File | Lines | Purpose | Coupling |
|------|-------|---------|----------|
| `src/qmatsuite/core/w90/` | (directory) | W90-specific modules | **Isolated** |
| `src/qmatsuite/core/w90/input_file.py` | all | Input file generation | Isolated |
| `src/qmatsuite/core/w90/output_parser.py` | all | Output parsing | Isolated |
| `src/qmatsuite/execution/handlers.py` | 200-320 | W90 handler (QE-coupled) | **Cross-engine** |
| `src/qmatsuite/workflow/registry.py` | 600-640 | W90 step types | Registry (good) |

**Coupling Notes**:
- Isolated in `core/w90/` directory
- **Cross-engine dependency on QE** (uses QE outputs)
- Handler has QE-specific logic embedded

---

## 3. Shared/Cross-Engine Code

### 3.1 Files with Multi-Engine Logic

| File | Lines | Engines | Concern |
|------|-------|---------|---------|
| `src/qmatsuite/core/calc_identity.py` | 78-116 | ALL | **CRITICAL: prefix-based inference** |
| `src/qmatsuite/calculation/structure_steps.py` | 758-792 | ORCA, PySCF, LAMMPS, CP2K | Hardcoded step type sets |
| `src/qmatsuite/calculation/step_done.py` | 115-200 | VASP, LAMMPS | Hardcoded step type sets |
| `src/qmatsuite/workflow/generalized_steps.py` | 364-389 | ALL | MATERIALIZATION_MAP inference |
| `src/qmatsuite/execution/handlers.py` | 1335-1342 | ALL | Handler dispatch map |
| `src/qmatsuite/execution/recipes.py` | 798-827 | ALL | Recipe selection map |

### 3.2 Critical Coupling Points

**`calc_identity.py:78-116` - Engine Family Detection**

```python
def determine_engine_family(machine_type: str) -> set[str]:
    families = set()
    if machine_type.startswith("qe_") or machine_type.startswith("pw_"):
        families.add("qe")
    elif machine_type.startswith("vasp_"):
        families.add("vasp")
    elif machine_type.startswith("orca_"):
        families.add("orca")
    elif machine_type.startswith("pyscf_"):
        families.add("pyscf")
    elif machine_type.startswith("lammps_"):
        families.add("lammps")
    elif machine_type.startswith("cp2k_"):
        families.add("cp2k")
    elif machine_type.startswith("w90_"):
        families.add("w90")
    else:
        # DANGEROUS: Unknown prefix defaults to QE
        families.add("qe")
    return families
```

**Problem**: Any typo or new engine silently routes to QE.

**`structure_steps.py:758-792` - Duplicate Step Type Sets**

```python
PYSCF_STEP_TYPES = {"pyscf_scf", "pyscf_mp2", "pyscf_td", "pyscf_analysis", "pyscf_freq"}
ORCA_STEP_TYPES = {"orca_scf", "orca_hf", "orca_td", "orca_mp2", "orca_opt", "orca_freq"}
LAMMPS_STEP_TYPES = {"lammps_relax", "lammps_md"}
CP2K_STEP_TYPES = {"cp2k_scf", "cp2k_relax", "cp2k_md"}
```

**Problem**: These sets duplicate registry information and can diverge.

---

## 4. Coupling Assessment Summary

| Engine | Isolated Files | Kernel-Embedded | Cross-Engine | Migration Complexity |
|--------|----------------|-----------------|--------------|---------------------|
| QE | 4 | 3 | 0 | **High** (oldest, deepest) |
| VASP | 3 | 4 | 0 | Medium |
| ORCA | 3 | 2 | 0 | Low |
| PySCF | 3 | 2 | 0 | Low |
| LAMMPS | 1 | 3 | 0 | Medium |
| CP2K | 3 | 3 | 0 | Medium |
| W90 | 2 | 1 | 1 | **High** (QE dependency) |

---

## 5. Migration Priority Assessment

### 5.1 Easiest to Migrate (Low Risk)

1. **ORCA** - Well-isolated engine code, clean chain pattern
2. **PySCF** - Similar to ORCA, shares chain pattern

### 5.2 Medium Complexity

3. **VASP** - Good isolation but has reference resolver coupling
4. **LAMMPS** - Contains restart resolution logic
5. **CP2K** - Follows LAMMPS pattern, straightforward

### 5.3 Highest Complexity (Migrate Last)

6. **QE** - Oldest engine, deepest integration, fallback target
7. **W90** - Cross-engine QE dependency

---

## 6. Files Requiring Modification

### 6.1 Kernel Files (Must Become Engine-Agnostic)

| File | Current State | Required Change |
|------|---------------|-----------------|
| `calc_identity.py` | Prefix-based inference | Use registry lookup |
| `structure_steps.py` | Hardcoded step type sets | Query from drivers |
| `step_done.py` | Hardcoded step type sets | Query from drivers |
| `generalized_steps.py` | Hardcoded MATERIALIZATION_MAP | Driver-provided mappings |

### 6.2 Execution Layer (Consolidate into Drivers)

| File | Current State | Required Change |
|------|---------------|-----------------|
| `handlers.py` | All handlers in one file | Move to driver bundles |
| `recipes.py` | All recipes in one file | Move to driver bundles |

### 6.3 Engine Files (Become Driver Bundles)

| Current Location | New Structure |
|------------------|---------------|
| `engine/vasp_engine.py` | `drivers/vasp/driver.py` |
| `engine/orca_engine.py` | `drivers/orca/driver.py` |
| `engine/pyscf_engine.py` | `drivers/pyscf/driver.py` |
| `engine/lammps_engine.py` | `drivers/lammps/driver.py` |
| `engine/cp2k_engine.py` | `drivers/cp2k/driver.py` |
| `core/qe/` | `drivers/qe/` |
| `core/w90/` | `drivers/w90/` |
