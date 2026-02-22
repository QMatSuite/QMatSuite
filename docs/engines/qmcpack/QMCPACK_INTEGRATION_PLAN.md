# QMCPACK Integration Plan

**Date**: 2026-02-03
**Status**: PROPOSAL — requires review before implementation
**Companion**: `QMCPACK_EXPLORATION.md` (findings), `qmcpack_parser.py`, `qmcpack_writer.py`

---

## 0. Executive Summary

QMCPACK integration into QMatSuite follows the plug-in driver pattern defined
by `ENGINE_RECIPE_AND_RUNNER_CONSTITUTION.md`. The integration requires:

1. A new driver bundle at `src/qmatsuite/drivers/qmcpack/`
2. Three new GEN steps added to `GenStepRegistry` (**kernel change**)
3. A new recipe archetype: **Multi-Section Recipe** (variant of Directory-state)
4. A QMCPACK-specific pseudopotential assets map in `calculation.yaml`

No changes to runner, executor, or dispatch code are needed.

### Kernel Change Justification

QMCPACK requires three GEN steps not currently in `GenStepRegistry.GEN_STEPS`:

| New GEN Step | Purpose | Why not reuse existing |
|-------------|---------|----------------------|
| `vmc` | Variational Monte Carlo | No existing GEN step covers stochastic energy evaluation |
| `dmc` | Diffusion Monte Carlo | No existing GEN step covers projector QMC |
| `wfopt` | Wavefunction optimization | `relax` means geometry optimization; this optimizes wavefunction parameters at fixed geometry |

These are fundamental QMC method types with no semantic overlap with existing
GEN steps. `scf` is inappropriate because QMC is not self-consistent-field.
`custom` could be used as an escape hatch but would lose type safety and
violate the spirit of the GEN/SPEC system.

**Files modified outside `drivers/`**:
- `src/qmatsuite/workflow/gen_steps.py` — add `"vmc"`, `"dmc"`, `"wfopt"` to `GEN_STEPS` frozenset

This is the **only kernel file** that needs modification.

---

## 1. Driver Bundle Structure

```
src/qmatsuite/drivers/qmcpack/
├── __init__.py          # DriverRegistry.register(QMCPACKDriver())
├── driver.py            # QMCPACKDriver (PREFIX + SUPPORTED_GEN_STEPS + 7 MUST methods)
├── handler.py           # qmcpack_step_handler()
├── recipe.py            # QMCPACKRecipe (materialize → JobGraph)
├── writer.py            # XML input file generation
├── parser.py            # scalar.dat / dmc.dat / stdout parsing
├── pseudo_map.py        # QMCPACK pseudopotential mapping utilities
└── constants.py         # QMCPACK-specific constants (optional)
```

---

## 2. Driver Declaration

### 2.1 Class Attributes

```python
class QMCPACKDriver(BaseEngineDriver):
    PREFIX: str = "qmcpack"
    SUPPORTED_GEN_STEPS: frozenset[str] = frozenset({"vmc", "dmc", "wfopt"})
```

### 2.2 MUST Interface

| Item | Value |
|------|-------|
| `engine_family` | `"qmcpack"` |
| `display_name` | `"QMCPACK"` |
| `driver_api_version` | `"1.0.0"` |
| `get_step_type_specs()` | 3 StepTypeSpec instances (see §2.3) |
| `get_handler()` | `qmcpack_step_handler` function |
| `get_recipe_class()` | `QMCPACKRecipe` |
| `get_materialization_map()` | `{"vmc": "qmcpack_vmc", "dmc": "qmcpack_dmc", "wfopt": "qmcpack_wfopt"}` |

### 2.3 Step Type Specs

```python
StepTypeSpec(
    step_type_spec="qmcpack_vmc",
    engine="qmcpack",
    executable="qmcpack",
    description="Variational Monte Carlo energy evaluation",
    category="qmc",
    supports_restart=True,    # via .cont.xml + .config.h5
    mpi_aware=True,
)

StepTypeSpec(
    step_type_spec="qmcpack_dmc",
    engine="qmcpack",
    executable="qmcpack",
    description="Diffusion Monte Carlo ground-state projection",
    category="qmc",
    supports_restart=True,
    mpi_aware=True,
)

StepTypeSpec(
    step_type_spec="qmcpack_wfopt",
    engine="qmcpack",
    executable="qmcpack",
    description="Wavefunction parameter optimization (Jastrow, CI coefficients)",
    category="qmc",
    supports_restart=False,   # optimization is typically re-run from scratch
    mpi_aware=True,
)
```

