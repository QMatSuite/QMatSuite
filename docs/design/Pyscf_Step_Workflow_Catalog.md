# PySCF Step and Workflow Catalog for QMatSuite

**Status**: Design Document (Final Revision)  
**Engine Family**: `pyscf` (molecular quantum chemistry)  
**Architecture Version**: Phase 3C+ (Final)  
**Last Updated**: 2025-01-10 (Final Revision)

---

## 1. Concepts and Scope

### 1.1 Design Philosophy

**Step Abstraction Aligned with Physical Meaning**: Steps correspond to "things chemists actually run and look at together", not implementation details.

**Step Independence**: Steps remain independent; workflows provide physical closure. Steps do NOT enforce full physical consistency by themselves. Workflow templates define "normal" and physically meaningful paths. Users may manually assemble steps; system responds with:
- **OK**: Physically meaningful combination
- **WARNING**: Allowed but non-standard (e.g., DFT → MP2)
- **ERROR**: Blocked, meaningless physics (e.g., DFT → TDHF)

**SSOT (Single Source of Truth)**: SCF metadata (method, xc, checkpoint path) is stored in the SCF step's artifacts. Downstream steps (analysis, td, mp2, freq) **MUST NOT** duplicate this information in their step.yaml parameters. The runner infers SCF metadata from upstream step artifacts.

**Reduced Fragmentation**: Fewer, stronger steps that bundle related operations.

**Scope Boundaries (v0)**:
- **analysis**: Cheap ground-state interpretation only (dipole, populations, frontier orbitals). No expensive properties.
- **freq**: Fixed-geometry harmonic analysis only (frequencies, normal modes, ZPE, thermochemistry). **Geometry optimization is explicitly OUT of v0 scope**.
- **td**: Excited-state calculations (TDDFT/TDHF) for fixed geometries only.
- **mp2**: Post-HF correlation energy correction for fixed geometries only.

### 1.2 Workflow Categories

PySCF workflows in QMatSuite are organized into three categories based on computational dependency and restart behavior:

**Category 1: SCF → Property**
- **Pattern**: Single SCF calculation followed by a property calculation (excited states, frequencies, analysis, etc.)
- **SCF Restart**: SCF step is restartable via PySCF checkpoint file (`checkpoint.chk`)
- **Property Restart**: Property steps are **non-restartable** in v0 (always rerun)
- **Examples**: `scf_td`, `scf_freq`, `scf_analysis`

**Category 2: SCF → Post-HF Energy**
- **Pattern**: SCF calculation followed by post-Hartree-Fock correlation energy (MP2, CCSD, CCSD(T), etc.)
- **SCF Restart**: SCF step is restartable via checkpoint file
- **Post-HF Restart**: Post-HF steps are **non-restartable** in v0 (always rerun, even if theoretically equivalent)
- **Examples**: `scf_mp2` (implemented), `scf_ccsd` (v1), `scf_ccsd_t` (v1)

**Category 3: SCF → Post-HF → Property (Template-Only)**
- **Pattern**: SCF → Post-HF → Property calculation on correlated wavefunction
- **Restart Policy**: Same as Category 2 (SCF restartable, others not)
- **Constraint**: **Template-only in v0/v1** (no free lego assembly). Users can only use predefined workflows.
- **Examples**: `scf_ccsd_eom` (v1, template-only)

### 1.3 SSOT (Single Source of Truth) Rules

1. **`step.yaml` is machine code**: Contains ONLY step-specific parameters. **MUST NOT** contain:
   - IR/preset sections
   - Structure payload (atoms, coordinates, charge, spin, basis, unit)
   - Workflow metadata
   - **SCF metadata duplication** (scf_method, scf_xc, scf_chkfile) - these are inferred from upstream artifacts

2. **Structure is calc-level only**: 
   - Structure (atoms, coordinates, charge, spin, unit, ECP) is stored in `calculation.yaml` via `structure_id` reference (ULID)
   - OR stored in structure registry file referenced by `calculation.yaml`
   - `step.yaml` **MUST NOT** contain structure data (even as embedded dict)
   - **`basis` is in step.yaml parameters**: Per-molecule basis selection is calculation-specific, not structure-level

3. **SCF metadata inference** (CRITICAL):
   - SCF step (`pyscf_scf`) stores its method/xc in its own `results.json` and `checkpoint.chk`
   - Downstream steps (analysis, td, mp2, freq) **MUST NOT** have `scf_method`, `scf_xc`, `scf_chkfile` in their step.yaml parameters
   - The runner infers SCF metadata by:
     - Reading the upstream SCF step's `results.json` to get `method` and `xc` (if DFT)
     - Constructing the checkpoint path from the upstream step's artifacts directory
   - This ensures SSOT: SCF metadata lives only in the SCF step's artifacts

4. **Parameter separation**:
   - **Structure-level** (in structure resource or calculation.yaml): `atoms`, `charge`, `spin`, `unit`, `ecp`
   - **Step-level** (in step.yaml `parameters` dict): `method`, `xc`, `basis`, `conv_tol`, `max_cycle`, `init_guess`, etc. (step-specific only, no upstream metadata)

### 1.4 Restart Policy (Conservative and Robust)

**PySCF Checkpoint Policy (Conservative)**:
- **NO "mf shim"**: We do NOT inject `mo_coeff` or other attributes into a new `mf` object to create a "restored" state
- **Only supported reuse**: Load existing SCF `checkpoint.chk` as `init_guess` input to a **new** SCF calculation, then run `mf.kernel()` again to reconstruct the full `mf` object
- **Rationale**: PySCF's `chkfile.load()` provides orbitals, but PySCF best practice is to rerun the kernel to ensure consistency (especially for DFT with grid-dependent quantities)

