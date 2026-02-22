# Phase PySCF Incremental Implementation Roadmap

**Status**: Planning Document (Revised)  
**Engine Family**: `pyscf` (molecular quantum chemistry)  
**Baseline**: Phase 3C (SCF + MP2 workflows implemented)  
**Last Updated**: 2025-01-10 (Revised)

---

## Overview

This document provides an incremental, checkable roadmap for expanding PySCF support in QMatSuite from the current Phase 3C baseline (SCF + MP2) to a comprehensive molecular quantum chemistry workflow system.

**Baseline (Phase 3C)**:
- ✅ `pyscf_scf` step type (public key: `scf`)
- ✅ `pyscf_mp2` step type (public key: `mp2`)
- ✅ `scf` workflow (single SCF step)
- ✅ `scf_mp2` workflow (SCF → MP2)
- ✅ Conservative restart policy (SCF restartable via checkpoint, MP2 always rerun)
- ✅ SSOT architecture (step.yaml contains only PySCF parameters, no structure)
- ✅ Incremental skip gating (`supports_incremental_skip` flag)

**Goal**: Incrementally add Category 1 (SCF → Property) workflows and refine Category 2 (SCF → Post-HF) workflows, maintaining architectural constraints and test coverage.

**Milestone Order**: SIMPLE → COMPLEX
- M0: SCF (HF/DFT unified) + restart semantics
- M1: Analysis (bundle population, dipole, frontier orbitals)
- M2: TD (unified TDDFT/TDHF, backend selection)
- M3: MP2 (post-HF energy correction)
- M4: Freq (harmonic frequencies + thermochemistry)
- M5: Deferred extensions (CCSD, EOM-CCSD, NMR, etc.)

---

## Milestone M0: SCF (HF/DFT Unified) + Restart Semantics

**Status**: ✅ Implemented (Phase 3C, verification required)

**Goal**: Verify existing Phase 3C implementation matches unified SCF design and conservative restart policy.

**Key Design Decision**: SCF is ONE step with `method: hf | dft` parameter. HF vs DFT is NOT calc-level identity and NOT separate steps.

**Tasks**:

### Verification Tasks
- [ ] Verify `pyscf_scf` uses unified `method` parameter (`hf` or `dft`)
  - Verify step.yaml parameters: `method`, `xc` (if `method=dft`)
  - Verify PySCF implementation: `method=hf` → RHF/UHF/ROHF; `method=dft` → RKS/UKS/ROKS + xc
- [ ] Verify checkpoint behavior matches conservative policy (no mf shim, only init_guess from chkfile)
- [ ] Verify `pyscf_scf` always reruns (even if SHA matches, but checkpoint allows skip)
- [ ] Verify `step.yaml` does NOT contain structure payload
- [ ] Verify structure (atoms, charge, spin, unit) comes from `calculation.yaml` (via structure_id)
- [ ] Verify artifacts layout: per-step artifacts directory, cleared before each step run
- [ ] Verify `basis` is in step.yaml parameters (not structure resource)
- [ ] Run integration tests: `pytest tests/integration/test_pyscf_execution.py -v`

**Steps Introduced**:
- `pyscf_scf` (unified HF/DFT step)

**Workflows Introduced**:
- `scf` (single SCF step)

**Validation Rules Added**:
- `xc` parameter is REQUIRED if `method=dft`, ignored if `method=hf`
- `basis` must be valid PySCF basis set name (runtime validation)

**Tests Added**:
- Unit tests: SCF step type spec, parameter defaults, step.yaml structure
- Integration tests: Run SCF with `method=hf` and `method=dft`, verify checkpoint behavior, verify restart semantics
- **Numeric Validation Tests**:
  - Test system: H2/cc-pVDZ RHF
  - Golden value: **-1.1287000935564406 Hartree** (from PySCF Tutorial `user_guide.ipynb` Cell 4)
  - Tolerance: ±0.0001 Hartree
  - **Reference**: `<HOME>/QMatSuite/.tmp/PySCF_Tutorial-master/user_guide.ipynb`

**Acceptance Criteria**:
- All Phase 3C tests pass
- SCF checkpoint can be loaded as `init_guess` for rerun (no mf shim)
- Unified `method` parameter works for both HF and DFT
- No structure data in step.yaml
- Artifacts are written to per-step directories