### 2.4 SHOULD Interface

| Item | Value | Rationale |
|------|-------|-----------|
| `get_workdir_policy()` | `WorkdirPolicy.ISOLATED` | Each QMCPACK step gets its own directory |
| `get_capabilities()` | `{"vmc", "dmc", "wfopt"}` | Standard capability set |
| `supports_incremental_skip()` | `{"qmcpack_vmc": True, "qmcpack_dmc": True}` | Can skip via fingerprint check |
| `get_preflight_requirements()` | See §5 | Wavefunction HDF5 + pseudopotentials |
| `classify_error()` | Parse stderr/stdout | QMCPACK prints clear error messages |

### 2.5 PLUGIN Interface

| Item | Value |
|------|-------|
| `get_artifact_patterns()` | `{"scalar_dat": "{id}.s{NNN}.scalar.dat", "dmc_dat": "{id}.s{NNN}.dmc.dat", ...}` |
| `parse_output()` | Delegates to `parser.py` |

---

## 3. Recipe Design

### 3.1 Recipe Archetype: ISOLATED with Multi-Section Input

QMCPACK does not fit cleanly into any existing archetype:

- **Not Directory-state (QE-like)**: No shared scratch directory between steps
- **Not Strong-chain (QC-like)**: No SCF chain root; steps are independent XML inputs
- **Not Cleanup (VASP-like)**: No CHGCAR/WAVECAR staging

QMCPACK is closest to **ISOLATED** (like LAMMPS) but with a key difference:
a single QMCPACK input XML can contain multiple `<qmc>` sections that produce
multiple series of output. However, for QMatSuite integration, we treat each
QMatSuite step as producing **one QMCPACK input file with one primary `<qmc>` section**.

This means:
- A `wfopt` step produces an XML with `<loop max="N"><qmc method="linear">...</qmc></loop>`
- A `vmc` step produces an XML with `<qmc method="vmc">...</qmc>`
- A `dmc` step produces an XML with `<qmc method="vmc">...(walker gen)...</qmc><qmc method="dmc">...</qmc>`

The DMC step internally includes a short VMC walker-generation section — this is
an implementation detail of the DMC step, not a separate QMatSuite step.

### 3.2 Recipe Behavior

```python
class QMCPACKRecipe(BaseRecipe):
    def materialize(
        self,
        steps: List[Step],
        calc_raw_dir: Path,
        step_shas: Optional[Dict[str, str]] = None,
    ) -> JobGraph:
        """
        For each step:
        1. Create isolated workdir: calc_raw_dir / step.meta.ulid /
        2. Stage wavefunction HDF5 file (symlink or copy)
        3. Stage pseudopotential XML files
        4. Generate QMCPACK XML input via writer.py
        5. Create Job with command, inputs, expected outputs
        6. Set dependencies (dmc depends on wfopt for .opt.xml)
        """
```

### 3.3 Working Directory Layout

For a calculation with wfopt → vmc → dmc steps:

```
calc/raw/
├── <wfopt_ulid>/
│   ├── qmc_input.xml         # Optimization input
│   ├── pwscf.pwscf.h5        # Symlink to wavefunction HDF5
│   ├── C.BFD.xml             # Pseudopotential
│   ├── project.s000.scalar.dat  # Output (loop 0)
│   ├── project.s000.opt.xml     # Optimized wavefunction (loop 0)
│   ├── project.s001.scalar.dat  # Output (loop 1)
│   ├── project.s001.opt.xml     # Optimized wavefunction (loop 1)
│   └── ...
├── <vmc_ulid>/
│   ├── qmc_input.xml         # VMC input (references optimized wfn)
│   ├── pwscf.pwscf.h5        # Symlink
│   ├── C.BFD.xml
│   ├── project.s000.scalar.dat  # VMC output
│   └── ...
└── <dmc_ulid>/
    ├── qmc_input.xml         # VMC+DMC input
    ├── pwscf.pwscf.h5        # Symlink
    ├── C.BFD.xml
    ├── project.s000.scalar.dat  # Walker-gen VMC output
    ├── project.s001.scalar.dat  # DMC output
    ├── project.s001.dmc.dat     # DMC step-level data
    └── ...
```