**Restart Boundaries**:
- **SCF steps** (`pyscf_scf`): Can be skipped/restarted IF:
  - SHA hash matches (inputs unchanged)
  - `checkpoint.chk` exists and is readable
  - `supports_incremental_skip=True` (default for SCF)
- **All other PySCF steps**: **Always rerun** in v0 (even if SHA matches)
  - `supports_incremental_skip=False`
  - Rationale: Property and post-HF calculations are fast relative to SCF; rerunning ensures consistency

**No Require/Produce Graph**: We do NOT use `requires_charge_density`/`produces_charge_density` semantics. QE outdir and PySCF checkpoint behavior are too heterogeneous. Only special-case behavior:
- `pyscf_scf` produces a checkpoint (chkfile)
- Only `pyscf_scf` is restartable / skippable
- All other PySCF steps always rerun in v0

### 1.5 Artifact Contracts

**Per-step artifacts directory**: Each step writes to `raw/<step_slug>/` (or `step_artifacts/<step_slug>/`). Before each step run, clear that step's artifacts directory (keep only newest results, like QE).

**Artifact files**:
- `pyscf_scf`: 
  - `checkpoint.chk` (PySCF checkpoint file, HDF5 format)
  - `results.json` (structured results: energy, converged, method, xc, runtime, etc.)
  - `stdout.txt` (PySCF stdout log)
- All other PySCF steps:
  - `results.json` (structured results: step-specific quantities)
  - `stdout.txt` (PySCF stdout log)
  - **NO checkpoint file** (v0 policy: only SCF is restartable)

**Downstream dependency**:
- Steps that require SCF: Read `checkpoint.chk` from upstream SCF step's artifacts directory
- SCF metadata (method, xc) is read from upstream SCF step's `results.json`
- If checkpoint missing/corrupt: Fail with clear error message (do NOT auto-rerun SCF unless explicitly requested)

### 1.6 Generalized Steps are String Keys

**Public step keys are strings**: `"scf"`, `"analysis"`, `"td"`, `"mp2"`, `"freq"`, `"nmr"`, etc.

**Do NOT use enums**: Generalized steps are NOT enum values. Materialization maps public string keys → engine-specific step types.

### 1.7 Step Independence and Workflow Validation

**Steps are Dumb**: Step runners execute the computational task. They do NOT enforce physics rules or validate method compatibility.

**Workflows are Smart**: Workflow validation (at materialization/instantiation time) enforces physics rules:
- **OK**: Physically meaningful combination (e.g., HF → MP2, DFT → TD)
- **WARNING**: Allowed but non-standard (e.g., DFT → MP2). System logs warning, allows execution.
- **ERROR**: Blocked, meaningless physics (e.g., DFT → TDHF). System rejects the combination.

**Validation Location**: Workflow validation happens in the workflow service/materialization layer, NOT in step runners.

---

## 2. Core Design Decisions

### 2.1 SCF is ONE Step, with Method Parameter

**Unified SCF Step**: `pyscf_scf` remains a single step type. HF vs DFT is NOT calc-level identity and NOT separate steps.

**SCF Theory Control**:
- `method: hf | dft` (parameter in step.yaml)
- `xc: <functional>` (only if `method=dft`)

**Rationale**: HF and DFT are both single-reference mean-field methods. They share the same computational structure (SCF iteration), differ only in the exchange-correlation treatment. Separating them into different steps would fragment the abstraction without physical justification.

**PySCF Implementation**: 
- `method=hf` → `scf.RHF()` / `scf.UHF()` / `scf.ROHF()` (depending on spin)
- `method=dft` → `scf.RKS()` / `scf.UKS()` / `scf.ROKS()` (depending on spin) + `mf.xc = <functional>`

---

### 2.2 Post-HF Methods Require HF Reference

**Rule**: MP2, CCSD, CCSD(T) **REQUIRE** `scf.method == hf` for standard usage.

**Validation Behavior** (at workflow level):
- **HF → Post-HF**: OK (normal usage)
- **DFT → Post-HF**: WARNING (allowed but non-standard, expert usage). System logs warning, allows execution.
- **Error handling**: System warns but does NOT block DFT → Post-HF (user may have valid reasons)

**Rationale**: Post-HF methods are defined with respect to HF reference. DFT → post-HF is physically questionable but occasionally used in practice (e.g., double-hybrid functionals, hybrid approaches). We allow it with a warning, not a hard error.

**Documentation**: This rule must be clearly documented in workflow validation rules and step type descriptions.

---

### 2.3 TD is ONE Generalized Step, Backend Depends on SCF Reference

**Unified TD Step**: Use ONE generalized step key: `"td"` (public key).

**Runtime Backend Selection** (inferred from upstream SCF):
- If upstream SCF `method == "dft"` → TDDFT backend
- If upstream SCF `method == "hf"` → TDHF backend
- **DFT → TDHF is a HARD ERROR** (blocked at workflow validation level)

**Do NOT expose separate steps**: Do NOT expose `tddft`/`tdhf` as separate public step keys in v0. The backend selection is an implementation detail, not a step-level abstraction.

**Parameters**:
- `nroots`: Number of excited states (required)
- `tda`: Optional flag for TDA approximation (optional, default: False)
- Backend selection (TDDFT vs TDHF) is automatic based on upstream SCF method (inferred from SCF results.json)

**Rationale**: TDDFT and TDHF are both linear response theories. They differ in the reference (DFT vs HF), not in the physical operation being performed (excited states). Separating them would fragment the abstraction.

---

### 2.4 Steps Remain Independent; Workflows Provide Physical Closure

**Step Independence**: Steps do NOT enforce full physical consistency by themselves. They are independent computational units.

