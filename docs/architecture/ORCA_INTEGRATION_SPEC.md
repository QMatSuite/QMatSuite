# ORCA Integration Specification

**Version**: 2.0
**Date**: 2026-01-13
**Status**: Canonical Reference (Post QC Chain Namespace + Stable Token Semantics)

This document defines the complete specification for ORCA quantum chemistry engine integration in QMatSuite, including the QC chain namespace model, stable token semantics, and execution contracts.

---

## Table of Contents

1. [Terminology](#terminology)
2. [Filesystem Contract](#filesystem-contract)
3. [Stable Token Semantics](#stable-token-semantics)
4. [Execution Semantics](#execution-semantics)
5. [ORCA Input Compilation](#orca-input-compilation)
6. [Testing Strategy](#testing-strategy)
7. [Developer Quickstart](#developer-quickstart)

---

## Terminology

### Public Step Types vs Machine Step Types

**Public step types** are the generalized, engine-agnostic step type identifiers used in the UI, workflow definitions, and public APIs:
- Examples: `scf`, `hf`, `td`, `mp2`, `freq`, `nmr`
- These form the **public contract** and must remain stable across engine implementations
- Users and workflows reference these types, NOT engine-specific variants

**Machine step types** are engine-specific internal identifiers used in `step.yaml` files and stored in the database:
- Examples: `orca_scf`, `pyscf_scf`, `qe_scf`, `orca_td`, `pyscf_mp2`
- These are materialized from public types based on the selected engine
- Format: `{engine}_{public_type}` (e.g., `orca_scf` = ORCA implementation of `scf`)

**Rule**: The public API and workflow layer use ONLY public step types. Machine step types are internal implementation details.

### Chain vs Subchain

**Chain**: A complete dependency sequence rooted at an SCF calculation, including all downstream steps that depend on that SCF's wavefunction.
- Example: SCF → MP2 → NMR is one chain
- All steps in a chain share the same SCF root
- Chains are SCF-rooted (every chain starts with `scf` or `hf`)

**Subchain**: A partial chain from the SCF root up to (and including) a specific target step.
- Example: For chain [SCF, MP2, NMR], the subchain to MP2 is [SCF, MP2]
- Subchains are used in "Run Step" operations (see Execution Semantics)
- The basename of a subchain encodes its step sequence using tokens

### Namespace Folder

**Chain namespace folder**: The directory containing all artifacts for a specific SCF-rooted chain, keyed by the SCF root step's ULID suffix.

- Format: `<calc>/raw/qc_chains/scf_<suffix>/`
- Suffix: Last 6-10 characters of the SCF root step's ULID
  - Default: 6 characters (e.g., `scf_KR5DQ9`)
  - On collision: Extend to 7, 8, 9, or 10 characters
- All subchains of the same SCF root write artifacts to the same namespace folder
- Provides stable, content-addressable namespacing

### Canonical scf.gbw

**Canonical orbital file**: The hard-coded filename `scf.gbw` used for SCF wavefunction storage in ORCA.

- SCF subchains (just SCF step) produce `scf.gbw` as their wavefunction output
- Non-SCF subchains (e.g., SCF+TD, SCF+MP2) reuse `scf.gbw` via MORead
- The name `scf.gbw` is **immutable** and **must not be changed**
- No copy or symlink operations—ORCA reads `scf.gbw` directly via `%moinp "scf.gbw"`

---

## Filesystem Contract

### Directory Structure

```
<project_root>/
  calculations/
    calc_01/
      raw/
        qc_chains/
          scf_KR5DQ9/          # Chain namespace folder (SCF ULID ends with KR5DQ9)
            scf.gbw            # Canonical wavefunction file (produced by SCF subchain)
            s.inp              # SCF-only subchain input
            s.out              # SCF-only subchain output
            s.property.txt     # SCF-only subchain properties
            s_t.inp            # SCF+TD subchain input
            s_t.out            # SCF+TD subchain output
            s_t.property.txt   # SCF+TD subchain properties
            s_m2.inp           # SCF+MP2 subchain input
            s_m2.out           # SCF+MP2 subchain output
            s_m2.property.txt  # SCF+MP2 subchain properties
          scf_ABCDEF/          # Different SCF root = different namespace
            scf.gbw
            s.inp
            s.out
            s.property.txt
```

### Filename Rules

1. **Namespace folder**: `scf_<suffix>` where suffix is the last 6-10 chars of the SCF root ULID
2. **Subchain basenames**: Token path from stable token mapping (see next section)
   - SCF-only: `s`
   - SCF+TD: `s_t`
   - SCF+MP2: `s_m2`
   - SCF+MP2+NMR: `s_m2_n`
3. **Artifact files**: `<basename>.{inp,out,property.txt,gbw}`
4. **Canonical wavefunction**: Always `scf.gbw` (no prefix, no suffix, hard-coded)

### Duplicate Handling

- Subchains with the same token path (e.g., two SCF+TD runs with different TD parameters) **may overwrite** previous artifacts
- No disambiguation or versioning is required—last write wins
- This is intentional: subchain identity is defined by its step sequence (token path), not by parameter values

---

## Stable Token Semantics

### Token Mapping (Immutable Contract)

The following token mapping is **immutable once published**. New tokens may be added, but existing mappings **must never change**.

```python
PUBLIC_TYPE_TOKENS = {
    "scf": "s",     # SCF/DFT root
    "hf": "h",      # Hartree-Fock root
    "td": "t",      # TDDFT/TDHF excited states
    "mp2": "m2",    # MP2 correlation
    "freq": "f",    # Frequency/vibrational analysis
    "nmr": "n",     # NMR chemical shifts
}
```

**Location**: `src/quantumvitas/workflow/registry.py`

### Subchain Basename Generation

Subchain basenames are generated by joining tokens with underscores:

- `["scf"]` → `"s"`
- `["scf", "td"]` → `"s_t"`
- `["scf", "mp2"]` → `"s_m2"`
- `["scf", "mp2", "nmr"]` → `"s_m2_n"`
- `["hf", "td"]` → `"h_t"`

**Implementation**: `quantumvitas.workflow.registry.generate_subchain_basename()`

### Adding New Public Step Types Safely

To add a new public step type:

1. Choose a **new, unique token** that does not conflict with existing tokens
2. Add the mapping to `PUBLIC_TYPE_TOKENS` in `src/quantumvitas/workflow/registry.py`
3. Add the `token` field to all corresponding `StepTypeSpec` definitions (e.g., `orca_newtype`, `pyscf_newtype`)
4. Write unit tests to verify the token is stable (see `tests/unit/orca/test_qc_chain_tokens.py`)
5. **Never renumber or change existing tokens**—they are part of the filesystem contract

**Example**: Adding a new `ccsd` step type:
```python
# BAD: Reusing an existing token
"ccsd": "s"  # WRONG! This conflicts with "scf"

# GOOD: New unique token
"ccsd": "c2"  # OK, unique and descriptive
```

### Why Tokens Must Never Change

1. **Filesystem stability**: Changing tokens would break existing calculations on disk
2. **Reproducibility**: Token paths are part of the calculation identity
3. **No migration path**: Old calculations would become unreadable
4. **Simple contract**: Immutability eliminates entire classes of bugs

---

## Execution Semantics

### Run Calc vs Run Step

QMatSuite supports two execution modes for QC calculations:

#### Run Calc (Full Calculation)

Executes all chains in the calculation sequentially.

- Command: `qmatsuite run calc <calc_id>`
- Behavior: For each chain in the calculation's workflow:
  1. Resolve chain namespace folder: `scf_<suffix>` from SCF root ULID
  2. Execute full chain (SCF root + all downstream steps)
  3. Write all artifacts to namespace folder
- Use case: Standard workflow execution (e.g., "run all my SCF+TD calculations")

#### Run Step (Partial Chain)

Executes a partial chain from the SCF root up to (and including) a specific target step.

- Command: `qmatsuite run step <step_id>`
- Behavior:
  1. Find the chain containing `<step_id>`
  2. Extract partial chain: [SCF root, ..., target step]
  3. Resolve chain namespace folder from SCF root ULID
  4. Execute partial chain, writing artifacts with subchain basename
- Use case: Iterative development (e.g., "rerun just the MP2 step with different parameters")

**Critical Rule**: The target step **must always run**. It is never skipped, even if artifacts already exist.

- For non-SCF targets: SCF may be skipped if `scf.gbw` exists (via MORead)
- For SCF targets: **SCF must run fresh** (with `NoAutoStart`) to ensure deterministic results

### Error Cases

**No SCF root**: If a step is not part of any SCF-rooted chain, execution fails with error:
```
ValueError: Step <step_id> is not part of any SCF-rooted chain
```

**Orphan steps**: Steps that appear before the first SCF in a workflow are ignored (not part of any chain).

### Strong-Chain vs Weak-Chain

**ORCA** is a **strong-chain** engine:
- One ORCA job = one complete chain
- Chain artifacts (inp/out/property.txt/gbw) are written to the chain namespace folder
- Input file fusion: SCF + TD keywords are combined into a single input file

**PySCF** is a **weak-chain** engine internally:
- Steps are executed sequentially in-memory (one Python session)
- State is passed via in-memory objects (mf, mp2_obj) between steps
- However, PySCF shares the **same high-level chain semantics** (SCF-rooted, namespace folders, basenames)

---

## ORCA Input Compilation

### MORead Injection

When a subchain depends on a previous SCF calculation's wavefunction, the ORCA input compiler injects MORead directives:

**Example**: SCF+TD subchain (`s_t.inp`)
```orca
# Chain: scf_KR5DQ9/s_t
# Generated by QMatSuite

! B3LYP def2-SVP TightSCF MORead

%moinp "scf.gbw"

%tddft
  NRoots 5
  TDA true
end

* xyz 0 1
O   0.000000   0.000000   0.117300
H   0.000000   0.756950  -0.469200
H   0.000000  -0.756950  -0.469200
*
```

**Key elements**:
1. `MORead` keyword tells ORCA to read orbitals from an external file
2. `%moinp "scf.gbw"` specifies the canonical wavefunction file (hard-coded name)
3. No copy or symlink—ORCA reads `scf.gbw` directly from the current directory (chain namespace folder)

### NoAutoStart for Fresh SCF

When running an SCF subchain (target step = SCF), the input compiler adds `NoAutoStart`:

**Example**: Fresh SCF run (`s.inp`)
```orca
# Chain: scf_KR5DQ9/s
# Generated by QMatSuite

! B3LYP def2-SVP TightSCF NoAutoStart

* xyz 0 1
O   0.000000   0.000000   0.117300
H   0.000000   0.756950  -0.469200
H   0.000000  -0.756950  -0.469200
*
```

**Why NoAutoStart**:
- Prevents ORCA from automatically reading old `scf.gbw` files
- Ensures deterministic, reproducible SCF calculations
- Required for "Run Step" on SCF targets (force recomputation)

### Input Compiler Implementation

**Location**: `src/quantumvitas/engines/orca/input_compiler.py`

```python
def compile(
    self,
    chain: QCChain,
    molecule: MoleculeLike,
    fresh: bool = False,
    moread_file: Optional[str] = None,
) -> str:
    # ...
    if fresh:
        keywords.add("NoAutoStart")

    if moread_file:
        keywords.add("MORead")
        blocks["moinp"] = f'"{moread_file}"'
    # ...
```

**Constant**: `CANONICAL_GBW_FILE = "scf.gbw"` (immutable)

---

## Testing Strategy

### Unit Tests (No ORCA Binary Required)

**Location**: `tests/unit/orca/`

- **Property parser**: `test_property_parser.py` (14 tests - parsing .property.txt files)
- **Chain detection**: `test_chain_detection.py` (14 tests - QCChain construction)
- **Input compiler**: `test_input_compiler.py` (20 tests - input file generation, MORead injection)
- **Token semantics**: `test_qc_chain_tokens.py` (32 tests - stable token mapping, basename generation)
- **ORCA engine**: `test_orca_engine.py` (9 tests - mocked engine tests)
- **Chain base**: `test_qc_engine_base.py` (18 tests - chain detection, partial chains)

**Run command**:
```bash
pytest tests/unit/orca/ -v
```

**Expected**: 107 tests pass (no ORCA binary needed)

### Integration Tests (Require ORCA Binary)

**Location**: `tests/integration/orca/`

- **ORCA execution**: `test_orca_execution.py` (10 tests - actual ORCA runs)
- **System integration**: `test_system_integration.py` (8 tests - end-to-end chains, property extraction)

**ORCA binary location** (this machine):
```
/Users/hh7465/QMatSuite/.qmatsuite/engines/orca/orca_6_1_1_macosx_arm64_openmpi411/orca
```

**Run command**:
```bash
# Set environment variable (optional - bundled ORCA is auto-detected)
export QMATSUITE_ORCA_BIN=/Users/hh7465/QMatSuite/.qmatsuite/engines/orca/orca_6_1_1_macosx_arm64_openmpi411/orca

# Run ORCA integration tests
pytest tests/integration/orca/ -v -m integration
```

**Expected**: 18 tests pass (requires ORCA binary)

**Note**: Integration tests use the resolver (`quantumvitas.core.engines.orca_resolver.resolve_orca_bin()`) which automatically detects bundled ORCA. Setting `QMATSUITE_ORCA_BIN` is optional but recommended for explicit control.

### PySCF Regression Tests

**Location**: `tests/integration/test_pyscf_phase3c.py`

**Run command**:
```bash
pytest tests/integration/test_pyscf_phase3c.py -v
```

**Expected**: 5 tests pass

**Purpose**: Verify PySCF MP2 chain execution (one-session model) works correctly after ORCA integration changes.

### Focused Testing Philosophy

We deliberately avoid full-suite test runs to keep iteration fast:

1. Run **unit tests** during development (fast, no external dependencies)
2. Run **focused integration tests** when validating ORCA behavior
3. Run **focused PySCF tests** when changes touch shared chain code
4. Run **full suite** only in CI or before major releases

---

## Developer Quickstart

### Prerequisites

- QMatSuite installed and activated venv
- ORCA 6.x bundled at `.qmatsuite/engines/orca/orca_6_1_1_macosx_arm64_openmpi411/`
- pytest installed (in venv)

### Quick Verification

**1. Verify ORCA detection**:
```bash
python -c "
from quantumvitas.core.engines.orca_resolver import resolve_orca_bin
print('ORCA found at:', resolve_orca_bin())
"
```

Expected output:
```
ORCA found at: /Users/hh7465/QMatSuite/.qmatsuite/engines/orca/orca_6_1_1_macosx_arm64_openmpi411
```

**2. Run ORCA unit tests** (fast, ~5 seconds):
```bash
pytest tests/unit/orca/ -v --tb=short
```

Expected: 107 passed

**3. Run ORCA integration tests** (~20-30 seconds):
```bash
# Optional: set explicit ORCA binary path
export QMATSUITE_ORCA_BIN=/Users/hh7465/QMatSuite/.qmatsuite/engines/orca/orca_6_1_1_macosx_arm64_openmpi411/orca

# Run integration tests
pytest tests/integration/orca/ -v -m integration --tb=short
```

Expected: 18 passed

**4. Verify PySCF not broken** (~15 seconds):
```bash
pytest tests/integration/test_pyscf_phase3c.py -v --tb=short
```

Expected: 5 passed

**5. Test token semantics**:
```bash
pytest tests/unit/orca/test_qc_chain_tokens.py -v
```

Expected: 32 passed

### Common Workflows

**Adding a new ORCA test**:
1. Add test to `tests/unit/orca/` or `tests/integration/orca/`
2. Run focused test: `pytest tests/unit/orca/test_mytest.py -v`
3. Run full ORCA unit suite: `pytest tests/unit/orca/ -v`

**Debugging ORCA execution**:
1. Run single test with verbose output: `pytest tests/integration/orca/test_orca_execution.py::TestORCAExecution::test_scf_execution -vv`
2. Inspect temp directory artifacts: test creates files in `tmp_path` (pytest manages cleanup)
3. Check ORCA output files: `<tmp_path>/chain01_scf.out`

**Modifying token mapping** (DON'T DO THIS without review):
1. Tokens are **immutable**—changing them breaks filesystem contract
2. Adding new tokens is OK, see "Adding New Public Step Types Safely"
3. Any token change requires migration plan and backward compatibility

---

## Appendix: Key Implementation Files

### Core Engine

- `src/quantumvitas/engine/orca_engine.py` - ORCA engine implementation
- `src/quantumvitas/engines/orca/input_compiler.py` - Input file generation
- `src/quantumvitas/engines/orca/property_parser.py` - Property file parsing
- `src/quantumvitas/core/engines/orca_resolver.py` - ORCA binary resolution

### Chain Infrastructure

- `src/quantumvitas/engine/qc_engine_base.py` - QCChain dataclass, chain detection
- `src/quantumvitas/workflow/registry.py` - Step type registry, token mapping

### Configuration

- `pytest.ini` - Test markers (`integration`, `orca`)
- `.qmatsuite/engines/orca/` - Bundled ORCA installation

---

## Document History

- **2026-01-13 v2.0**: Complete rewrite after QC Chain Namespace + Stable Token Semantics implementation
  - Added canonical terminology section
  - Added filesystem contract with namespace folders
  - Added stable token semantics (immutable)
  - Added execution semantics (Run Calc vs Run Step)
  - Added MORead + NoAutoStart documentation
  - Added comprehensive testing strategy
  - Added developer quickstart section
- **2026-01-13 v1.0**: Initial version (MVP) - Basic ORCA integration