### 3.4 Artifact Chaining

**wfopt → vmc/dmc**: The optimized Jastrow parameters from the last `.opt.xml`
are read and embedded directly into the VMC/DMC input XML by `writer.py`. There
is no file-level chaining — the recipe reads the `.opt.xml` from the wfopt
workdir and extracts Jastrow coefficients at materialization time.

**Alternative**: Copy the final `.opt.xml` into the VMC/DMC workdir and
reference it via `<include>`. This is simpler but less explicit.

**Recommendation**: Embed coefficients directly. This makes each step's input
self-contained and reproducible.

### 3.5 Job Formation

| Step Type | Jobs | Command |
|-----------|------|---------|
| `wfopt` | 1 job | `mpirun -np N qmcpack qmc_input.xml` |
| `vmc` | 1 job | `mpirun -np N qmcpack qmc_input.xml` |
| `dmc` | 1 job | `mpirun -np N qmcpack qmc_input.xml` |

Each step is one job. The DMC job's input XML contains both VMC walker-generation
and DMC production sections, but it's still a single `qmcpack` invocation.

### 3.6 Expected Outputs

| Step Type | Expected Output Files |
|-----------|-----------------------|
| `wfopt` | `{id}.s{N}.scalar.dat` for each loop iteration, `{id}.s{N}.opt.xml` |
| `vmc` | `{id}.s000.scalar.dat` |
| `dmc` | `{id}.s000.scalar.dat` (VMC), `{id}.s001.scalar.dat` (DMC), `{id}.s001.dmc.dat` |

---

## 4. Handler Design

### 4.1 Handler Signature

```python
def qmcpack_step_handler(
    job: Job,
    calculation: "Calculation",
    engine_registry: "EngineRegistry",
    context: Dict[str, Any],
) -> JobResult:
```

### 4.2 Handler Flow

1. Get step from calculation by ULID
2. Get engine config from registry
3. Create workdir (already done by recipe materialization)
4. Verify input files exist (XML input, HDF5, pseudopotentials)
5. Build command: resolve `qmcpack` executable path
6. Execute via subprocess
7. Parse stdout for success/failure
8. Parse scalar.dat for energy results
9. Return `JobResult` with parsed output

### 4.3 Error Classification

| Error Pattern | ErrorClass | Action |
|---------------|-----------|--------|
| `QMCPACK execution completed successfully` | SUCCESS | Parse results |
| `Fatal Error` in stderr | FATAL | Report and abort |
| Non-zero exit code | RUNTIME_ERROR | Report stderr |
| Missing output files | OUTPUT_MISSING | Report which files |
| `samples > walkers*steps*blocks` | INPUT_ERROR | Suggest parameter fix |

---

## 5. Preflight Requirements

### 5.1 Wavefunction HDF5 File

QMCPACK requires an HDF5 wavefunction file (`.h5`) generated by a DFT code
converter. This is the primary preflight requirement.

**Options for obtaining the HDF5 file**:

1. **User provides pre-computed HDF5** — simplest; user runs DFT + conversion
   externally and points QMCPACK step to the `.h5` file path.

2. **Cross-engine dependency** — QMatSuite runs QE SCF/NSCF first, then a
   `pw2qmcpack` conversion step, then QMCPACK. This requires either:
   - A `qe_pw2qmcpack` step type (new GEN step `pw2qmcpack` or reuse `custom`)
   - Or a pre/post-hook on the QE NSCF step

3. **PySCF path** — PySCF has built-in `savetoqmcpack`. A `pyscf_scf` step
   could be configured to also export to QMCPACK HDF5 format.

**Recommendation for v1**: Option 1 (user provides HDF5). Add the HDF5 file
path as a required field in the QMCPACK step parameters. Cross-engine
dependencies can be added in a later version.

### 5.2 Pseudopotentials

QMCPACK uses XML-format pseudopotentials (BFD, ccECP), NOT QE `.UPF` files.
The QMCPACK driver needs its own pseudopotential map.

**Proposal**: Add a `qmcpack_pseudo_map` to `calculation.yaml`:

```yaml
qmcpack_pseudo_map:
  C: "C.BFD.xml"
  O: "O.BFD.xml"
```

This is separate from the QE `species_map` because the formats are different.
The recipe stages these files from `project/qmcpack_pseudo/` into the step workdir.

### 5.3 Preflight Declaration

```python
def get_preflight_requirements(self) -> List[PreflightRequirement]:
    return [
        PreflightRequirement(
            name="wavefunction_h5",
            description="HDF5 wavefunction file from DFT converter",
            required=True,
            check=lambda step: "wavefunction_h5" in step.params,
        ),
        PreflightRequirement(
            name="pseudopotentials",
            description="QMCPACK XML pseudopotential files",
            required=True,  # Required for pseudopotential calculations
            check=lambda step: step.params.get("all_electron", False) or
                               "qmcpack_pseudo_map" in step.params,
        ),
    ]
```

---

## 6. Input Writer (`writer.py`)

The writer generates QMCPACK XML input files from step parameters (YAML → XML).

### 6.1 Responsibilities

- Read step parameters from `step.yaml`
- Generate complete QMCPACK XML with all sections:
  - `<project>` with unique ID and series=0
  - `<qmcsystem>` with cell, particles, wavefunction, hamiltonian
  - `<qmc>` section(s) appropriate for the step type
- Embed Jastrow coefficients (from optimization or defaults)
- Reference HDF5 wavefunction and pseudopotential files

### 6.2 Managed Keys (Runtime-Overridden)

| Key | Managed By | Reason |
|-----|-----------|--------|
| `project.id` | Recipe | Set to step identifier for unique output naming |
| `project.series` | Recipe | Always 0 (step isolation) |
| `sposet_collection.href` | Recipe | Points to staged HDF5 file |
| `pseudo.href` | Recipe | Points to staged pseudopotential files |

### 6.3 User-Configurable Parameters

**VMC step (`qmcpack_vmc`)**:
- `blocks`, `steps`, `substeps`, `timestep` — sampling parameters
- `warmupsteps` — equilibration
- `usedrift` — drift in moves (yes/no)

**DMC step (`qmcpack_dmc`)**:
- `targetwalkers` — walker population
- `blocks`, `steps`, `timestep` — sampling
- `warmupsteps` — equilibration
- `nonlocalmoves` — T-moves (yes/no/v0/v1/v3)
- `reconfiguration` — walker reconfiguration (yes/no)

**Optimization step (`qmcpack_wfopt`)**:
- `num_loops` — number of optimization iterations
- `blocks`, `steps`, `samples` — per-iteration sampling
- `minmethod` — optimizer (adaptive/descent/hybrid)
- `cost_energy`, `cost_variance` — cost function weights
- `shift_i`, `shift_s` — regularization

**Common parameters**:
- `wavefunction_h5` — path to HDF5 wavefunction
- `all_electron` — boolean, skip pseudopotential section
- `jastrow_coefficients` — pre-optimized Jastrow (optional)
- `tilematrix` — supercell tiling matrix
- `meshfactor` — B-spline mesh factor

### 6.4 Prototype

The temporary `qmcpack_writer.py` in the exploration scratchpad provides the
starting implementation. Key functions to adapt:

- `write_vmc_input()` → used by `qmcpack_vmc` materialization
- `write_vmc_dmc_input()` → used by `qmcpack_dmc` materialization
- Add `write_wfopt_input()` → used by `qmcpack_wfopt` materialization

---

## 7. Output Parser (`parser.py`)

### 7.1 Responsibilities

- Parse `scalar.dat` → block-averaged energy, variance, acceptance ratio
- Parse `dmc.dat` → per-step DMC data, walker population
- Parse stdout → success/failure, reference energy, reference variance
- Parse `opt.xml` → optimized Jastrow coefficients (for artifact chaining)

### 7.2 Parsed Output Structure

```python
@dataclass
class QMCPACKStepResult:
    """Parsed result from a single QMCPACK step."""
    energy: float           # Mean LocalEnergy (Ha)
    energy_error: float     # Standard error of mean
    variance: float         # Energy variance
    accept_ratio: float     # Mean acceptance ratio
    num_blocks: int         # Number of data blocks
    success: bool           # Execution succeeded
    method: str             # "vmc", "dmc", or "wfopt"
    # DMC-specific
    num_walkers: Optional[float] = None
    # Optimization-specific
    optimized_jastrow: Optional[dict] = None
```