**Workflow Templates Define Normal Paths**: Workflow templates define "normal" and physically meaningful step sequences.

**Manual Assembly Response** (at workflow validation level):
- **OK**: Physically meaningful combination (e.g., HF → MP2, DFT → TD)
- **WARNING**: Allowed but non-standard (e.g., DFT → MP2). System logs warning, allows execution.
- **ERROR**: Blocked, meaningless physics (e.g., DFT → TDHF). System rejects the combination.

**Validation Rules**: Validation happens at workflow/materialization level, not at individual step level.

---

## 3. Proposed Step Types

### 3.1 v0 Step Types (Required)

#### 3.1.1 `pyscf_scf` (Public Key: `scf`)

**Status**: ✅ Implemented (Phase 3C)

**Machine Step Type**: `pyscf_scf`  
**Public Step Key**: `"scf"` (string key)  
**Engine**: `pyscf`  
**Executable**: `python` (PySCF runner subprocess)

**Description**: Unified SCF calculation (HF or DFT). Produces reference wavefunction/density. Only restartable step (chkfile used as init_guess, SCF kernel rerun).

**Required Inputs**:
- From structure (via `calculation.yaml`): `atoms`, `charge`, `spin`, `unit`
- From step.yaml `parameters`: `method`, `basis`, `xc` (if DFT), `conv_tol`, `max_cycle`, etc.
- Upstream artifacts: None (initial step)

**Produced Artifacts**:
- `checkpoint.chk` (PySCF checkpoint file, HDF5)
- `results.json` (structured results: MUST include `method` and `xc` fields for downstream inference)
- `stdout.txt` (PySCF stdout)

**Restartable?**: Yes (`supports_incremental_skip=True`)

**Skip Policy**: Can be skipped if:
- SHA hash matches (inputs unchanged)
- `checkpoint.chk` exists and is readable
- `supports_incremental_skip=True` (enforced by registry)

**Key Parameters** (step.yaml `parameters` dict):
```yaml
parameters:
  method: hf  # Options: "hf" or "dft" (unified SCF step)
  basis: sto-3g  # Basis set name (PySCF standard names)
  xc: pbe  # DFT functional (REQUIRED if method=dft, ignored if method=hf)
  conv_tol: 1e-9  # SCF convergence tolerance
  max_cycle: 50  # Maximum SCF iterations
  verbose: 4  # PySCF verbosity level (0-9)
  init_guess: atom  # Initial guess method (atom, chkfile, minao, etc.)
  level_shift: 0.0  # Level shift for convergence (optional)
  damping: 0.0  # Damping factor (optional)
  diis: True  # Use DIIS acceleration (optional, default True)
  density_fitting: False  # Use density fitting (optional, default False)
  auxbasis: None  # Auxiliary basis for DF (optional, default: auto)
```

**PySCF Implementation Details**:
- `method=hf`: Creates `scf.RHF()` / `scf.UHF()` / `scf.ROHF()` based on spin
- `method=dft`: Creates `scf.RKS()` / `scf.UKS()` / `scf.ROKS()` based on spin, sets `mf.xc = xc`

**Constraints / Validation**:
- `xc` parameter is REQUIRED if `method=dft`, ignored if `method=hf`
- `init_guess='chkfile'` requires `init_guess_chkfile` path parameter (handled by runner)
- Density fitting requires `auxbasis` or auto-selection

**Reference**:
- PySCF SCF docs: https://pyscf.org/user/scf.html
- Phase 3C implementation: `src/qmatsuite/engines/pyscf/runner.py`

---

#### 3.1.2 `pyscf_analysis` (Public Key: `analysis`)

**Status**: 📋 Planned (v0, Category 1)

**Machine Step Type**: `pyscf_analysis`  
**Public Step Key**: `"analysis"` (string key)  
**Engine**: `pyscf`  
**Executable**: `python` (PySCF runner subprocess)

**Description**: Cheap ground-state interpretation only. Bundle all "interpretation of ground-state wavefunction" into ONE step. Includes population analysis (Mulliken/Löwdin/Mayer if available), dipole moment, and frontier orbital summary (HOMO/LUMO, gap).

**Scope Boundary**: This step computes **cheap** properties only. No expensive calculations (e.g., no frequency calculations, no excited states).

**Rationale**: These properties are almost always run together. ORCA and other QC codes present these as a block. This avoids fragmentation into tiny steps.

**Required Inputs**:
- From structure (via `calculation.yaml`): `atoms`, `charge`, `spin`, `unit`
- From step.yaml `parameters`: `population_method` (optional)
- Upstream artifacts: **SCF `checkpoint.chk`** (required, must exist)
- **SCF metadata inference**: Runner reads upstream SCF step's `results.json` to get `method` and `xc` (if DFT). Runner constructs checkpoint path from upstream step's artifacts directory.

**Produced Artifacts**:
- `results.json` (structured results: dipole, populations, frontier orbitals)
- `stdout.txt` (PySCF stdout)
- **NO checkpoint file** (v0 policy)

**Restartable?**: No (`supports_incremental_skip=False`)

**Skip Policy**: Always rerun (even if SHA matches)

**Key Parameters** (step.yaml `parameters` dict):
```yaml
parameters:
  verbose: 4  # PySCF verbosity level
  population_method: mulliken  # Options: "mulliken", "lowdin", "mayer" (if available, optional)
```

**NOTE**: `scf_method`, `scf_xc`, `scf_chkfile` are **NOT** step.yaml parameters. They are inferred by the runner from upstream SCF step artifacts.