**Files to Review**:
- `src/qmatsuite/engines/pyscf/runner.py` (checkpoint handling, unified method parameter)
- `src/qmatsuite/calculation/manifest_reconcile.py` (incremental skip gating)
- `src/qmatsuite/workflow/registry.py` (step type specs)
- `tests/integration/test_pyscf_execution.py` (integration tests)

**Not Doing**:
- Changing restart policy (conservative policy is non-negotiable)
- Modifying structure storage (SSOT constraint)
- Adding new step types (deferred to M1+)

---

## Milestone M1: Analysis (Bundle Population, Dipole, Frontier Orbitals)

**Status**: 📋 Planned (v0, Category 1)

**Goal**: Implement `pyscf_analysis` step type and `scf_analysis` workflow. Bundle all "interpretation of ground-state wavefunction" into ONE step.

**Rationale**: These properties (population analysis, dipole moment, frontier orbitals) are almost always run together. ORCA and other QC codes present these as a block. This avoids fragmentation into tiny steps.

**Scope Boundary**: This step computes **cheap** ground-state interpretation only. No expensive calculations (e.g., no frequency calculations, no excited states).

**Tasks**:

### C1: Step Type Registry
- [ ] Add `pyscf_analysis` step type to registry
  - File: `src/qmatsuite/workflow/registry.py`
  - `id`: `"analysis"` (public type, string key)
  - `machine_type`: `"pyscf_analysis"`
  - `public_type`: `"analysis"`
  - `engine`: `"pyscf"`
  - `executable`: `"python"`
  - `supports_incremental_skip`: `False` (always rerun in v0)

### C2: Workflow Materialization
- [ ] Add `("pyscf", "analysis"): "pyscf_analysis"` to `MATERIALIZATION_MAP`
  - File: `src/qmatsuite/workflow/generalized_steps.py`
  - Use string key `"analysis"`, NOT enum value
- [ ] Update `materialize_public_step_key()` to handle `"analysis"` public key
- [ ] Add `scf_analysis` workflow template
  - File: `src/qmatsuite/workflow/templates.py`
  - `id`: `"scf_analysis"`
  - `name`: `"SCF + Analysis"`
  - `step_sequence`: `("scf", "analysis")`
  - Public step keys (string keys, lowercase)

### C3: Step.yaml Generation
- [ ] Add default parameters for `pyscf_analysis`
  - File: `src/qmatsuite/calculation/step_defaults.py`
  - Defaults: `population_method="mulliken"`, `verbose=4`
  - **CRITICAL**: Do NOT include `scf_method`, `scf_xc`, `scf_chkfile` in defaults (these are inferred by runner from upstream artifacts)
- [ ] Verify `create_step_doc()` handles `pyscf_analysis` correctly
  - File: `src/qmatsuite/workflow/step_factory.py`

### C4: Execution Engine
- [ ] Implement `run_analysis()` function in PySCF runner
  - File: `src/qmatsuite/engines/pyscf/runner.py`
  - **SCF metadata inference**: Read upstream SCF step's `results.json` to get `method` and `xc` (if DFT). Construct checkpoint path from upstream step's artifacts directory.
  - Load SCF checkpoint (must exist, fail if missing/corrupt)
  - Rebuild `mol` and `mf` from checkpoint (conservative policy: rerun SCF kernel)
  - Compute dipole moment: `pyscf.prop.dipole` or `mf.dip_moment()`
  - Compute population analysis: Mulliken charges (Löwdin/Mayer if available)
  - Extract frontier orbitals: HOMO, LUMO, gap from MO energies
  - Write `results.json` and `stdout.txt` (NO checkpoint)
- [ ] Update `run_job()` to dispatch to `run_analysis()` for `pyscf_analysis` step type
- [ ] Artifact contract: `results.json` + `stdout.txt` (NO checkpoint)
- [ ] **CRITICAL**: Do NOT read `scf_method`, `scf_xc`, `scf_chkfile` from step.yaml parameters. These are inferred from upstream SCF step artifacts.

### C5: Incremental Skip Gating
- [ ] Verify `pyscf_analysis` has `supports_incremental_skip=False` in registry
- [ ] Verify `reconcile_manifest()` respects skip gating (analysis always reruns)