### 7.3 Prototype

The temporary `qmcpack_parser.py` provides the starting implementation:
- `parse_scalar_dat()` → `QMCPACKScalarData`
- `parse_dmc_dat()` → `QMCPACKDMCData`
- `parse_qmcpack_stdout()` → success + section summaries
- `parse_qmcpack_run()` → full run result

---

## 8. Registration

### 8.1 Driver Registration

```python
# src/qmatsuite/drivers/qmcpack/__init__.py
from qmatsuite.core.driver_registry import DriverRegistry
from .driver import QMCPACKDriver

DriverRegistry.register(QMCPACKDriver())
```

### 8.2 Import Chain

Add to `src/qmatsuite/drivers/__init__.py`:

```python
from qmatsuite.drivers import (
    qe,
    vasp,
    lammps,
    cp2k,
    w90,
    orca,
    pyscf,
    qmcpack,   # <-- ADD
)
```

---

## 9. GenStepRegistry Update

### 9.1 Change

```python
# src/qmatsuite/workflow/gen_steps.py
GEN_STEPS: FrozenSet[str] = frozenset({
    # ... existing steps ...
    # QMC methods
    "vmc",       # Variational Monte Carlo
    "dmc",       # Diffusion Monte Carlo
    "wfopt",     # Wavefunction optimization (Jastrow, CI coefficients)
})
```

### 9.2 Naming Rationale

| Name | Alternatives Considered | Why Chosen |
|------|------------------------|------------|
| `vmc` | `montecarlo`, `mc` | Standard abbreviation, unambiguous |
| `dmc` | `diffusion`, `projector` | Standard abbreviation, unambiguous |
| `wfopt` | `optimize`, `opt`, `jastrow` | `optimize` is ambiguous (geometry?), `opt` conflicts with ORCA convention (§8 of STEP_TYPE_GEN_SPEC_CONSTITUTION: opt is forbidden as step type), `wfopt` is specific to wavefunction optimization |

All names satisfy the underscore ban (no underscores in GEN steps).

### 9.3 Future-Proofing

These GEN steps are not QMCPACK-specific. Other QMC codes (CASINO, TurboRVB)
could also declare support for `vmc`, `dmc`, and `wfopt` with their own prefixes:
- `casino_vmc`, `casino_dmc`
- `turborvb_vmc`, `turborvb_dmc`

This follows the GEN/SPEC philosophy: GEN steps are engine-agnostic intents.

---

## 10. Pseudopotential Assets

### 10.1 Project-Level Directory

```
project/qmcpack_pseudo/
├── C.BFD.xml
├── O.BFD.xml
└── H.BFD.xml
```

Separate from `project/pseudo/` (which stores QE `.UPF` files).

### 10.2 calculation.yaml Schema Addition

```yaml
# calculation.yaml
engine: qmcpack
qmcpack_pseudo_map:
  C: C.BFD.xml
  O: O.BFD.xml
```

### 10.3 Staging

The recipe copies (or symlinks) pseudopotential files from
`project/qmcpack_pseudo/` to the step workdir during materialization.

### 10.4 Digest

`qmcpack_pseudo_sha` is computed from the `qmcpack_pseudo_map` for incremental
skip decisions, following the same pattern as QE's `pseudo_set_sha`.

---

## 11. Cross-Engine Dependency (Future Work)

### 11.1 The Problem

QMCPACK almost always needs a DFT wavefunction. The typical pipeline is:

```
QE SCF → QE NSCF → pw2qmcpack → QMCPACK wfopt → QMCPACK VMC → QMCPACK DMC
```

This crosses engine boundaries (QE → QMCPACK).

### 11.2 Options

**Option A: User provides HDF5 externally** (v1 recommendation)
- User runs DFT + conversion outside QMatSuite
- QMCPACK step references the `.h5` file path
- Simplest, no cross-engine coupling
- Drawback: loses end-to-end workflow automation

**Option B: Multi-engine calculation**
- A single QMatSuite calculation contains both QE and QMCPACK steps
- Requires `calculation.yaml` to support multiple engines
- Recipe must handle cross-engine artifact passing
- Significant complexity increase