**Results Schema** (minimal and honest):
```json
{
  "success": true,
  "dipole": [dx, dy, dz],  # Dipole moment vector (atomic units)
  "dipole_magnitude": |d|,  # Dipole magnitude
  "population_analysis": {
    "method": "mulliken",
    "charges": [q1, q2, ...],  # Atomic charges
    "bonds": {...}  # Bond orders (if available, optional)
  },
  "frontier_orbitals": {
    "homo": -0.5234,  # HOMO energy (Hartree)
    "lumo": 0.2345,   # LUMO energy (Hartree)
    "gap": 0.7579     # HOMO-LUMO gap (Hartree)
  },
  "execution_time": 0.12,
  "pyscf_version": "2.11.0"
}
```

**Reference**:
- PySCF properties: `pyscf.prop.dipole`, `pyscf.prop.pop_analysis`

---

#### 3.1.3 `pyscf_td` (Public Key: `td`)

**Status**: 📋 Planned (v0, Category 1)

**Machine Step Type**: `pyscf_td`  
**Public Step Key**: `"td"` (string key)  
**Engine**: `pyscf`  
**Executable**: `python` (PySCF runner subprocess)

**Description**: Excited-state calculation via linear response. Backend selection (TDDFT or TDHF) is automatic based on upstream SCF method. Do NOT expose `tddft`/`tdhf` as separate public steps.

**Scope Boundary**: Fixed-geometry excited-state calculations only. No geometry optimization.

**Required Inputs**:
- From structure (via `calculation.yaml`): `atoms`, `charge`, `spin`, `unit`
- From step.yaml `parameters`: `nroots`, `tda` (optional)
- Upstream artifacts: **SCF `checkpoint.chk`** (required, must exist)
- **SCF metadata inference**: Runner reads upstream SCF step's `results.json` to get `method` and `xc` (if DFT). Runner constructs checkpoint path from upstream step's artifacts directory.

**Produced Artifacts**:
- `results.json` (structured results: excitation energies, oscillator strengths, transition dipoles)
- `stdout.txt` (PySCF stdout)
- **NO checkpoint file** (v0 policy)

**Restartable?**: No (`supports_incremental_skip=False`)

**Skip Policy**: Always rerun (even if SHA matches)

**Key Parameters** (step.yaml `parameters` dict):
```yaml
parameters:
  nroots: 10  # Number of excited states (required)
  tda: False  # Use TDA approximation (optional, default: False)
  verbose: 4  # PySCF verbosity level
  conv_tol: 1e-9  # TD convergence tolerance (optional)
  max_cycle: 50  # Maximum TD iterations (optional)
```

**NOTE**: `scf_method`, `scf_xc`, `scf_chkfile` are **NOT** step.yaml parameters. They are inferred by the runner from upstream SCF step artifacts.

**Runtime Backend Selection** (inferred from upstream SCF):
- If upstream SCF `method == "dft"` → Use TDDFT backend (`tddft.TDDFT(mf)`)
- If upstream SCF `method == "hf"` → Use TDHF backend (`tdhf.TDHF(mf)`)
- **DFT → TDHF is a HARD ERROR** (physically meaningless, blocked at workflow validation level)

**Results Schema**:
```json
{
  "success": true,
  "method": "tddft",  # or "tdhf" (backend used, inferred from SCF)
  "basis": "6-31g",
  "nstates": 10,
  "excitation_energies": [0.1234, 0.2345, ...],  # Hartree
  "oscillator_strengths": [0.0123, 0.0456, ...],
  "transition_dipoles": [[0.1, 0.2, 0.3], ...],  # Atomic units
  "energy_unit": "Hartree",
  "execution_time": 2.34,
  "pyscf_version": "2.11.0"
}
```

**Constraints / Validation** (at workflow level):
- Requires converged SCF checkpoint (must exist and be readable)
- Backend selection is automatic (not a user parameter, inferred from upstream SCF)
- DFT → TDHF is blocked (hard error at workflow validation level)

**Reference**:
- PySCF TDDFT docs: https://pyscf.org/user/tdscf.html
- Examples: `.tmp/pyscf-master/examples/tddft/00-simple_tddft.py`

---

#### 3.1.4 `pyscf_mp2` (Public Key: `mp2`)

**Status**: ✅ Implemented (Phase 3C)

**Machine Step Type**: `pyscf_mp2`  
**Public Step Key**: `"mp2"` (string key)  
**Engine**: `pyscf`  
**Executable**: `python` (PySCF runner subprocess)

**Description**: Post-HF correlation energy correction. Requires HF reference (warns if DFT at workflow validation level).

**Scope Boundary**: Fixed-geometry MP2 calculations only. No geometry optimization.

**Required Inputs**:
- From structure (via `calculation.yaml`): `atoms`, `charge`, `spin`, `unit`
- From step.yaml `parameters`: `frozen`, `density_fitting`, etc.
- Upstream artifacts: **SCF `checkpoint.chk`** (required, must exist)
- **SCF metadata inference**: Runner reads upstream SCF step's `results.json` to get `method` and `xc` (if DFT). Runner constructs checkpoint path from upstream step's artifacts directory.

**Produced Artifacts**:
- `results.json` (structured results: `energy_mp2_correlation`, `energy_total`, etc.)
- `stdout.txt` (PySCF stdout)
- **NO checkpoint file** (v0 policy)

**Restartable?**: No (`supports_incremental_skip=False`)

**Skip Policy**: Always rerun (even if SHA matches)

**Key Parameters** (step.yaml `parameters` dict):
```yaml
parameters:
  verbose: 4  # PySCF verbosity level
  frozen: 0  # Number of frozen core orbitals (optional, default 0)
  density_fitting: False  # Use density fitting for MP2 (optional)
  auxbasis: None  # Auxiliary basis for DF-MP2 (optional)
```

**NOTE**: `scf_method`, `scf_xc`, `scf_chkfile` are **NOT** step.yaml parameters. They are inferred by the runner from upstream SCF step artifacts.