### C6: Tests
- [ ] Unit tests:
  - Test: `materialize_public_step_key("analysis", "pyscf")` → `"pyscf_analysis"`
  - Test: `pyscf_analysis` step type exists in registry with correct properties
  - Test: `pyscf_analysis` has `supports_incremental_skip=False`
  - Test: `scf_analysis` workflow template exists and materializes correctly
  - Test: `get_default_step_params("pyscf_analysis")` returns expected defaults
  - File: `tests/unit/test_pyscf_integration.py`
- [ ] Integration tests:
  - Test: Run `scf_analysis` workflow on H2O molecule
    - Assert: SCF step produces checkpoint
    - Assert: Analysis step reads checkpoint successfully
    - Assert: Analysis `results.json` contains dipole, population analysis, frontier orbitals
    - Assert: Dipole magnitude is non-negative
    - Assert: HOMO-LUMO gap is positive (for stable molecule)
  - Test: Analysis step fails if checkpoint missing (clear error message)
  - Test: Analysis step always reruns (incremental skip gating)
  - File: `tests/integration/test_pyscf_execution.py`

**Steps Introduced**:
- `pyscf_analysis` (bundled analysis step)

**Workflows Introduced**:
- `scf_analysis` (SCF → Analysis)

**Validation Rules Added**:
- Analysis step requires converged SCF checkpoint

**Tests Added**:
- Unit tests: Materialization, step type spec, parameter defaults
- Integration tests: Run scf_analysis workflow, verify results structure, verify skip gating
- **Numeric Validation Tests**:
  - Test system: OH/cc-pVDZ UHF
  - Golden properties (from PySCF Tutorial `user_guide.ipynb` Cell 12):
    - Dipole moment: [0.00000, 0.00000, 1.80400] (atomic units), tolerance: ±0.01
    - Mulliken charge (O): -0.323214025599, tolerance: ±0.01
  - **Reference**: `<HOME>/QMatSuite/.tmp/PySCF_Tutorial-master/user_guide.ipynb`

**Test Commands**:
```bash
# Unit tests
pytest tests/unit/test_pyscf_integration.py::TestPySCFAnalysis -v

# Integration tests (requires .venv with PySCF)
source .venv/bin/activate
pytest tests/integration/test_pyscf_execution.py::TestPySCFAnalysis -v
```

**Acceptance Criteria**:
- `pyscf_analysis` step type exists in registry
- `scf_analysis` workflow materializes correctly for `engine_family="pyscf"`
- Analysis calculation runs successfully on H2O molecule
- Analysis results.json contains dipole, population analysis, frontier orbitals
- Analysis step always reruns (incremental skip gating works)
- All tests pass

**UI Acceptance Criteria**:
- Workflow name remains "SCF + Analysis" (generalized, unchanged)
- Materialization is correct (UI sees "scf" + "analysis", backend uses `pyscf_scf` + `pyscf_analysis`)

**Not Doing**:
- Separate steps for dipole, population, orbitals (bundle into analysis)
- Analysis restart/checkpoint (v0 policy: always rerun)
- Advanced population methods (Löwdin/Mayer are optional, Mulliken is default)

---

## Milestone M2: TD (Unified TDDFT/TDHF, Backend Selection)

**Status**: 📋 Planned (v0, Category 1)

**Goal**: Implement `pyscf_td` step type and `scf_td` workflow. Unified excited-state calculation with automatic backend selection (TDDFT or TDHF) based on SCF method.

**Rationale**: TDDFT and TDHF are both linear response theories. They differ in the reference (DFT vs HF), not in the physical operation (excited states). Separating them would fragment the abstraction.

**Key Design Decision**: Use ONE generalized step key `"td"`. Runtime backend selection:
- If `scf.method == "dft"` → TDDFT backend
- If `scf.method == "hf"` → TDHF backend
- **DFT → TDHF is a HARD ERROR** (physically meaningless)

**Tasks**:

### C1: Step Type Registry
- [ ] Add `pyscf_td` step type to registry
  - File: `src/qmatsuite/workflow/registry.py`
  - `id`: `"td"` (public type, string key)
  - `machine_type`: `"pyscf_td"`
  - `public_type`: `"td"`
  - `engine`: `"pyscf"`
  - `executable`: `"python"`
  - `supports_incremental_skip`: `False` (always rerun in v0)