**Option C: Calculation chaining**
- Separate QE calculation and QMCPACK calculation
- QMCPACK calculation references QE calculation's output directory
- A "predecessor calculation" field in `calculation.yaml`
- Moderate complexity, clean separation

**Option D: pw2qmcpack as a QMCPACK step type**
- Add `pw2qmcpack` as a GEN step (or QMCPACK-specific step)
- The QMCPACK recipe knows how to run `pw2qmcpack.x` / `convertpw4qmc`
- Would need access to QE output files
- Breaks the isolation principle

**Recommendation**: Option A for v1, Option C for v2.

### 11.3 HDF5 Requirement for QE

If using QE as the DFT source, QE must be compiled with HDF5 support.
Our local QE 7.5 does NOT have HDF5. This is a deployment concern, not
a code architecture concern.

---

## 12. Implementation Phases

### Phase 1: Core Driver (Minimal Viable Integration)

**Scope**: Get QMCPACK running within QMatSuite with user-provided HDF5.

1. Add `vmc`, `dmc`, `wfopt` to `GenStepRegistry.GEN_STEPS`
2. Create `drivers/qmcpack/` bundle with all 7 files
3. Implement `QMCPACKDriver` with MUST interface
4. Implement `QMCPACKRecipe.materialize()` for VMC-only
5. Implement `writer.py` (adapted from exploration `qmcpack_writer.py`)
6. Implement `parser.py` (adapted from exploration `qmcpack_parser.py`)
7. Implement `handler.py`
8. Add unit tests: `tests/drivers/test_qmcpack_driver.py`
9. Add golden fixture tests using exploration artifacts

**Deliverable**: Can run `qmcpack_vmc` step with pre-provided HDF5 + pseudopotentials.

### Phase 2: Full Step Coverage

**Scope**: Support all three step types with artifact chaining.

1. Add DMC materialization (VMC walker-gen + DMC in single input)
2. Add wfopt materialization (loop optimization)
3. Implement wfopt → vmc/dmc artifact chaining (Jastrow extraction)
4. Add integration tests with real QMCPACK execution
5. Add pseudopotential staging logic

**Deliverable**: Can run wfopt → vmc → dmc pipeline.

### Phase 3: Cross-Engine Pipeline (Future)

**Scope**: Automated DFT → QMCPACK workflow.

1. Design calculation chaining mechanism (Option C from §11.2)
2. Implement predecessor calculation reference
3. Add `pw2qmcpack` conversion step or hook
4. End-to-end QE → QMCPACK test

**Deliverable**: Automated SCF → NSCF → pw2qmcpack → wfopt → VMC → DMC.

---

## 13. Test Plan

### 13.1 Unit Tests (no QMCPACK binary needed)

| Test | Description |
|------|-------------|
| `test_driver_registration` | QMCPACKDriver registers without errors |
| `test_step_type_specs` | All 3 StepTypeSpecs valid and resolve |
| `test_materialization_map` | GEN→SPEC map is purely derived |
| `test_recipe_materialize_vmc` | VMC materialization produces valid XML |
| `test_recipe_materialize_dmc` | DMC materialization produces valid XML |
| `test_recipe_materialize_wfopt` | Optimization materialization produces valid XML |
| `test_writer_vmc` | Writer generates correct VMC XML structure |
| `test_writer_dmc` | Writer generates correct VMC+DMC XML structure |
| `test_writer_wfopt` | Writer generates correct optimization XML structure |
| `test_parser_scalar_dat` | Parser reads golden scalar.dat correctly |
| `test_parser_dmc_dat` | Parser reads golden dmc.dat correctly |
| `test_parser_stdout` | Parser extracts success + section summaries |
| `test_parser_opt_xml` | Parser extracts Jastrow coefficients from .opt.xml |
| `test_preflight_checks` | Preflight validates HDF5 + pseudo presence |
| `test_error_classification` | Error classifier handles known error patterns |

### 13.2 Integration Tests (QMCPACK binary required)

| Test | Description | Marker |
|------|-------------|--------|
| `test_vmc_diamond` | Run VMC on diamond C (golden reference) | `@pytest.mark.qmcpack` |
| `test_dmc_diamond` | Run VMC+DMC on diamond C | `@pytest.mark.qmcpack` |
| `test_wfopt_h4` | Run optimization+VMC on H4 | `@pytest.mark.qmcpack` |