**Constraints / Validation** (at workflow level):
- Requires converged SCF checkpoint (must exist and be readable)
- **HF → MP2**: OK (normal usage, no warning)
- **DFT → MP2**: WARNING (allowed but non-standard, expert usage). Workflow validation logs warning, allows execution.
- If checkpoint missing/corrupt: Fail with clear error (do not auto-rerun SCF)

**Reference**:
- PySCF MP2 docs: https://pyscf.org/user/mp.html
- Examples: `.tmp/pyscf-master/examples/mp/00-simple_mp2.py`
- Phase 3C implementation: `src/qmatsuite/engines/pyscf/runner.py::run_mp2`

---

#### 3.1.5 `pyscf_freq` (Public Key: `freq`)

**Status**: 📋 Planned (v0, Category 1)

**Machine Step Type**: `pyscf_freq`  
**Public Step Key**: `"freq"` (string key)  
**Engine**: `pyscf`  
**Executable**: `python` (PySCF runner subprocess)

**Description**: Fixed-geometry harmonic frequencies, zero-point energy, and thermochemistry. Chosen for v0 over NMR because frequencies are more fundamental (vibrational spectroscopy, thermochemistry, etc.).

**Scope Boundary**: **Fixed-geometry harmonic analysis only**. Geometry optimization is **explicitly OUT of v0 scope**. This step computes frequencies for a fixed molecular geometry (from the SCF step).

**Rationale for v0 Selection**: Frequencies are essential for:
- Vibrational spectroscopy
- Thermochemistry
- Force constants (can be used for geometry optimization in v1+, but optimization itself is not in v0)

NMR is deferred to v1 as it's more specialized.

**Required Inputs**:
- From structure (via `calculation.yaml`): `atoms`, `charge`, `spin`, `unit`
- From step.yaml `parameters`: `thermo`, `temperature`, `pressure`
- Upstream artifacts: **SCF `checkpoint.chk`** (required, must exist)
- **SCF metadata inference**: Runner reads upstream SCF step's `results.json` to get `method` and `xc` (if DFT). Runner constructs checkpoint path from upstream step's artifacts directory.

**Produced Artifacts**:
- `results.json` (structured results: frequencies, normal modes, intensities, ZPE, thermochemistry)
- `stdout.txt` (PySCF stdout)
- **NO checkpoint file** (v0 policy)

**Restartable?**: No (`supports_incremental_skip=False`)

**Skip Policy**: Always rerun (even if SHA matches)

**Key Parameters** (step.yaml `parameters` dict):
```yaml
parameters:
  verbose: 4  # PySCF verbosity level
  thermo: False  # Compute thermochemistry (optional, default: False)
  temperature: 298.15  # Temperature for thermochemistry (K, optional)
  pressure: 101325  # Pressure for thermochemistry (Pa, optional)
```

**NOTE**: `scf_method`, `scf_xc`, `scf_chkfile` are **NOT** step.yaml parameters. They are inferred by the runner from upstream SCF step artifacts. `atmlst` (partial Hessian) is deferred to v1.

**Results Schema** (minimal and honest):
```json
{
  "success": true,
  "method": "hessian",
  "basis": "6-31g",
  "n_atoms": 3,
  "frequencies": [1654.3, 3832.1, 3942.5, ...],  # cm^-1
  "frequencies_unit": "cm^-1",
  "normal_modes": [[[0.1, 0.2, 0.3], ...], ...],  # Shape: [nmodes, natoms, 3]
  "intensities": [12.3, 45.6, ...],  # IR intensities (best-effort, optional)
  "zpe": 0.0234,  # Zero-point energy (Hartree, if computed)
  "zpe_unit": "Hartree",
  "thermochemistry": {  # Only if thermo=True
    "temperature": 298.15,
    "pressure": 101325,
    "rot_const": [20.5, 13.2, 8.7],
    "E_0K": -74.9872,
    "E_tot": -74.9654,
    "H_tot": -74.9645,
    "G_tot": -74.9789,
    "Cv_tot": 0.0012
  },
  "execution_time": 5.67,
  "pyscf_version": "2.11.0"
}
```

**Note on Intensities**: IR/Raman intensities are marked as "best-effort" (optional). They may not be available for all methods/basis sets. Do NOT promise quantities that are not robust.

**Constraints / Validation**:
- Requires converged SCF checkpoint
- Hessian calculation can be expensive (scales as O(N²) with number of atoms)
- Thermochemistry requires full Hessian (cannot use `atmlst`)
- **Geometry optimization is explicitly OUT of v0 scope** (this step computes frequencies for fixed geometry only)

**Reference**:
- PySCF Hessian docs: https://pyscf.org/user/grad.html#hessian
- Examples:
  - `.tmp/pyscf-master/examples/hessian/01-scf_hessian.py`
  - `.tmp/pyscf-master/examples/hessian/10-thermochemistry.py`

---

### 3.2 v1 Step Types (Deferred)

#### 3.2.1 `pyscf_nmr` (Public Key: `nmr`)

**Status**: 📋 Planned (v1, Category 1)

**Machine Step Type**: `pyscf_nmr`  
**Public Step Key**: `"nmr"` (string key)  
**Engine**: `pyscf`

**Description**: NMR shielding and chemical shifts. Deferred to v1 in favor of frequencies for v0.

**Reference**:
- Examples: `.tmp/pyscf-master/examples/nmr/crco6-nr-msc.py`

---

#### 3.2.2 `pyscf_ccsd` / `pyscf_ccsd_t` / `pyscf_eom_ccsd`

**Status**: 📋 Planned (v1, Category 2/3)

See roadmap for details. Deferred to v1 to prioritize property workflows in v0.

---