### C2: Workflow Materialization
- [ ] Add `("pyscf", "td"): "pyscf_td"` to `MATERIALIZATION_MAP`
  - File: `src/qmatsuite/workflow/generalized_steps.py`
  - Use string key `"td"`, NOT enum value
  - Do NOT add separate `"tddft"` or `"tdhf"` keys
- [ ] Update `materialize_public_step_key()` to handle `"td"` public key
- [ ] Add `scf_td` workflow template
  - File: `src/qmatsuite/workflow/templates.py`
  - `id`: `"scf_td"`
  - `name`: `"SCF + Excited States"`
  - `step_sequence`: `("scf", "td")`
  - Public step keys (string keys, lowercase)

### C3: Step.yaml Generation
- [ ] Add default parameters for `pyscf_td`
  - File: `src/qmatsuite/calculation/step_defaults.py`
  - Defaults: `nroots=10`, `tda=False`, `conv_tol=1e-9`, `max_cycle=50`, `verbose=4`
  - **CRITICAL**: Do NOT include `scf_method`, `scf_xc`, `scf_chkfile` in defaults (these are inferred by runner from upstream artifacts)
- [ ] Verify `create_step_doc()` handles `pyscf_td` correctly

### C4: Execution Engine
- [ ] Implement `run_td()` function in PySCF runner
  - File: `src/qmatsuite/engines/pyscf/runner.py`
  - **SCF metadata inference**: Read upstream SCF step's `results.json` to get `method` and `xc` (if DFT). Construct checkpoint path from upstream step's artifacts directory.
  - Load SCF checkpoint (must exist, fail if missing/corrupt)
  - Rebuild `mol` and `mf` from checkpoint (conservative policy: rerun SCF kernel)
  - **Backend selection** (automatic, inferred from upstream SCF, not user parameter):
    - If upstream SCF `method == "dft"` → Use TDDFT backend (`tddft.TDDFT(mf)`)
    - If upstream SCF `method == "hf"` → Use TDHF backend (`tdhf.TDHF(mf)`)
    - **DFT → TDHF is a HARD ERROR** (blocked at workflow validation level, not in runner)
  - Set parameters: `nroots`, `tda` (optional), `conv_tol`, `max_cycle`
  - Run `mytd.kernel()`
  - Extract results: excitation energies, oscillator strengths, transition dipoles
  - Write `results.json` (include `method` field indicating backend used: `"tddft"` or `"tdhf"`) and `stdout.txt`
  - NO checkpoint for TD in v0
- [ ] Update `run_job()` to dispatch to `run_td()` for `pyscf_td` step type
- [ ] Artifact contract: `results.json` + `stdout.txt` (NO checkpoint)
- [ ] **CRITICAL**: Do NOT read `scf_method`, `scf_xc`, `scf_chkfile` from step.yaml parameters. These are inferred from upstream SCF step artifacts.

### C5: Workflow Validation Rules
- [ ] Add validation rule: DFT → TDHF is blocked (hard error)
  - File: `src/qmatsuite/workflow/templates.py` (workflow validation layer)
  - Check: If upstream SCF method is DFT and TD step is used → ERROR (DFT → TDHF is meaningless)
  - Note: Workflow validation happens at materialization/instantiation time, NOT in runner
  - Runner does NOT enforce physics rules (steps are dumb, workflows are smart)

### C6: Incremental Skip Gating
- [ ] Verify `pyscf_td` has `supports_incremental_skip=False` in registry
- [ ] Verify `reconcile_manifest()` respects skip gating (td always reruns)

### C7: Tests
- [ ] Unit tests:
  - Test: `materialize_public_step_key("td", "pyscf")` → `"pyscf_td"`
  - Test: `pyscf_td` step type exists in registry with correct properties
  - Test: `pyscf_td` has `supports_incremental_skip=False`
  - Test: `scf_td` workflow template exists and materializes correctly
  - Test: `get_default_step_params("pyscf_td")` returns expected defaults
