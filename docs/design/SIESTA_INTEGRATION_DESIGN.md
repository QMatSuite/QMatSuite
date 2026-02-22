# SIESTA Integration Design for QMatSuite (Constitution-Aligned)

**Version:** 2.0
**Author:** Claude Opus 4.5
**Date:** January 27, 2026
**Status:** Ready for Review

---

## Executive Summary

This document specifies the constitution-aligned integration of SIESTA into QMatSuite. The design follows existing engine patterns (QE, ORCA, PySCF, LAMMPS, CP2K) and respects all invariants from `CONSTITUTION_ZH.md`.

**Key Design Decisions:**
- **SystemLabel**: ULID-derived (stable, deterministic), NOT slug
- **Pseudopotentials**: Use existing `species_map` in `calculation.yaml` (no new SSOT)
- **Artifact Dependencies**: Explicit `hamiltonian_from`/`restart_from` refs (no scanning)
- **Step Types**: Map to existing GEN types (`RELAX` not `VC_RELAX`)
- **Core Changes**: **Zero required** - uses existing infrastructure

---

## Table of Contents

1. [Step Types and Mapping](#1-step-types-and-mapping)
2. [Directory/Workdir Policy](#2-directoryworkdir-policy)
3. [SystemLabel Convention](#3-systemlabel-convention)
4. [Pseudopotential/species_map Alignment](#4-pseudopotentialspecies_map-alignment)
5. [Artifact Model and Staging Rules](#5-artifact-model-and-staging-rules)
6. [Materialize and Run Flow](#6-materialize-and-run-flow)
7. [Minimal Parser Expectations](#7-minimal-parser-expectations)
8. [Testing Plan](#8-testing-plan)
9. [Core Changes Section](#9-core-changes-section)

---

## 1. Step Types and Mapping

### 1.1 Machine Step Types (SPEC)

Following the `{engine}_{public_type}` naming convention:

| Machine Type | Engine | Executable | Description | is_structure_transform |
|--------------|--------|------------|-------------|------------------------|
| `siesta_scf` | siesta | siesta | Single-point SCF energy | `False` |
| `siesta_relax` | siesta | siesta | Geometry optimization (fixed or variable cell) | `True` |
| `siesta_md` | siesta | siesta | Molecular dynamics (Verlet/Nose/etc.) | `False` |
| `siesta_bands` | siesta | siesta | Band structure along k-path | `False` |
| `siesta_dos` | siesta | siesta | Density of states (PDOS) | `False` |

**Note:** Variable-cell relaxation is a parameter of `siesta_relax` (`MD.VariableCell = T`), NOT a separate step type. This aligns with Constitution rule: "RELAX is a structure transformer; public step type must remain `relax` (do not introduce public `vc_relax`)."

### 1.2 GEN-to-SPEC Materialization Map

```python
# In workflow/generalized_steps.py MATERIALIZATION_MAP additions:
("siesta", "SCF"): "siesta_scf",
("siesta", "NSCF"): None,  # SIESTA doesn't have distinct NSCF; bands handles this
("siesta", "RELAX"): "siesta_relax",
("siesta", "VC_RELAX"): "siesta_relax",  # Maps to same step type (param controls cell)
("siesta", "BANDS"): "siesta_bands",
("siesta", "BANDS_POST"): None,  # 0-mapping: gnubands is external utility
("siesta", "DOS"): "siesta_dos",
("siesta", "MD"): "siesta_md",
```

### 1.3 StepTypeSpec Registration

```python
# In drivers/siesta/step_types.py
SIESTA_STEP_TYPE_SPECS: list[StepTypeSpec] = [
    StepTypeSpec(
        id="scf",
        machine_type="siesta_scf",
        public_type="scf",
        engine="siesta",
        executable="siesta",
        description="SIESTA single-point SCF calculation",
        requires_structure=True,
        produces_charge_density=True,  # .DM file
        produces_state="dm",
        supports_incremental_skip=True,
        is_structure_transform=False,
        token="s",
    ),
    StepTypeSpec(
        id="relax",
        machine_type="siesta_relax",
        public_type="relax",
        engine="siesta",
        executable="siesta",
        description="SIESTA geometry optimization",
        requires_structure=True,
        produces_charge_density=True,
        produces_state="dm",
        supports_incremental_skip=False,  # Always rerun (structure changes)
        is_structure_transform=True,  # CRITICAL: Produces structure artifact
        token="r",
    ),
    StepTypeSpec(
        id="md",
        machine_type="siesta_md",
        public_type="md",
        engine="siesta",
        executable="siesta",
        description="SIESTA molecular dynamics",
        requires_structure=True,
        supports_incremental_skip=False,  # Always rerun
        consumes_state="xv",  # Can consume restart .XV
        produces_state="xv",
        is_structure_transform=False,
        token="d",
    ),
    StepTypeSpec(
        id="bands",
        machine_type="siesta_bands",
        public_type="bands",
        engine="siesta",
        executable="siesta",
        description="SIESTA band structure calculation",
        requires_structure=True,
        consumes_state="tshs",  # Requires .TSHS from SCF
        supports_incremental_skip=True,
        is_structure_transform=False,
        token="b",
    ),
    StepTypeSpec(
        id="dos",
        machine_type="siesta_dos",
        public_type="dos",
        engine="siesta",
        executable="siesta",
        description="SIESTA density of states",
        requires_structure=True,
        consumes_state="dm",  # Requires .DM from SCF
        supports_incremental_skip=True,
        is_structure_transform=False,
        token="o",
    ),
]
```

---

## 2. Directory/Workdir Policy

### 2.1 Policy: ISOLATED (Per-Step Subdirectories)

SIESTA uses **ISOLATED workdir policy** like VASP/LAMMPS/CP2K (NOT shared like QE).

**Rationale:** SIESTA writes all output files to CWD based on `SystemLabel`. Using isolated subdirectories prevents filename collisions and enables clean artifact management.

```
calc/
  calculation.yaml
  steps/
    scf.step.yaml      # Contains step_id (ULID)
    relax.step.yaml
  raw/                 # calc_raw_dir (working directory)
    {step_ulid_1}/     # Per-step isolated workdir
      input.fdf        # Generated input (clean rewrite)
      Si.psml          # Staged pseudopotentials
      O.psml
      {label}.out      # Redirected stdout
      {label}.DM       # Density matrix (restart artifact)
      {label}.TSHS     # Hamiltonian (for bands/transport)
      {label}.XV       # Positions+velocities (MD restart)
      ...
    {step_ulid_2}/
      input.fdf
      {label}.DM       # Staged from step_ulid_1 (renamed)
      ...
  generated_structures/
    step_{relax_ulid}/
      current.json     # Final structure from relax (Constitution contract)
```

### 2.2 Comparison with Existing Engines

| Engine | Workdir Policy | Subdirectory Key | Shared Scratch |
|--------|---------------|------------------|----------------|
| **QE** | SHARED | None (all in `raw/`) | `raw/outdir/` (prefix-keyed) |
| **VASP** | ISOLATED | `{step_ulid}/` | None |
| **LAMMPS** | ISOLATED | `{step_ulid}/` | None |
| **CP2K** | ISOLATED (no cleanup) | `{step_ulid}/` | None |
| **ORCA** | ISOLATED | `scf_{suffix}/` (chain namespace) | None |
| **PySCF** | ISOLATED | `scf_{suffix}/` (chain namespace) | None |
| **SIESTA** | ISOLATED | `{step_ulid}/` | None |

---

## 3. SystemLabel Convention

### 3.1 Rule: ULID-Derived, NOT Slug

Per Constitution: "slug is presentation only (stored only in resource's own meta.slug), must NEVER become runtime semantics (no SystemLabel = slug, no directory keys = slug)."

**SystemLabel Algorithm:**
```python
def siesta_system_label(step_ulid: str) -> str:
    """
    Generate SIESTA SystemLabel from step ULID.

    Per Constitution: ULID-derived, deterministic, stable across renames.

    Format: "si" + last 8 chars of ULID (lowercase)
    - "si" prefix identifies SIESTA-generated labels
    - 8 chars provides uniqueness within project
    - Total: 10 chars (well under SIESTA's limits)

    Example:
        step_ulid = "01KC38NVA0NES3T6YG7DK8DP82"
        → "sidk8dp82"
    """
    return "si" + step_ulid[-8:].lower()
```

**Consistency with QE:**
- QE uses `"qms" + ULID[-6:]` for prefix (e.g., `qmsg5fav`)
- SIESTA uses `"si" + ULID[-8:]` for SystemLabel (e.g., `sidk8dp82`)
- Both are ULID-derived, stable, and deterministic

### 3.2 FDF Generation

```fdf
# Generated by SiestaRecipe.materialize()
SystemName  QMatSuite Calculation
SystemLabel sidk8dp82

# ... structure, parameters, etc. ...
```

### 3.3 Output File Names

All SIESTA outputs use SystemLabel prefix:
- `sidk8dp82.out` (stdout redirect)
- `sidk8dp82.DM` (density matrix)
- `sidk8dp82.TSHS` (Hamiltonian)
- `sidk8dp82.XV` (MD restart)
- `sidk8dp82.bands` (band data)
- etc.

---

## 4. Pseudopotential/species_map Alignment

### 4.1 SSOT: calculation.yaml species_map

Per Constitution: "Project-run pseudo/species SSOT: `calculation.yaml: species_map`. No third SSOT."

SIESTA pseudopotentials (PSF, PSML, VPS) are integrated into the **existing** `species_map` mechanism, NOT a new SSOT.

### 4.2 Extended species_map Schema

```yaml
# calculation.yaml
species_map:
  Si:
    # Existing QE fields (backward compatible)
    pseudopot: Si.pbe-n-kjpaw_psl.1.0.0.UPF      # QE pseudo filename
    pseudo_sha256: abc123...                      # SHA256 of UPF file
    pseudo_sha_family: def456...                  # Physical equivalence hash
    mass: 28.0855

    # NEW: Engine-specific pseudo assets (optional)
    siesta_pseudo:
      filename: Si.psml                           # SIESTA pseudo filename
      format: psml                                # psml | psf | vps
      sha256: xyz789...                           # SHA256 of SIESTA pseudo

  O:
    pseudopot: O.pbe-n-kjpaw_psl.1.0.0.UPF
    pseudo_sha256: ...
    siesta_pseudo:
      filename: O.psml
      format: psml
      sha256: ...
```

### 4.3 Pseudo Resolution Algorithm

```python
def resolve_siesta_pseudo(element: str, species_map: dict) -> Path:
    """
    Resolve SIESTA pseudopotential for an element.

    Priority:
    1. species_map[element]["siesta_pseudo"]["filename"] (explicit SIESTA pseudo)
    2. species_map[element]["pseudopot"] with .psml/.psf/.vps extension (implicit)
    3. Default library lookup by element+functional (fallback)
    """
    element_map = species_map.get(element, {})

    # Priority 1: Explicit siesta_pseudo
    siesta_pseudo = element_map.get("siesta_pseudo")
    if siesta_pseudo:
        return siesta_pseudo["filename"]

    # Priority 2: pseudopot with SIESTA extension
    pseudopot = element_map.get("pseudopot", "")
    if pseudopot.endswith((".psml", ".psf", ".vps")):
        return pseudopot

    # Priority 3: Fallback to default (from installed library)
    # Uses same library infrastructure as QE
    raise ValueError(f"No SIESTA pseudopotential found for {element}")
```

### 4.4 Pseudo Staging (Materialize Time)

```python
def stage_siesta_pseudos(
    species_map: dict,
    working_dir: Path,
    project_root: Path,
) -> dict[str, Path]:
    """
    Stage SIESTA pseudopotentials into step working directory.

    Similar to QE's materialize_calc_pseudos but for SIESTA formats.
    """
    staged = {}

    for element, settings in species_map.items():
        siesta_pseudo = settings.get("siesta_pseudo", {})
        filename = siesta_pseudo.get("filename")
        sha256 = siesta_pseudo.get("sha256")

        if not filename:
            # Skip elements without SIESTA pseudo
            continue

        # Resolve source path (project/pseudo or library)
        source_path = resolve_pseudo_source(
            filename=filename,
            sha256=sha256,
            project_root=project_root,
        )

        # Copy to working directory
        target_path = working_dir / filename
        shutil.copy2(source_path, target_path)

        # Verify SHA256 after copy
        if sha256:
            actual_sha = compute_sha256_file(target_path)
            if actual_sha != sha256:
                raise ValueError(f"SHA256 mismatch for {element} pseudo")

        staged[element] = target_path

    return staged
```

### 4.5 pseudo_set_sha for Manifest

```python
def compute_siesta_pseudo_set_sha(species_map: dict) -> str:
    """
    Compute SHA256 hash of SIESTA pseudo set.

    Only includes elements with siesta_pseudo defined.
    """
    tokens = []
    for element, settings in sorted(species_map.items()):
        siesta_pseudo = settings.get("siesta_pseudo", {})
        sha256 = siesta_pseudo.get("sha256")
        if sha256:
            tokens.append(f"{element}:{sha256}")

    combined = "|".join(tokens)
    return hashlib.sha256(combined.encode()).hexdigest()
```

---

## 5. Artifact Model and Staging Rules

### 5.1 Explicit Refs (NOT Scanning)

Per Constitution: "Artifact dependencies must be deterministic. Avoid 'scan raw and pick nearest' as the primary mechanism. Prefer explicit upstream refs."

SIESTA artifacts are referenced via **explicit step ULID refs** in step parameters:

```yaml
# calculation.yaml - Step definitions
steps:
- step_id: 01KC38NVA0NES3T6YG7DK8DP82
  type: scf
  # ... parameters ...

- step_id: 01KC38P68GFY8CSNGKWZJRZ50E
  type: bands
  parameters:
    hamiltonian_from: 01KC38NVA0NES3T6YG7DK8DP82  # EXPLICIT ref to SCF step
    # ... other parameters ...

- step_id: 01KC38PGMYFABDDE5T6CA8A2J8
  type: md
  parameters:
    restart_from: 01KC38P68GFY8CSNGKWZJRZ50E      # EXPLICIT ref to previous MD
```

### 5.2 Artifact Types and Files

| Artifact Type | File Pattern | Produced By | Consumed By |
|---------------|-------------|-------------|-------------|
| `dm` | `{label}.DM` | `siesta_scf`, `siesta_relax` | `siesta_dos`, restart |
| `tshs` | `{label}.TSHS` | `siesta_scf` | `siesta_bands` |
| `xv` | `{label}.XV` | `siesta_md`, `siesta_relax` | `siesta_md` (restart) |
| `structure` | `generated_structures/step_{ulid}/current.json` | `siesta_relax` | Downstream steps |

### 5.3 Artifact Staging Algorithm

```python
def stage_siesta_artifacts(
    step: "Step",
    calculation: "Calculation",
    working_dir: Path,
) -> dict[str, Path]:
    """
    Stage artifacts from upstream steps into current step's working directory.

    Per Constitution: Uses EXPLICIT refs, not scanning.
    """
    staged = {}
    params = step.parameters or {}

    # Get current step's SystemLabel
    current_label = siesta_system_label(step.meta.id)

    # 1. Handle hamiltonian_from (for bands)
    hamiltonian_from = params.get("hamiltonian_from")
    if hamiltonian_from:
        source_label = siesta_system_label(hamiltonian_from)
        source_dir = calculation.raw_dir / hamiltonian_from
        source_tshs = source_dir / f"{source_label}.TSHS"

        if not source_tshs.exists():
            raise MissingArtifactError(
                f"MISSING_ARTIFACT_ERROR: Step requires Hamiltonian from "
                f"step '{hamiltonian_from}' but {source_tshs} is missing."
            )

        # Copy and rename to match current SystemLabel
        target_tshs = working_dir / f"{current_label}.TSHS"
        shutil.copy2(source_tshs, target_tshs)
        staged["tshs"] = target_tshs

    # 2. Handle restart_from (for MD continuation)
    restart_from = params.get("restart_from")
    if restart_from:
        source_label = siesta_system_label(restart_from)
        source_dir = calculation.raw_dir / restart_from
        source_xv = source_dir / f"{source_label}.XV"

        if not source_xv.exists():
            raise MissingArtifactError(
                f"MISSING_ARTIFACT_ERROR: Step requires restart from "
                f"step '{restart_from}' but {source_xv} is missing."
            )

        # Copy and rename to match current SystemLabel
        target_xv = working_dir / f"{current_label}.XV"
        shutil.copy2(source_xv, target_xv)
        staged["xv"] = target_xv

    # 3. Handle dm_from (optional, for SCF restart)
    dm_from = params.get("dm_from")
    if dm_from:
        source_label = siesta_system_label(dm_from)
        source_dir = calculation.raw_dir / dm_from
        source_dm = source_dir / f"{source_label}.DM"

        if source_dm.exists():  # DM is optional for restart
            target_dm = working_dir / f"{current_label}.DM"
            shutil.copy2(source_dm, target_dm)
            staged["dm"] = target_dm

    return staged
```

### 5.4 Relax Structure Artifact

For `siesta_relax` steps, the final structure is written to the standard location:

```
generated_structures/step_{relax_ulid}/current.json
```

This follows the existing `RelaxArtifactSpec` pattern:

```python
# In siesta_handler, after successful relax:
if success and is_relax_step_type(step.step_type):
    struct_out = working_dir / f"{label}.STRUCT_OUT"
    if struct_out.exists():
        step_result_data["relax_artifact_spec"] = RelaxArtifactSpec(
            artifact_type="siesta_struct_out",
            artifact_path=struct_out,
            step_ulid=step.meta.id,
            step_type=str(step.step_type),
        ).to_dict()
```

Register the handler in `RELAX_ARTIFACT_HANDLERS`:

```python
RELAX_ARTIFACT_HANDLERS["siesta_struct_out"] = _handle_siesta_struct_out

def _handle_siesta_struct_out(spec, calc_dir, run_context) -> Path:
    """Parse .STRUCT_OUT and write current.json."""
    struct_out = spec.artifact_path
    structure = parse_siesta_struct_out(struct_out)
    canonicalize_structure_like_in_place(structure)

    return write_generated_structure(
        structure=structure,
        calc_dir=calc_dir,
        step_ulid=spec.step_ulid,
        step_type=spec.step_type,
        run_id=run_context.get("run_id"),
        calculation_ulid=run_context.get("calculation_ulid", ""),
        input_structure_ulid=run_context.get("input_structure_ulid", ""),
    )
```

---

## 6. Materialize and Run Flow

### 6.1 Recipe: SiestaRecipe

```python
# In drivers/siesta/recipe.py
class SiestaRecipe(BaseRecipe):
    """
    SIESTA Recipe: Per-step isolated workdir model.

    Creates one job per step with isolated working directories.
    Similar to LAMMPS/VASP recipes.
    """

    def materialize(
        self,
        steps: List["Step"],
        calc_raw_dir: Path,
        step_shas: Optional[Dict[str, str]] = None,
    ) -> JobGraph:
        """Materialize one job per SIESTA step."""
        jobs: List[Job] = []

        for idx, step in enumerate(steps):
            step_ulid = step.meta.id
            step_type = step.step_type

            # Per-step isolated working directory
            working_dir = calc_raw_dir / step_ulid

            # SystemLabel from ULID
            label = siesta_system_label(step_ulid)

            # Input file name (clean rewrite target)
            input_file = "input.fdf"

            # Expected outputs
            expected_outputs = [
                working_dir / f"{label}.out",
            ]

            # Add structure artifact for relax steps
            if is_relax_step_type(step_type):
                # Relax produces .STRUCT_OUT
                expected_outputs.append(working_dir / f"{label}.STRUCT_OUT")

            # Compute fingerprint for incremental skip
            fingerprint = step_shas.get(step_ulid) if step_shas else None

            # Build job
            job = Job(
                id=f"step_{idx:02d}",
                step_ids=[step_ulid],
                working_dir=working_dir,
                command=["siesta"],  # stdin redirect handled by handler
                input_files=[working_dir / input_file],
                expected_outputs=expected_outputs,
                deps=[],  # Conservative: linear execution order
                fingerprint=fingerprint,
                metadata={
                    "engine": "siesta",
                    "system_label": label,
                    "step_type": step_type,
                },
            )
            jobs.append(job)

        return JobGraph(jobs=jobs)
```

### 6.2 Materialize Step Spec (FDF Generation)

```python
# In drivers/siesta/fdf_writer.py
def materialize_siesta_fdf(
    step: "Step",
    calculation: "Calculation",
    working_dir: Path,
) -> Path:
    """
    Generate FDF input file for SIESTA step.

    Per Constitution: Clean rewrite materialization.
    - NEVER parse old engine inputs and merge/inject
    - Always generate fresh from step.yaml + calculation.yaml
    """
    # SystemLabel from ULID
    label = siesta_system_label(step.meta.id)

    # Start fresh FDF
    fdf_path = working_dir / "input.fdf"

    with open(fdf_path, 'w') as f:
        # System identification
        f.write(f"SystemName  QMatSuite Calculation\n")
        f.write(f"SystemLabel {label}\n\n")

        # Structure (from calculation.structure or generated_structure)
        structure = resolve_step_structure(step, calculation)
        write_fdf_structure(f, structure)

        # Parameters from step.yaml
        params = step.parameters or {}
        write_fdf_parameters(f, params, step.step_type)

        # XC functional
        xc = params.get("xc_functional", "PBE")
        f.write(f"XC.functional  GGA\n")
        f.write(f"XC.authors     {xc}\n\n")

        # Calculation type (depends on step_type)
        if step.step_type == "siesta_relax":
            variable_cell = params.get("variable_cell", False)
            write_fdf_relax_block(f, params, variable_cell)
        elif step.step_type == "siesta_md":
            write_fdf_md_block(f, params)
        elif step.step_type == "siesta_bands":
            write_fdf_bands_block(f, params)
        elif step.step_type == "siesta_dos":
            write_fdf_dos_block(f, params)

        # Output control
        f.write("SaveHS         true\n")
        f.write("WriteCoorXmol  true\n")

        # Restart files (based on staged artifacts)
        if params.get("restart_from"):
            f.write("MD.UseSaveXV   true\n")
        if params.get("dm_from"):
            f.write("DM.UseSaveDM   true\n")

    return fdf_path
```

### 6.3 Handler: siesta_step_handler

```python
# In drivers/siesta/handler.py
def siesta_step_handler(
    job: Job,
    calculation: "Calculation",
    engine_registry: "EngineRegistry",
    context: Dict[str, Any],
) -> JobResult:
    """
    Execute a single SIESTA step job.

    Follows same pattern as LAMMPS/CP2K handlers:
    1. Create isolated working directory
    2. Stage pseudopotentials
    3. Stage upstream artifacts (explicit refs)
    4. Generate FDF input (clean rewrite)
    5. Execute SIESTA
    6. Parse output
    7. Return JobResult with artifact spec
    """
    started = datetime.now(timezone.utc)

    # Step 1: Validate single-step job
    if len(job.step_ids) != 1:
        return JobResult(job_id=job.id, success=False, error="Expected single-step job")

    step_ulid = job.step_ids[0]
    step = _find_step_by_ulid(calculation, step_ulid)
    if step is None:
        return JobResult(job_id=job.id, success=False, error=f"Step {step_ulid} not found")

    # Step 2: Create isolated working directory
    working_dir = job.working_dir
    working_dir.mkdir(parents=True, exist_ok=True)

    try:
        # Step 3: Stage pseudopotentials
        staged_pseudos = stage_siesta_pseudos(
            species_map=calculation.species_map,
            working_dir=working_dir,
            project_root=calculation.project.root,
        )

        # Step 4: Stage upstream artifacts (explicit refs)
        staged_artifacts = stage_siesta_artifacts(
            step=step,
            calculation=calculation,
            working_dir=working_dir,
        )

        # Step 5: Generate FDF input (clean rewrite)
        fdf_path = materialize_siesta_fdf(
            step=step,
            calculation=calculation,
            working_dir=working_dir,
        )

        # Step 6: Execute SIESTA
        label = job.metadata["system_label"]
        stdout_path = working_dir / f"{label}.out"
        stderr_path = working_dir / f"{label}.err"

        with open(fdf_path, 'r') as fdf_in, \
             open(stdout_path, 'w') as stdout_out, \
             open(stderr_path, 'w') as stderr_out:

            result = subprocess.run(
                ["siesta"],
                stdin=fdf_in,
                stdout=stdout_out,
                stderr=stderr_out,
                cwd=working_dir,
            )

        # Step 7: Parse output
        success = result.returncode == 0
        if success:
            stdout_text = stdout_path.read_text()
            if "FATAL" in stdout_text or "ERROR" in stdout_text:
                success = False

        # Step 8: Build JobResult
        step_result_data = {
            "success": success,
            "output_file": str(stdout_path),
            "return_code": result.returncode,
        }

        # Add relax artifact spec if applicable
        step_type = step.step_type
        if success and is_relax_step_type(step_type):
            struct_out = working_dir / f"{label}.STRUCT_OUT"
            if struct_out.exists():
                step_result_data["relax_artifact_spec"] = RelaxArtifactSpec(
                    artifact_type="siesta_struct_out",
                    artifact_path=struct_out,
                    step_ulid=step_ulid,
                    step_type=str(step_type),
                ).to_dict()

        return JobResult(
            job_id=job.id,
            success=success,
            error=None if success else f"SIESTA failed with return code {result.returncode}",
            started_at=started,
            finished_at=datetime.now(timezone.utc),
            step_results={step_ulid: step_result_data},
        )

    except Exception as e:
        import traceback
        return JobResult(
            job_id=job.id,
            success=False,
            error=f"{type(e).__name__}: {e}\n{traceback.format_exc()[:500]}",
            started_at=started,
            finished_at=datetime.now(timezone.utc),
        )
```

### 6.4 Run Calc vs Run Step

SIESTA follows the same Run Calc / Run Step semantics as other engines:

**Run Calc (Incremental):**
- Manifest checks step_sha, structure_sha, pseudo_set_sha
- Steps with matching SHAs and `done=True` are skipped
- Modified steps and downstream are rerun

**Run Step (TARGET):**
- Target step is ALWAYS rerun (per Constitution)
- Prerequisite steps may use incremental semantics
- `SelectionMode.TARGET` with `target_step_id` parameter

---

## 7. Minimal Parser Expectations

### 7.1 Primary Output Parser

```python
# In drivers/siesta/parsers/output_parser.py
@dataclass
class SiestaParseResult:
    final_energy: Optional[float] = None
    forces: Optional[np.ndarray] = None
    stress: Optional[np.ndarray] = None
    scf_converged: bool = False
    md_steps: int = 0

def parse_siesta_output(output_path: Path) -> SiestaParseResult:
    """
    Parse SIESTA stdout output.

    Minimal parsing for:
    - Final energy (required)
    - SCF convergence status (required)
    - Forces (optional, for relax/MD)
    - Stress (optional, for vc-relax)
    """
    text = output_path.read_text()
    result = SiestaParseResult()

    # Final energy
    energy_match = re.search(r"siesta:\s+Total\s+=\s+([-\d.]+)", text)
    if energy_match:
        result.final_energy = float(energy_match.group(1))

    # SCF convergence
    result.scf_converged = "scf: converged" in text.lower()

    # Forces (last occurrence)
    forces_section = re.findall(
        r"siesta: Atomic forces.*?\n((?:siesta:\s+[-\d.\s]+\n)+)",
        text, re.DOTALL
    )
    if forces_section:
        force_lines = re.findall(
            r"siesta:\s+([-\d.]+)\s+([-\d.]+)\s+([-\d.]+)",
            forces_section[-1]
        )
        result.forces = np.array([[float(x), float(y), float(z)]
                                   for x, y, z in force_lines])

    # MD step count
    md_steps = re.findall(r"Begin MD step =\s+(\d+)", text)
    if md_steps:
        result.md_steps = int(md_steps[-1])

    return result
```

### 7.2 Structure Parser (.STRUCT_OUT)

```python
def parse_siesta_struct_out(struct_out_path: Path) -> dict:
    """
    Parse SIESTA .STRUCT_OUT file into QMatSuite structure dict.

    .STRUCT_OUT is in FDF format with LatticeVectors and AtomicCoordinates.
    """
    text = struct_out_path.read_text()

    # Parse lattice vectors
    lattice_match = re.search(
        r"%block LatticeVectors\n(.*?)%endblock LatticeVectors",
        text, re.DOTALL
    )
    lattice = []
    if lattice_match:
        for line in lattice_match.group(1).strip().split('\n'):
            parts = line.split()
            if len(parts) >= 3:
                lattice.append([float(parts[0]), float(parts[1]), float(parts[2])])

    # Parse atomic coordinates
    coords_match = re.search(
        r"%block AtomicCoordinatesAndAtomicSpecies\n(.*?)%endblock",
        text, re.DOTALL
    )
    atoms = []
    if coords_match:
        for line in coords_match.group(1).strip().split('\n'):
            parts = line.split()
            if len(parts) >= 4:
                x, y, z = float(parts[0]), float(parts[1]), float(parts[2])
                species_idx = int(parts[3])
                atoms.append({
                    "frac_coords": [x, y, z],
                    "species_index": species_idx,
                })

    # Parse species labels
    species_match = re.search(
        r"%block ChemicalSpeciesLabel\n(.*?)%endblock",
        text, re.DOTALL
    )
    species = {}
    if species_match:
        for line in species_match.group(1).strip().split('\n'):
            parts = line.split()
            if len(parts) >= 3:
                idx = int(parts[0])
                element = parts[2]
                species[idx] = element

    # Build structure dict
    return {
        "lattice": lattice,
        "atoms": [
            {
                "element": species.get(a["species_index"], "X"),
                "frac_coords": a["frac_coords"],
            }
            for a in atoms
        ],
        "unit": "angstrom",
    }
```

### 7.3 Step Done Policy

```python
# In calculation/step_done.py - Add SIESTA case
def is_step_done_siesta(calc_raw_dir: Path, step_ulid: str, step_type: str) -> bool:
    """
    Check if a SIESTA step has completed successfully.

    Criteria:
    - Output file exists
    - Contains "Job completed" or similar marker
    - No "FATAL" or "ERROR" in output
    """
    label = siesta_system_label(step_ulid)
    output_path = calc_raw_dir / step_ulid / f"{label}.out"

    if not output_path.exists():
        return False

    try:
        text = output_path.read_text()

        # Check for fatal errors
        if "FATAL" in text or "ERROR:" in text:
            return False

        # Check for success markers
        if "Job completed" in text:
            return True

        # For relax: check .STRUCT_OUT exists
        if step_type == "siesta_relax":
            struct_out = calc_raw_dir / step_ulid / f"{label}.STRUCT_OUT"
            return struct_out.exists()

        # For SCF/DOS: check energy present
        if "siesta: Total =" in text:
            return True

        return False
    except Exception:
        return False
```

---

## 8. Testing Plan

### 8.1 Test Matrix

| Test Case | Structure Kind | Workflow | Assertions |
|-----------|---------------|----------|------------|
| `test_siesta_scf_molecule` | molecule | SCF only | Energy parsed, .DM exists |
| `test_siesta_scf_periodic` | periodic | SCF only | Energy parsed, .TSHS exists |
| `test_siesta_relax` | periodic | RELAX | Structure artifact in `generated_structures/` |
| `test_siesta_scf_bands` | periodic | SCF → BANDS | .bands file exists, hamiltonian_from staging works |
| `test_siesta_scf_dos` | periodic | SCF → DOS | .PDOS file exists |
| `test_siesta_md_restart` | molecule | MD → MD | .XV staging, trajectory continuation |
| `test_siesta_incremental` | periodic | SCF (twice) | Second run skips if unchanged |

### 8.2 Integration Test Structure

```python
# tests/integration/siesta/test_siesta_workflows.py
import pytest
from qmatsuite.api.service import QMSService

@pytest.fixture
def siesta_project(tmp_path):
    """Create test project with SIESTA calculation."""
    service = QMSService(project_root=tmp_path)

    # Create project
    project = service.create_project(name="siesta_test")

    # Create structure (Silicon primitive cell)
    structure = service.create_structure(
        project_id=project.id,  # ULID
        name="Si",
        atoms=[
            {"element": "Si", "frac_coords": [0.0, 0.0, 0.0]},
            {"element": "Si", "frac_coords": [0.25, 0.25, 0.25]},
        ],
        lattice=[
            [0.0, 2.715, 2.715],
            [2.715, 0.0, 2.715],
            [2.715, 2.715, 0.0],
        ],
    )

    return project, structure


def test_siesta_scf_periodic(siesta_project):
    """Test basic SCF calculation."""
    project, structure = siesta_project
    service = QMSService(project_root=project.root)

    # Create calculation
    calc = service.create_calculation(
        project_id=project.id,
        structure_id=structure.id,  # ULID selector
        name="Si SCF",
        engine_family="siesta",
        structure_kind="periodic",
        species_map={
            "Si": {
                "siesta_pseudo": {
                    "filename": "Si.psml",
                    "format": "psml",
                    "sha256": "...",  # From installed library
                },
            },
        },
    )

    # Add SCF step
    scf_step = service.add_step(
        calculation_id=calc.id,
        step_type="siesta_scf",
        parameters={
            "xc_functional": "PBE",
            "mesh_cutoff": {"value": 200, "unit": "Ry"},
            "basis_size": "DZP",
            "k_grid": [4, 4, 4],
        },
    )

    # Run calculation
    result = service.run_calculation(calculation_id=calc.id)

    # Assertions
    assert result.success

    # Check output file exists
    output_path = calc.raw_dir / scf_step.id / f"si{scf_step.id[-8:].lower()}.out"
    assert output_path.exists()

    # Check DM file exists (restart artifact)
    dm_path = calc.raw_dir / scf_step.id / f"si{scf_step.id[-8:].lower()}.DM"
    assert dm_path.exists()

    # Check manifest updated
    manifest = service.get_manifest(calculation_id=calc.id)
    assert manifest.steps[0].done is True
    assert manifest.steps[0].step_ulid == scf_step.id


def test_siesta_relax_structure_artifact(siesta_project):
    """Test that relax produces structure artifact."""
    project, structure = siesta_project
    service = QMSService(project_root=project.root)

    # Create calculation with relax step
    calc = service.create_calculation(
        project_id=project.id,
        structure_id=structure.id,
        name="Si Relax",
        engine_family="siesta",
        structure_kind="periodic",
        species_map={...},
    )

    relax_step = service.add_step(
        calculation_id=calc.id,
        step_type="siesta_relax",
        parameters={
            "variable_cell": True,
            "max_force_tol": {"value": 0.04, "unit": "eV/Ang"},
            "max_cg_steps": 100,
        },
    )

    # Run
    result = service.run_calculation(calculation_id=calc.id)
    assert result.success

    # Check generated structure artifact
    artifact_path = calc.dir / "generated_structures" / f"step_{relax_step.id}" / "current.json"
    assert artifact_path.exists()

    # Verify structure content
    import json
    with open(artifact_path) as f:
        final_structure = json.load(f)
    assert "lattice" in final_structure
    assert "atoms" in final_structure


def test_siesta_scf_bands_explicit_ref(siesta_project):
    """Test bands calculation with explicit hamiltonian_from ref."""
    project, structure = siesta_project
    service = QMSService(project_root=project.root)

    calc = service.create_calculation(
        project_id=project.id,
        structure_id=structure.id,
        name="Si Bands",
        engine_family="siesta",
        structure_kind="periodic",
        species_map={...},
    )

    # Step 1: SCF
    scf_step = service.add_step(
        calculation_id=calc.id,
        step_type="siesta_scf",
        parameters={...},
    )

    # Step 2: Bands with EXPLICIT ref
    bands_step = service.add_step(
        calculation_id=calc.id,
        step_type="siesta_bands",
        parameters={
            "hamiltonian_from": scf_step.id,  # EXPLICIT ULID ref
            "band_lines": [
                {"npts": 1, "k": [0, 0, 0], "label": "Gamma"},
                {"npts": 40, "k": [0.5, 0, 0.5], "label": "X"},
                {"npts": 40, "k": [0.5, 0.5, 0.5], "label": "L"},
                {"npts": 40, "k": [0, 0, 0], "label": "Gamma"},
            ],
        },
    )

    # Run
    result = service.run_calculation(calculation_id=calc.id)
    assert result.success

    # Check .TSHS was staged
    bands_workdir = calc.raw_dir / bands_step.id
    bands_label = f"si{bands_step.id[-8:].lower()}"
    tshs_path = bands_workdir / f"{bands_label}.TSHS"
    assert tshs_path.exists()

    # Check bands file
    bands_path = bands_workdir / f"{bands_label}.bands"
    assert bands_path.exists()


def test_siesta_incremental_skip(siesta_project):
    """Test incremental skip when step unchanged."""
    project, structure = siesta_project
    service = QMSService(project_root=project.root)

    calc = service.create_calculation(...)
    scf_step = service.add_step(...)

    # First run
    result1 = service.run_calculation(calculation_id=calc.id)
    assert result1.success

    # Record mtime
    output_path = calc.raw_dir / scf_step.id / f"si{scf_step.id[-8:].lower()}.out"
    mtime1 = output_path.stat().st_mtime

    # Second run (should skip)
    result2 = service.run_calculation(calculation_id=calc.id)
    assert result2.success

    # mtime should be unchanged (step was skipped)
    mtime2 = output_path.stat().st_mtime
    assert mtime1 == mtime2
```

### 8.3 Test Data Setup

```
tests/data/siesta/
  pseudos/
    Si.psml
    O.psml
    H.vps
  structures/
    si_primitive.json
    h2o.json
```

---

## 9. Core Changes Section

### 9.1 Required Core Changes: **NONE**

The SIESTA integration requires **zero changes** to core infrastructure:

| Component | Changes Required |
|-----------|------------------|
| `calculation.yaml` schema | None - uses existing `species_map` with optional `siesta_pseudo` field |
| `step.yaml` schema | None - uses existing `parameters` dict |
| Runner (`runner.py`) | None - uses existing JobGraph execution |
| Manifest (`manifest.py`) | None - uses existing SHA-based skip logic |
| StepDonePolicy (`step_done.py`) | Minor addition: Add SIESTA completion check pattern |
| RelaxArtifacts (`relax_artifacts.py`) | Minor addition: Register `siesta_struct_out` handler |
| MATERIALIZATION_MAP | Addition only: Add SIESTA mappings |
| DriverRegistry | Addition only: Register SiestaDriver |

### 9.2 New Files (Additions Only)

```
src/qmatsuite/drivers/siesta/
  __init__.py              # Driver registration
  driver.py                # SiestaDriver class
  step_types.py            # SIESTA_STEP_TYPE_SPECS
  handler.py               # siesta_step_handler
  recipe.py                # SiestaRecipe
  fdf_writer.py            # FDF generation
  parsers/
    __init__.py
    output_parser.py       # Parse .out files
    struct_out_parser.py   # Parse .STRUCT_OUT files
```

### 9.3 Minor Additions to Existing Files

1. **`workflow/generalized_steps.py`**: Add SIESTA entries to `MATERIALIZATION_MAP`
2. **`execution/relax_artifacts.py`**: Add `siesta_struct_out` to `RELAX_ARTIFACT_HANDLERS`
3. **`calculation/step_done.py`**: Add SIESTA case in `is_step_done()`
4. **`drivers/__init__.py`**: Import `siesta` driver

### 9.4 No Behavioral Changes to Existing Engines

The SIESTA integration:
- Does NOT change QE, VASP, ORCA, PySCF, LAMMPS, CP2K behavior
- Does NOT modify calculation.yaml required fields
- Does NOT change manifest skip logic semantics
- Does NOT alter ULID generation or usage
- Does NOT introduce new SSOT locations

---

## Appendix A: File Locations Reference

| File | Purpose |
|------|---------|
| `src/qmatsuite/drivers/siesta/driver.py` | Driver protocol implementation |
| `src/qmatsuite/drivers/siesta/step_types.py` | StepTypeSpec definitions |
| `src/qmatsuite/drivers/siesta/handler.py` | Job execution handler |
| `src/qmatsuite/drivers/siesta/recipe.py` | JobGraph materialization |
| `src/qmatsuite/drivers/siesta/fdf_writer.py` | FDF input generation |
| `src/qmatsuite/drivers/siesta/parsers/` | Output parsing |
| `tests/integration/siesta/` | Integration tests |
| `tests/data/siesta/` | Test fixtures |

---

## Appendix B: FDF Parameter Mapping

| QMatSuite Parameter | FDF Parameter | Notes |
|--------------------|---------------|-------|
| `xc_functional: "PBE"` | `XC.authors PBE` | |
| `mesh_cutoff: {value: 200, unit: "Ry"}` | `MeshCutoff 200 Ry` | |
| `basis_size: "DZP"` | `PAO.BasisSize DZP` | SZ, DZ, DZP, TZP |
| `k_grid: [4, 4, 4]` | `%block kgrid_Monkhorst_Pack` | |
| `variable_cell: true` | `MD.VariableCell T` | For relax |
| `max_force_tol: {value: 0.04, unit: "eV/Ang"}` | `MD.MaxForceTol 0.04 eV/Ang` | |
| `ensemble: "nvt"` | `MD.TypeOfRun Nose` | MD thermostat |
| `temperature: 300` | `MD.TargetTemperature 300 K` | |

---

**Document Status:** Ready for Implementation
**Next Step:** Implement Phase 1 (SCF, relax) following this design