### 3.3 Summary Table: Step Types

| Public Key | Machine Type | Category | v0/v1 | Restartable? | Requires SCF Checkpoint? |
|------------|--------------|----------|-------|--------------|--------------------------|
| `scf` | `pyscf_scf` | N/A (initial) | v0 ✅ | Yes | No |
| `analysis` | `pyscf_analysis` | 1 | v0 📋 | No | Yes |
| `td` | `pyscf_td` | 1 | v0 📋 | No | Yes |
| `mp2` | `pyscf_mp2` | 2 | v0 ✅ | No | Yes |
| `freq` | `pyscf_freq` | 1 | v0 📋 | No | Yes |
| `nmr` | `pyscf_nmr` | 1 | v1 📋 | No | Yes |
| `ccsd` | `pyscf_ccsd` | 2 | v1 📋 | No | Yes |
| `ccsd_t` | `pyscf_ccsd_t` | 2 | v1 📋 | No | Yes |
| `eom_ccsd` | `pyscf_eom_ccsd` | 3 (template-only) | v1 📋 | No | Yes (via CCSD) |

---

## 4. Proposed Workflows (Generalized Templates)

### 4.1 v0 Workflows (Exactly These Five)

#### 4.1.1 `scf` (Already Implemented)

**Status**: ✅ Implemented (Phase 3C)

**Public Step Sequence**: `("scf",)`

**Materialization** (for `engine_family="pyscf"`):
- `scf` → `pyscf_scf`

**UI Display Name**: "SCF"

**Constraints / Prerequisites**: None (initial step)

**Incremental Behavior**: SCF can be skipped if SHA matches AND `checkpoint.chk` exists

---

#### 4.1.2 `scf_analysis` (Planned for v0)

**Status**: 📋 Planned (v0, Category 1)

**Public Step Sequence**: `("scf", "analysis")`

**Materialization** (for `engine_family="pyscf"`):
- `scf` → `pyscf_scf`
- `analysis` → `pyscf_analysis`

**UI Display Name**: "SCF + Analysis"

**Constraints / Prerequisites**:
- Step 1 (SCF) must converge
- Step 2 (analysis) requires SCF checkpoint

**Validation**: No special validation rules (analysis works with any SCF method)

**Incremental Behavior**:
- SCF can be skipped if SHA matches AND checkpoint exists
- Analysis always reruns (even if SHA matches)

---

#### 4.1.3 `scf_td` (Planned for v0)

**Status**: 📋 Planned (v0, Category 1)

**Public Step Sequence**: `("scf", "td")`

**Materialization** (for `engine_family="pyscf"`):
- `scf` → `pyscf_scf`
- `td` → `pyscf_td`

**UI Display Name**: "SCF + Excited States"

**Constraints / Prerequisites**:
- Step 1 (SCF) must converge (typically DFT SCF, but HF also supported)
- Step 2 (td) requires SCF checkpoint
- Backend selection (TDDFT vs TDHF) is automatic based on upstream SCF method

**Validation Rules** (at workflow level):
- DFT → TD: OK (uses TDDFT backend automatically)
- HF → TD: OK (uses TDHF backend automatically)
- **DFT → TDHF**: ERROR (blocked, meaningless physics). Workflow validation rejects this combination.

**Incremental Behavior**:
- SCF can be skipped if SHA matches AND checkpoint exists
- TD always reruns (even if SHA matches)

---

#### 4.1.4 `scf_mp2` (Already Implemented)

**Status**: ✅ Implemented (Phase 3C)

**Public Step Sequence**: `("scf", "mp2")`

**Materialization** (for `engine_family="pyscf"`):
- `scf` → `pyscf_scf`
- `mp2` → `pyscf_mp2`

**UI Display Name**: "SCF + MP2"

**Constraints / Prerequisites**: 
- Step 1 (SCF) must converge
- Step 2 (MP2) requires SCF checkpoint

**Incremental Behavior**: 
- SCF can be skipped if SHA matches AND checkpoint exists
- MP2 always reruns (even if SHA matches)

**Validation Rules** (at workflow level):
- **HF → MP2**: OK (normal usage, no warning)
- **DFT → MP2**: WARNING (allowed but non-standard, expert usage). Workflow validation logs warning, allows execution.

---

#### 4.1.5 `scf_freq` (Planned for v0)

**Status**: 📋 Planned (v0, Category 1)

**Public Step Sequence**: `("scf", "freq")`

**Materialization** (for `engine_family="pyscf"`):
- `scf` → `pyscf_scf`
- `freq` → `pyscf_freq`

**UI Display Name**: "SCF + Frequencies"

**Constraints / Prerequisites**:
- Step 1 (SCF) must converge
- Step 2 (freq) requires SCF checkpoint

**Validation**: No special validation rules (freq works with any SCF method)

**Incremental Behavior**:
- SCF can be skipped if SHA matches AND checkpoint exists
- Freq always reruns (even if SHA matches)

---

### 4.2 v1+ Workflows (Deferred)

All other workflows (CCSD, CCSD(T), EOM-CCSD, NMR, etc.) are deferred to v1+.

---

### 4.3 Summary Table: Workflows

| Workflow ID | Step Sequence | Category | v0/v1 | UI Display Name |
|-------------|---------------|----------|-------|-----------------|
| `scf` | `("scf",)` | N/A | v0 ✅ | "SCF" |
| `scf_analysis` | `("scf", "analysis")` | 1 | v0 📋 | "SCF + Analysis" |
| `scf_td` | `("scf", "td")` | 1 | v0 📋 | "SCF + Excited States" |
| `scf_mp2` | `("scf", "mp2")` | 2 | v0 ✅ | "SCF + MP2" |
| `scf_freq` | `("scf", "freq")` | 1 | v0 📋 | "SCF + Frequencies" |