- [ ] Integration tests:
  - Test: Run `scf_td` workflow on H2O molecule with DFT SCF (RKS/B3LYP)
    - Assert: SCF step produces checkpoint
    - Assert: TD step reads checkpoint successfully
    - Assert: TD step uses TDDFT backend (check `results.json` method field)
    - Assert: TD `results.json` contains excitation energies, oscillator strengths
    - Assert: Excitation energies are positive
    - Assert: Oscillator strengths are non-negative
  - Test: Run `scf_td` workflow on H2O molecule with HF SCF (RHF)
    - Assert: TD step uses TDHF backend (check `results.json` method field)
  - Test: TD step fails if checkpoint missing (clear error message)
  - Test: TD step always reruns (incremental skip gating)
  - File: `tests/integration/test_pyscf_execution.py`

**Steps Introduced**:
- `pyscf_td` (unified TDDFT/TDHF step)

**Workflows Introduced**:
- `scf_td` (SCF → TD)

**Validation Rules Added**:
- Backend selection is automatic (not a user parameter)
- DFT → TDHF is blocked (hard error)
- TD step requires converged SCF checkpoint

**Tests Added**:
- Unit tests: Materialization, step type spec, parameter defaults
- Integration tests: Run scf_td workflow with DFT and HF, verify backend selection, verify results structure, verify skip gating

**Numeric Validation**:
- Test system: To be determined (use tutorial reference if available)
- Golden value: From PySCF Tutorial (`user_guide.ipynb` or `dev_guide.ipynb`) when available
- Validate excitation energies with tolerance: ±0.001 Hartree
- **Reference**: PySCF Tutorial at `<HOME>/QMatSuite/.tmp/PySCF_Tutorial-master/`

**Test Commands**:
```bash
# Unit tests
pytest tests/unit/test_pyscf_integration.py::TestPySCFTD -v

# Integration tests (requires .venv with PySCF)
source .venv/bin/activate
pytest tests/integration/test_pyscf_execution.py::TestPySCFTD -v
```

**Acceptance Criteria**:
- `pyscf_td` step type exists in registry
- `scf_td` workflow materializes correctly for `engine_family="pyscf"`
- TD calculation runs successfully on H2O molecule (both DFT and HF references)
- TD results.json contains excitation energies, oscillator strengths, transition dipoles
- Backend selection is automatic (TDDFT for DFT, TDHF for HF)
- TD step always reruns (incremental skip gating works)
- All tests pass

**UI Acceptance Criteria**:
- Workflow name remains "SCF + Excited States" (generalized, unchanged)
- Materialization is correct (UI sees "scf" + "td", backend uses `pyscf_scf` + `pyscf_td`)
- Users do NOT see "tddft" or "tdhf" as separate steps (unified abstraction)

**Not Doing**:
- Separate `tddft` and `tdhf` steps (unified `td` step)
- TD restart/checkpoint (v0 policy: always rerun)
- NTO analysis (optional, defer to v1+)
- TDA as separate step (TDA is a parameter option, not a separate step)

**Reference**:
- PySCF TDDFT docs: https://pyscf.org/user/tdscf.html
- Examples: `.tmp/pyscf-master/examples/tddft/00-simple_tddft.py`

---

## Milestone M3: MP2 (Post-HF Energy Correction)

**Status**: ✅ Implemented (Phase 3C, refinement required)

**Goal**: Refine existing `pyscf_mp2` implementation to match design decisions (HF reference requirement, validation rules).

**Key Design Decision**: MP2 requires HF reference. DFT → MP2 is allowed but with WARNING (expert usage).

**Tasks**:

### Refinement Tasks
- [ ] Verify MP2 step accepts HF reference (OK, normal usage)
- [ ] Add validation rule: DFT → MP2 triggers WARNING (allowed but non-standard)
  - File: Workflow validation or runner validation
  - Check: If `scf_method == "dft"` and MP2 step is used → WARNING (log, do not block)
- [ ] Update documentation: MP2 requires HF reference (warn if DFT)
- [ ] Verify MP2 step always reruns (even if SHA matches)
- [ ] Verify MP2 step requires SCF checkpoint
- [ ] Run integration tests: `pytest tests/integration/test_pyscf_execution.py -k mp2 -v`

**Steps Introduced**:
- `pyscf_mp2` (already implemented, refine validation)

**Workflows Introduced**:
- `scf_mp2` (already implemented)

**Validation Rules Added**:
- MP2 requires HF reference (warn if DFT)
- MP2 step requires converged SCF checkpoint

**Tests Added**:
- Integration tests: Run scf_mp2 with HF (OK) and DFT (WARNING), verify validation behavior