These tests use `@pytest.mark.qmcpack` and skip if the binary is not available.

### 13.3 Gate Compliance

| Gate | Expected Result |
|------|----------------|
| No underscore in GEN steps | `vmc`, `dmc`, `wfopt` — PASS |
| `SUPPORTED_GEN_STEPS ⊆ GEN_STEPS` | After adding to registry — PASS |
| No manual join/split | Use `spec_from()`/`gen_from()` — PASS |
| Recipe roundtrip | `split(join("qmcpack", "vmc")) == ("qmcpack", "vmc")` — PASS |
| No prefix inference | Registry lookup only — PASS |
| Driver isolation | Only `drivers/qmcpack/` + `tests/` + `gen_steps.py` modified — needs justification for `gen_steps.py` |

---

## 14. Risks and Mitigations

| Risk | Impact | Mitigation |
|------|--------|------------|
| GenStepRegistry change breaks existing gates | Medium | Add new steps to gate allowlists |
| QMCPACK binary not available in CI | Low | Use `@pytest.mark.qmcpack` skip marker |
| HDF5 dependency for QE integration | Medium | v1 uses pre-computed HDF5 (defer) |
| Multi-section output complicates parsing | Low | Parser already handles multi-series |
| Pseudopotential format confusion (UPF vs XML) | Medium | Separate `qmcpack_pseudo_map`, clear docs |
| `wfopt` name might not be intuitive | Low | Good `display_name` in StepTypeSpec |

---

## 15. Files Changed Summary

### Kernel (requires justification)

| File | Change |
|------|--------|
| `src/qmatsuite/workflow/gen_steps.py` | Add `"vmc"`, `"dmc"`, `"wfopt"` to `GEN_STEPS` |

### New Files (driver bundle)

| File | Purpose |
|------|---------|
| `src/qmatsuite/drivers/qmcpack/__init__.py` | Registration |
| `src/qmatsuite/drivers/qmcpack/driver.py` | Driver class |
| `src/qmatsuite/drivers/qmcpack/handler.py` | Step handler |
| `src/qmatsuite/drivers/qmcpack/recipe.py` | Recipe class |
| `src/qmatsuite/drivers/qmcpack/writer.py` | XML writer |
| `src/qmatsuite/drivers/qmcpack/parser.py` | Output parser |
| `src/qmatsuite/drivers/qmcpack/pseudo_map.py` | Pseudo utilities |

### Modified Files (non-kernel)

| File | Change |
|------|--------|
| `src/qmatsuite/drivers/__init__.py` | Add `qmcpack` import |

### Test Files

| File | Purpose |
|------|---------|
| `tests/drivers/test_qmcpack_driver.py` | Unit + integration tests |
| `tests/drivers/qmcpack_golden/` | Golden reference fixtures |

---

## 16. Open Questions

1. **Should `wfopt` be a separate step or a parameter on VMC?**
   Recommendation: Separate step. Optimization produces different output files
   (`.opt.xml`), has different parameters, and serves a fundamentally different
   purpose than energy evaluation.

2. **Should DMC include the VMC walker-generation internally?**
   Recommendation: Yes. The VMC walker-gen is a technical requirement of DMC,
   not a user-meaningful separate step. The DMC step's XML contains both
   sections but only the DMC results are exposed to the user.

3. **Should we support AFQMC?**
   Not in v1. AFQMC uses a completely different input format and workflow
   (FCIDUMP Hamiltonian). It could be added as `qmcpack_afqmc` later if the
   `afqmc` GEN step is added to GenStepRegistry.

4. **Should the HDF5 wavefunction path be in `step.yaml` or `calculation.yaml`?**
   Recommendation: `calculation.yaml` (shared across all QMCPACK steps in the
   calculation). The HDF5 file is a property of the system, not of a specific
   QMC step.

5. **Naming: `qmcpack` vs `qmc` for PREFIX?**
   Recommendation: `qmcpack`. The PREFIX should identify the specific code,
   not the method family. Other QMC codes (CASINO, TurboRVB) would have their
   own prefixes. This follows the existing pattern (engine prefix = code name).

---

**End of Integration Plan**