---

## 5. Validation Rules

### 5.1 Step-Level Validation (Minimal)

**SCF Step**:
- `xc` parameter is REQUIRED if `method=dft`, ignored if `method=hf`
- `basis` must be valid PySCF basis set name (runtime validation)

**Analysis Step**:
- No step-level validation (works with any SCF method)

**TD Step**:
- No step-level validation (backend selection is automatic, inferred from upstream SCF)

**MP2 Step**:
- No step-level validation (works with any SCF method, but workflow validation warns if DFT)

**Freq Step**:
- No step-level validation (works with any SCF method)

### 5.2 Workflow-Level Validation (Physics Rules)

**Location**: Workflow validation happens in the workflow service/materialization layer (`src/qmatsuite/workflow/templates.py` or workflow service).

**Category 1 Workflows (SCF → Property)**:
- All property steps require converged SCF checkpoint
- Backend selection (TDDFT vs TDHF) is automatic based on upstream SCF method (inferred from SCF results.json)
- **DFT → TDHF**: ERROR (blocked, meaningless physics). Workflow validation rejects this combination.

**Category 2 Workflows (SCF → Post-HF)**:
- Post-HF steps require HF reference for standard usage (warn if DFT at workflow validation level)
- **HF → MP2/CCSD**: OK (normal usage, no warning)
- **DFT → MP2/CCSD**: WARNING (allowed but non-standard). Workflow validation logs warning, allows execution.

**Category 3 Workflows (SCF → Post-HF → Property)**:
- Template-only (no free lego assembly in v0/v1)
- Must use predefined workflow templates

### 5.3 Manual Assembly Response (Workflow Validation)

When users manually assemble steps (not using predefined workflow templates), workflow validation responds with:

- **OK**: Physically meaningful combination (e.g., HF → MP2, DFT → TD)
  - System allows execution, no warnings
- **WARNING**: Allowed but non-standard (e.g., DFT → MP2)
  - System logs warning message, allows execution
  - Warning is visible to user but does not block execution
- **ERROR**: Blocked, meaningless physics (e.g., DFT → TDHF)
  - System rejects the combination, raises error
  - User must use a valid combination

---

## 6. Result Schema & Testing Policy

### 6.1 Result Schemas: Minimal and Honest

**Principle**: Do NOT promise quantities that are not robust across methods/versions.

**Examples**:
- `freq` results: Frequencies and ZPE are required. IR/Raman intensities are optional (best-effort, not guaranteed).
- `analysis` results: Dipole and frontier orbitals are required. Bond orders may be optional depending on method.

**Schema Structure**: Each step's `results.json` must clearly distinguish:
- **Required fields**: Always present and reliable
- **Optional fields**: Best-effort, may be missing for some methods/basis sets

### 6.2 Numeric Validation Strategy (STRICT)

**For each MAJOR CATEGORY** (scf, mp2, td, freq), choose **ONE** representative test system and use a **GOLDEN VALUE** from an external authoritative source.

**Primary Authoritative Source**: PySCF Tutorial (`<HOME>/QMatSuite/.tmp/PySCF_Tutorial-master/user_guide.ipynb` and `dev_guide.ipynb`)

**Secondary Sources** (if tutorial values unavailable):
- PySCF official examples (`.tmp/pyscf-master/examples/`)
- ORCA official tutorial/manual
- Published benchmarks (with citations)

**Do NOT use "self-generated" values as golden references**. Always validate against external authoritative sources.

**Validation Approach**:
1. Choose **ONE** representative test system per category
2. Use golden value from authoritative source (PySCF Tutorial is primary)
3. Validate numeric values WITH TOLERANCE (e.g., ±0.0001 Hartree for energies, ±1 cm⁻¹ for frequencies)
4. Other tests should validate:
   - Presence/structure of results
   - Physical ordering (e.g., MP2 energy < SCF energy for stable systems)
   - Correct detection of method/backend (TDDFT vs TDHF)

**Example Test Systems with Golden Reference Values** (from PySCF Tutorial: `<HOME>/QMatSuite/.tmp/PySCF_Tutorial-master/`):

- **SCF (HF)**: 
  - H2/cc-pVDZ RHF: **-1.1287000935564406 Hartree** (from `user_guide.ipynb` Cell 4)
  - OH/cc-pVDZ UHF: **-75.3938226865 Hartree** (from `user_guide.ipynb` Cell 10)
  - OH/cc-pVDZ RHF: **-75.3899856282 Hartree** (from `user_guide.ipynb` Cell 10)
  - Water dimer/cc-pVDZ HF: **-152.06253625 Hartree** (from `user_guide.ipynb` Cell 21)
- **SCF (DFT)**: 
  - (To be added from tutorial when available)
- **MP2**: 
  - (To be added from tutorial when available)
- **TD**: 
  - (To be added from tutorial when available)
- **Freq**: 
  - (To be added from tutorial when available)
- **Analysis (Properties)**:
  - OH/cc-pVDZ UHF properties (from `user_guide.ipynb` Cell 12):
    - Dipole moment: [0.00000, 0.00000, 1.80400] (atomic units)
    - S^2: 0.75461173279801885
    - 2S+1: 2.0046064280032816
    - Mulliken charges: O: -0.323214025599, H: 0.323214025599

**Validation Tolerances**:
- Energy comparisons: ±0.0001 Hartree (for tutorial reference systems)
- Property comparisons: ±0.01 (relative tolerance for dipole, populations)
- Frequency comparisons: ±1 cm⁻¹ (for tutorial reference systems)

---

## 7. Parameter Extraction

### 7.1 Where Parameters Live