**Numeric Validation**:
- Test system: H2/cc-pVDZ (or use tutorial reference systems)
- Golden value: From PySCF Tutorial (`user_guide.ipynb`) when available, or PySCF examples
- Validate MP2 correlation energy with tolerance: ±0.0001 Hartree
- **Reference**: PySCF Tutorial at `<HOME>/QMatSuite/.tmp/PySCF_Tutorial-master/user_guide.ipynb`

**Acceptance Criteria**:
- MP2 step works with HF reference (normal usage)
- MP2 step works with DFT reference but logs WARNING
- All tests pass

**Not Doing**:
- Changing MP2 implementation (already correct)
- MP2 restart/checkpoint (v0 policy: always rerun)

**Reference**:
- PySCF MP2 docs: https://pyscf.org/user/mp.html
- Examples: `.tmp/pyscf-master/examples/mp/00-simple_mp2.py`
- Phase 3C implementation: `src/qmatsuite/engines/pyscf/runner.py::run_mp2`

---

## Milestone M4: Freq (Harmonic Frequencies + Thermochemistry)

**Status**: 📋 Planned (v0, Category 1)

**Goal**: Implement `pyscf_freq` step type and `scf_freq` workflow. Harmonic frequencies, zero-point energy, and thermochemistry.

**Rationale for v0 Selection**: Frequencies are essential for vibrational spectroscopy, thermochemistry, geometry optimization (force constants), and transition state characterization. Chosen over NMR for v0 because frequencies are more fundamental.

**Tasks**:

### C1: Step Type Registry
- [ ] Add `pyscf_freq` step type to registry
  - File: `src/qmatsuite/workflow/registry.py`
  - `id`: `"freq"` (public type, string key)
  - `machine_type`: `"pyscf_freq"`
  - `public_type`: `"freq"`
  - `engine`: `"pyscf"`
  - `executable`: `"python"`
  - `supports_incremental_skip`: `False` (always rerun in v0)

### C2: Workflow Materialization
- [ ] Add `("pyscf", "freq"): "pyscf_freq"` to `MATERIALIZATION_MAP`
  - File: `src/qmatsuite/workflow/generalized_steps.py`
  - Use string key `"freq"`, NOT enum value
- [ ] Update `materialize_public_step_key()` to handle `"freq"` public key
- [ ] Add `scf_freq` workflow template
  - File: `src/qmatsuite/workflow/templates.py`
  - `id`: `"scf_freq"`
  - `name`: `"SCF + Frequencies"`
  - `step_sequence`: `("scf", "freq")`
  - Public step keys (string keys, lowercase)

### C3: Step.yaml Generation
- [ ] Add default parameters for `pyscf_freq`
  - File: `src/qmatsuite/calculation/step_defaults.py`
  - Defaults: `thermo=False`, `temperature=298.15`, `pressure=101325`, `verbose=4`
  - **CRITICAL**: Do NOT include `scf_method`, `scf_xc`, `scf_chkfile` in defaults (these are inferred by runner from upstream artifacts)
- [ ] Verify `create_step_doc()` handles `pyscf_freq` correctly

### C4: Execution Engine
- [ ] Implement `run_freq()` function in PySCF runner
  - File: `src/qmatsuite/engines/pyscf/runner.py`
  - **SCF metadata inference**: Read upstream SCF step's `results.json` to get `method` and `xc` (if DFT). Construct checkpoint path from upstream step's artifacts directory.
  - Load SCF checkpoint (must exist, fail if missing/corrupt)
  - Rebuild `mol` and `mf` from checkpoint (conservative policy: rerun SCF kernel)
  - Compute Hessian: `mf.Hessian().kernel()`
  - Compute frequencies and normal modes: `thermo.harmonic_analysis(mol, hessian)`
  - If `thermo=True`: Compute thermochemistry: `thermo.thermo(mf, frequencies, temperature, pressure)`
  - Extract results: frequencies (cm⁻¹), normal modes, intensities (best-effort), ZPE, thermochemistry (if requested)
  - Write `results.json` (minimal and honest: frequencies required, intensities optional) and `stdout.txt`
  - NO checkpoint for freq in v0