**Structure-Level Parameters** (in structure resource or `calculation.yaml`):
- `atoms`: List of atoms with coordinates `[{element: "O", x: 0.0, y: 0.0, z: 0.117790}, ...]`
- `charge`: Integer molecular charge (default: 0)
- `spin`: Integer spin multiplicity (2S, PySCF convention; default: 0 for singlet)
- `unit`: String unit for coordinates (`"Angstrom"` or `"Bohr"`, default: `"Angstrom"`)
- `ecp`: Optional ECP specification (dictionary mapping elements to ECP names)

**Step-Level Parameters** (in `step.yaml` `parameters` dict):
- **SCF step**: `method`, `basis`, `xc` (if DFT), `conv_tol`, `max_cycle`, `init_guess`, etc.
- **Downstream steps** (analysis, td, mp2, freq): Step-specific parameters only (e.g., `nroots`, `frozen`, `thermo`). **NO `scf_method`, `scf_xc`, `scf_chkfile`** (these are inferred by runner from upstream artifacts).

### 7.2 SCF-Level Parameters

**Key Parameters** (from PySCF SCF docs: https://pyscf.org/user/scf.html):
- `method`: `"hf"` or `"dft"` (REQUIRED)
- `basis`: Basis set name (REQUIRED)
- `xc`: DFT functional (REQUIRED if `method=dft`, ignored if `method=hf`)
- `conv_tol`: SCF convergence tolerance (default: `1e-9` for HF, `1e-7` for DFT)
- `max_cycle`: Maximum SCF iterations (default: 50)
- `init_guess`: Initial guess method (`"atom"`, `"chkfile"`, `"minao"`, `"huckel"`, etc.)
- `level_shift`: Level shift for convergence (optional, default: 0.0)
- `damping`: Damping factor (optional, default: 0.0)
- `diis`: Use DIIS acceleration (optional, default: True)
- `density_fitting`: Use density fitting (optional, default: False)
- `auxbasis`: Auxiliary basis for DF (optional, default: auto-selected)

### 7.3 Post-HF Parameters

**Key Parameters** (from PySCF MP2/CC docs: https://pyscf.org/user/mp.html, https://pyscf.org/user/cc.html):
- `frozen`: Number of frozen core orbitals (int, default: 0)
- `conv_tol`: Convergence tolerance (float, default: `1e-8` for CC, `1e-10` for MP2)
- `max_cycle`: Maximum iterations (int, default: 50 for CC, N/A for MP2)
- `density_fitting`: Use density fitting (bool, default: False)
- `auxbasis`: Auxiliary basis for DF (str, default: auto-selected)

### 7.4 TD Parameters

**Key Parameters** (from PySCF TDDFT docs: https://pyscf.org/user/tdscf.html):
- `nroots`: Number of excited states (int, required)
- `tda`: Use TDA approximation (bool, optional, default: False)
- `conv_tol`: Convergence tolerance (float, optional, default: `1e-9`)
- `max_cycle`: Maximum iterations (int, optional, default: 50)

**Note**: Backend selection (TDDFT vs TDHF) is automatic based on upstream SCF method (inferred from SCF results.json), not a parameter.

### 7.5 Frequency Parameters

**Key Parameters** (from PySCF Hessian docs: https://pyscf.org/user/grad.html#hessian):
- `thermo`: Compute thermochemistry (bool, default: False)
- `temperature`: Temperature for thermochemistry (float, K, default: 298.15)
- `pressure`: Pressure for thermochemistry (float, Pa, default: 101325)

**Note**: `atmlst` (partial Hessian) is deferred to v1.

---

## 8. References

### 8.1 PySCF Official Documentation

- **PySCF "How to use PySCF"**: https://pyscf.org/user/using.html
- **PySCF Quickstart**: https://pyscf.org/quickstart.html
- **SCF methods**: https://pyscf.org/user/scf.html
- **MP2 guide**: https://pyscf.org/user/mp.html
- **CC guide**: https://pyscf.org/user/cc.html
- **TDDFT guide**: https://pyscf.org/user/tdscf.html
- **Gradients/Hessian**: https://pyscf.org/user/grad.html
- **Feature list**: https://pyscf.org/features.html

### 8.2 PySCF Tutorial (Primary Reference for Golden Values)

- **PySCF Tutorial Repository**: `<HOME>/QMatSuite/.tmp/PySCF_Tutorial-master/`
- **User Guide**: `user_guide.ipynb` (contains verified output values for SCF calculations)
- **Developer Guide**: `dev_guide.ipynb` (detailed PySCF API usage)
- **Key Reference Outputs**:
  - H2/cc-pVDZ RHF: -1.1287000935564406 Hartree
  - OH/cc-pVDZ UHF: -75.3938226865 Hartree
  - OH/cc-pVDZ RHF: -75.3899856282 Hartree
  - Water dimer/cc-pVDZ HF: -152.06253625 Hartree
  - OH properties: dipole, S^2, Mulliken populations

### 8.3 Local Examples

- **PySCF examples directory**: `<HOME>/QMatSuite/.tmp/pyscf-master/examples/`
- Key examples referenced in step type descriptions

### 8.4 QMatSuite Architecture

- **Phase 3C Implementation Plan**: `docs/design/PHASE3C_PLAN.md`
- **SCHEMA.md**: `docs/SCHEMA.md` (structure and step.yaml format)
- **Workflow Materialization**: `src/qmatsuite/workflow/generalized_steps.py`
- **Step Type Registry**: `src/qmatsuite/workflow/registry.py`
- **PySCF Runner**: `src/qmatsuite/engines/pyscf/runner.py`

---

**Document Status**: ✅ Complete (Final Revision)  
**Next Step**: Review and implement Phase PySCF Roadmap (see `PHASE_PYSCF_ROADMAP.md`)