- [ ] Update `run_job()` to dispatch to `run_freq()` for `pyscf_freq` step type
- [ ] Artifact contract: `results.json` + `stdout.txt` (NO checkpoint)
- [ ] **CRITICAL**: Do NOT read `scf_method`, `scf_xc`, `scf_chkfile` from step.yaml parameters. These are inferred from upstream SCF step artifacts.

### C5: Incremental Skip Gating
- [ ] Verify `pyscf_freq` has `supports_incremental_skip=False` in registry
- [ ] Verify `reconcile_manifest()` respects skip gating (freq always reruns)

### C6: Tests
- [ ] Unit tests:
  - Test: `materialize_public_step_key("freq", "pyscf")` → `"pyscf_freq"`
  - Test: `pyscf_freq` step type exists in registry with correct properties
  - Test: `pyscf_freq` has `supports_incremental_skip=False`
  - Test: `scf_freq` workflow template exists and materializes correctly
  - Test: `get_default_step_params("pyscf_freq")` returns expected defaults
- [ ] Integration tests:
  - Test: Run `scf_freq` workflow on H2O molecule (RHF/6-31G)
    - Assert: SCF step produces checkpoint
    - Assert: Freq step reads checkpoint successfully
    - Assert: Freq `results.json` contains frequencies (cm⁻¹)
    - Assert: Frequencies are real (no imaginary frequencies for stable molecule)
    - Assert: Number of frequencies = 3N - 6 (for nonlinear molecule, N=3 → 3 frequencies)
    - Assert: Frequencies are positive (for stable molecule)
  - Test: Freq step with `thermo=True` computes thermochemistry
    - Assert: `results.json` contains `thermochemistry` dict
    - Assert: Thermochemistry includes ZPE, E_0K, E_tot, H_tot, G_tot, Cv_tot
  - Test: Freq step fails if checkpoint missing (clear error message)
  - Test: Freq step always reruns (incremental skip gating)
  - File: `tests/integration/test_pyscf_execution.py`

**Steps Introduced**:
- `pyscf_freq` (harmonic frequencies step)

**Workflows Introduced**:
- `scf_freq` (SCF → Frequencies)

**Validation Rules Added**:
- Freq step requires converged SCF checkpoint
- Thermochemistry requires full Hessian (cannot use `atmlst`)

**Tests Added**:
- Unit tests: Materialization, step type spec, parameter defaults
- Integration tests: Run scf_freq workflow, verify frequencies, verify thermochemistry, verify skip gating

**Numeric Validation**:
- Test system: To be determined (use tutorial reference if available)
- Golden value: From PySCF Tutorial (`user_guide.ipynb` or `dev_guide.ipynb`) when available
- Validate frequencies with tolerance: ±1 cm⁻¹
- **Reference**: PySCF Tutorial at `<HOME>/QMatSuite/.tmp/PySCF_Tutorial-master/`

**Test Commands**:
```bash
# Unit tests
pytest tests/unit/test_pyscf_integration.py::TestPySCFFreq -v

# Integration tests (requires .venv with PySCF)
source .venv/bin/activate
pytest tests/integration/test_pyscf_execution.py::TestPySCFFreq -v
```

**Acceptance Criteria**:
- `pyscf_freq` step type exists in registry
- `scf_freq` workflow materializes correctly for `engine_family="pyscf"`
- Freq calculation runs successfully on H2O molecule
- Freq results.json contains frequencies, normal modes, ZPE
- Freq step with `thermo=True` computes thermochemistry
- Freq step always reruns (incremental skip gating works)
- All tests pass

**UI Acceptance Criteria**:
- Workflow name remains "SCF + Frequencies" (generalized, unchanged)
- Materialization is correct (UI sees "scf" + "freq", backend uses `pyscf_scf` + `pyscf_freq`)

**Not Doing**:
- Partial Hessian (`atmlst` parameter) in v0 (defer to v1, focus on full Hessian)
- Geometry optimization (defer to v1)
- Anharmonic frequencies (defer to v1+)
- Freq restart/checkpoint (v0 policy: always rerun)
- IR/Raman intensities as required (best-effort, optional)

**Reference**:
- PySCF Hessian docs: https://pyscf.org/user/grad.html#hessian
- Examples:
  - `.tmp/pyscf-master/examples/hessian/01-scf_hessian.py`
  - `.tmp/pyscf-master/examples/hessian/10-thermochemistry.py`

---

## Milestone M5: Deferred Extensions (CCSD, EOM-CCSD, NMR, etc.)

**Status**: 📋 Planned (v1, Deferred)

**Goal**: Implement advanced post-HF methods and additional properties. Deferred to v1 to prioritize property workflows in v0.

**Steps to Defer**:
- `pyscf_ccsd` (Category 2)
- `pyscf_ccsd_t` (Category 2)
- `pyscf_eom_ccsd` (Category 3, template-only)
- `pyscf_nmr` (Category 1)

**Workflows to Defer**:
- `scf_ccsd`
- `scf_ccsd_t`
- `scf_ccsd_eom` (template-only)
- `scf_nmr`

**Rationale for Deferral**:
- CCSD/CCSD(T) are expensive and less commonly used than MP2 in v0
- EOM-CCSD is Category 3 (template-only), requires CCSD first
- NMR is less fundamental than frequencies for v0

**Tasks**: (Outlined in original roadmap, to be detailed in v1 planning)

---

## Summary Checklist

### v0 Milestones (Current Focus)
- [ ] **M0**: SCF (HF/DFT unified) + restart semantics (verification)
- [ ] **M1**: Analysis (bundle population, dipole, frontier orbitals)
- [ ] **M2**: TD (unified TDDFT/TDHF, backend selection)
- [ ] **M3**: MP2 (post-HF energy correction, refinement)
- [ ] **M4**: Freq (harmonic frequencies + thermochemistry)

### v1 Milestones (Deferred)
- [ ] **M5**: Deferred extensions (CCSD, EOM-CCSD, NMR, etc.)

---

## Testing Strategy

### Before Each Milestone
1. Run unit tests: `pytest tests/unit/test_pyscf_integration.py -v`
2. Run integration tests: `pytest tests/integration/test_pyscf_execution.py -v`
3. Run full test suite: `pytest tests/ -k pyscf -v`

### After Each Milestone
1. Verify all tests pass
2. Verify UI acceptance criteria (workflow names unchanged, materialization correct)
3. Verify numeric validation against authoritative sources
4. Update catalog document if needed (new step types/workflows)

### Numeric Validation Policy
- For each MAJOR CATEGORY (scf, mp2, td, freq):
  - Choose ONE representative test system
  - Use GOLDEN VALUE from external authoritative source (PySCF Tutorial is PRIMARY source)
  - **Primary Reference**: PySCF Tutorial (`<HOME>/QMatSuite/.tmp/PySCF_Tutorial-master/user_guide.ipynb` and `dev_guide.ipynb`)
  - Validate with tolerance (e.g., ±0.0001 Hartree for energies, ±1 cm⁻¹ for frequencies)
  - Do NOT use "self-generated" values as golden references

---

## Notes

### Architecture Constraints (Non-Negotiable)
1. **SSOT**: `step.yaml` contains only PySCF parameters (no structure, no IR/preset)
2. **Structure**: Structure is calc-level only (via `calculation.yaml` structure_id)
3. **Restart Policy**: Conservative (SCF restartable via checkpoint, others always rerun)
4. **Artifacts**: Per-step artifacts directory, cleared before each step run
5. **Skip Gating**: `supports_incremental_skip` flag enforced in incremental planner
6. **No Require/Produce Graph**: Only special-case behavior (SCF produces checkpoint, only SCF is restartable)
7. **String Keys**: Public step keys are strings, not enums

### Scope Boundaries
- **v0**: SCF (unified), Analysis, TD (unified), MP2, Freq
- **v1**: CCSD, CCSD(T), EOM-CCSD, NMR
- **Deferred**: Geometry optimization, anharmonic frequencies, advanced properties

### Design Decisions
1. **SCF is unified**: `method: hf | dft` parameter, not separate steps
2. **TD is unified**: Backend selection (TDDFT/TDHF) is automatic, not separate steps
3. **Analysis is bundled**: Population, dipole, frontier orbitals in ONE step
4. **Post-HF requires HF**: MP2/CCSD require HF reference (warn if DFT)
5. **Steps are independent**: Workflows provide physical closure, validation happens at workflow level

---

**Document Status**: ✅ Complete (Planning Phase, Revised)  
**Next Step**: Review catalog and roadmap, then proceed with M0 (status verification)
