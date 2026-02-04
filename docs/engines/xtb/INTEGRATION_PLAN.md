# xTB Engine Integration Plan

## Engine Identity

| Property | Value |
|----------|-------|
| `engine_family` | `"xtb"` |
| `display_name` | `"xTB"` |
| `PREFIX` | `"xtb"` |
| `driver_api_version` | `"1.0.0"` |
| Executable | `xtb` |
| Recipe Archetype | **Directory-state** (simplest variant) |
| WorkdirPolicy | `ISOLATED` |

## Engine Classification

xTB is a **semi-empirical quantum mechanical method**. Unlike DFT engines (QE, VASP) or wavefunction-based QC engines (ORCA, PySCF), xTB:
- Has no external basis sets or pseudopotentials
- Does not produce production-quality electronic structure
- Is extremely fast (seconds to minutes, not hours)
- Uses OpenMP threading only (no MPI)
- Operates as a single binary with CLI flags

**Primary integration value**: Fast structure optimizer (geometry relaxation) for pre-screening before expensive DFT calculations.

## GEN Steps Mapping

The `relax` GEN step already exists in `GenStepRegistry`. **No changes to gen_steps.py needed.**

| GEN Step | SPEC Step | xTB Capability | Notes |
|----------|-----------|----------------|-------|
| `relax` | `xtb_relax` | Geometry optimization | Primary use case. `xtb input.xyz --opt --gfn 2` |
| `scf` | `xtb_scf` | Single-point energy | Optional. `xtb input.xyz --gfn 2` |

### Initial Scope: `relax` Only

For the initial integration, we support **only `relax`**. Rationale:
1. xTB's primary value in a multi-engine workflow is geometry optimization
2. xTB single-point energies are not accurate enough for production use
3. xTB does not chain steps (no SCF -> bands -> DOS workflow)
4. Keeping scope minimal validates the plugin architecture cleanly

Future expansion (not in scope):
- `xtb_scf`: Single-point energy
- `xtb_md`: Molecular dynamics (requires xcontrol file)
- `xtb_hess`: Vibrational frequencies

### xTB RELAX = Pure Structure Transformer

This is the conceptual contract for xTB relax:
- **Input**: Atomic structure (XYZ format)
- **Output**: Relaxed atomic structure (XYZ format, in `xtbopt.xyz`)
- **No electronic state** is produced, reused, or chained
- **No SCF/wavefunction chaining**
- **No dependency** on MPI, HDF5, NetCDF, FFTW, or external libraries
- Obeys the existing RELAX constitution:
  - RELAX outputs a generated structure artifact
  - The structure is NOT a project structure resource unless explicitly promoted
  - Downstream steps must NOT treat RELAX as an electronic predecessor

## Files to Create

```
src/quantumvitas/drivers/xtb/
  __init__.py          # Register XTBDriver with DriverRegistry
  driver.py            # XTBDriver class (7-item MUST interface)
  handler.py           # xtb_step_handler function
  recipe.py            # XTBRecipe (Directory-state archetype, ISOLATED workdir)
  writer.py            # XYZ input writer (adapted from exploration utility)
  parser.py            # Output parser (adapted from exploration utility)
```

## Files to Modify

### Mandatory (allowed by constitution)

1. **`src/quantumvitas/drivers/__init__.py`** — Add import line:
   ```python
   from quantumvitas.drivers import xtb
   ```

### Requires Explicit Approval

2. **`src/quantumvitas/execution/relax_artifacts.py`** — Add xTB relax artifact handler:
   ```python
   RELAX_ARTIFACT_HANDLERS["xtb_xyz"] = _handle_xtb_xyz
   ```

   **Reason**: The capability-based relax artifact registry (`RELAX_ARTIFACT_HANDLERS`) already contains engine-specific handlers for QE, PySCF, ORCA, LAMMPS, and CP2K. Adding xTB follows the same established pattern. The handler parses `xtbopt.xyz` and converts to pymatgen Molecule for `current.json`. This is NOT a kernel routing change — it's extending the artifact handler registry, which is the designed extension point.

   **Handler implementation** (simple, since xTB writes standard XYZ):
   ```python
   def _handle_xtb_xyz(spec, calc_dir, run_context):
       from pymatgen.core import Molecule
       from quantumvitas.core.public import canonicalize_structure_like_in_place
       # Read xtbopt.xyz (standard XYZ format)
       mol = Molecule.from_file(str(spec.artifact_path))
       canonicalize_structure_like_in_place(mol)
       return write_generated_structure(
           structure=mol, calc_dir=calc_dir,
           step_ulid=spec.step_ulid,
           step_type_spec=spec.step_type_spec,
           run_ulid=run_context.get("run_ulid"),
           ...
       )
   ```

### NOT Modified (guaranteed)

The following files are NOT touched:
- `runner.py`, `executor.py`, `handlers.py`
- `driver_registry.py`, `driver_protocol.py`
- `gen_steps.py` (all needed GEN steps already exist)
- Any kernel routing/dispatch code

## Driver Implementation Details

### `driver.py` — XTBDriver

```python
class XTBDriver(BaseEngineDriver):
    PREFIX = "xtb"
    SUPPORTED_GEN_STEPS = frozenset({"relax"})

    # Properties
    engine_family -> "xtb"
    display_name -> "xTB"
    driver_api_version -> "1.0.0"

    # Methods
    get_step_type_specs() -> [
        StepTypeSpec(
            step_type_spec="xtb_relax",
            engine="xtb",
            executable="xtb",
            description="xTB geometry optimization (GFN2-xTB)",
            category="calculation",
            supports_restart=False,
            mpi_aware=False,
        ),
    ]
    get_handler() -> xtb_step_handler
    get_recipe_class() -> XTBRecipe
    get_workdir_policy() -> WorkdirPolicy.ISOLATED
```

### `recipe.py` — XTBRecipe (Simplest Possible)

**Archetype**: Directory-state with ISOLATED workdir.

**Key behaviors**:
1. One job per step (only relax initially)
2. Working dir: `calc/raw/{step_ulid}/`
3. No pseudopotential staging (xTB has built-in parameters)
4. No restart staging (xTB calculations are fast, no need to restart)
5. No shared state between steps
6. Command: `["xtb", "input.xyz", "--opt", "--gfn", "2"]`

```python
class XTBRecipe(BaseRecipe):
    def materialize(self, steps, calc_raw_dir, step_shas=None):
        jobs = []
        for step in steps:
            step_ulid = step.meta.ulid
            working_dir = calc_raw_dir / step_ulid

            # Build command from step parameters
            params = dict(step.params) if hasattr(step, "params") and step.params else {}
            cmd = build_xtb_command(
                runtype="opt",
                gfn_level=params.get("gfn_level", 2),
                opt_level=params.get("opt_level"),
                charge=params.get("charge", 0),
                uhf=params.get("uhf", 0),
            )

            job = Job(
                id=step_ulid,
                step_ulids=[step_ulid],
                working_dir=working_dir,
                command=cmd,
                input_files=[working_dir / "input.xyz"],
                expected_outputs=[working_dir / "xtbopt.xyz"],
                deps=[],
                fingerprint=self._get_step_sha(step, step_shas),
                metadata={
                    "engine": "xtb",
                    "step_type_spec": "xtb_relax",
                    "step_type_gen": "relax",
                },
            )
            jobs.append(job)
        return JobGraph(jobs=jobs)
```

### `handler.py` — xtb_step_handler

**Execution flow**:
1. Receive `Job` with step data
2. Create working directory
3. Write `input.xyz` from structure data
4. Execute `xtb input.xyz --opt --gfn 2` via subprocess
5. Check exit code (non-zero = hard error)
6. Check `xtbopt.xyz` exists (missing = hard error)
7. Check `.xtboptok` marker (missing = convergence warning)
8. Parse `xtbopt.xyz` for relaxed structure
9. Create `RelaxArtifactSpec(artifact_type="xtb_xyz", artifact_path=xtbopt_path)`
10. Return `JobResult` with step results

```python
def xtb_step_handler(job, calculation, engine_registry, context):
    from .writer import write_xyz_from_pymatgen
    from .parser import parse_xtbopt_xyz

    step_ulid = job.step_ulids[0]
    step = _find_step_by_ulid(calculation, step_ulid)
    working_dir = job.working_dir
    working_dir.mkdir(parents=True, exist_ok=True)

    # Write input structure
    write_xyz_from_pymatgen(calculation.structure, working_dir / "input.xyz")

    # Execute xTB
    result = subprocess.run(
        job.command, cwd=str(working_dir),
        capture_output=True, text=True, timeout=context.get("timeout", 3600),
    )

    # Save stdout
    (working_dir / "xtb.out").write_text(result.stdout + result.stderr)

    # Check results
    xtbopt_path = working_dir / "xtbopt.xyz"
    if result.returncode != 0:
        return JobResult(job_id=job.id, success=False,
                         error=f"xTB exited with code {result.returncode}")
    if not xtbopt_path.exists():
        return JobResult(job_id=job.id, success=False,
                         error="xtbopt.xyz not found after optimization")

    # Parse results
    parsed = parse_xtbopt_xyz(xtbopt_path)

    # Return with relax artifact
    step_results = {
        step_ulid: {
            "success": True,
            "total_energy_Eh": parsed.get("energy_Eh"),
            "gradient_norm": parsed.get("gnorm"),
            "relax_artifact_spec": RelaxArtifactSpec(
                artifact_type="xtb_xyz",
                artifact_path=xtbopt_path,
                step_ulid=step_ulid,
                step_type_spec="xtb_relax",
            ).to_dict(),
        }
    }
    return JobResult(job_id=job.id, success=True, step_results=step_results)
```

### `writer.py` — Input Writer

Adapted from `docs/engines/xtb/scripts/xtb_input_writer.py`:
- `write_xyz_file()`: Write standard XYZ from symbols + positions
- `write_xyz_from_pymatgen()`: Write XYZ from pymatgen Structure/Molecule
- `build_xtb_command()`: Build CLI arguments from parameters

### `parser.py` — Output Parser

Adapted from `docs/engines/xtb/scripts/xtb_parser.py`:
- `parse_xtbopt_xyz()`: Parse optimized geometry from xtbopt.xyz
- `parse_xtb_stdout()`: Parse stdout for energy, convergence, etc.
- `parse_charges()`: Parse Mulliken charges
- `check_success()`: Check success markers (.xtboptok)

## Test Plan

### Unit Tests (`tests/drivers/xtb/`)

1. **`test_xtb_driver.py`** — Driver protocol compliance:
   - All step types resolve via DriverRegistry
   - Handler is retrievable
   - Materialization map is correct ({"relax": "xtb_relax"})
   - PREFIX and SUPPORTED_GEN_STEPS are consistent

2. **`test_xtb_parser.py`** — Parser against golden artifacts:
   - Parse water optimization output (xtb.out)
   - Parse optimized geometry (xtbopt.xyz)
   - Parse charges file
   - Validate energy, convergence, structure extraction
   - Golden artifacts: `docs/engines/xtb/artifacts/`

3. **`test_xtb_writer.py`** — Input file generation:
   - XYZ file writing from symbols + positions
   - Command-line argument construction
   - xcontrol file generation

4. **`test_xtb_recipe.py`** — Recipe materialization:
   - Single relax step -> 1-job JobGraph
   - Correct working directory layout
   - Correct command line

### Integration Tests

5. **`tests/integration/test_xtb_relax.py`** — Real end-to-end test:
   - Create a minimal project
   - Create a calculation with one initial structure (H2O)
   - Add a single step: `step_type_gen = "relax"`, engine = "xtb"
   - Run the calculation
   - Assert:
     - Step succeeds
     - `xtbopt.xyz` was produced
     - Generated structure exists for the step
   - Promote the relaxed structure
   - Assert:
     - A new structure resource is created
     - Atomic positions differ from the original
     - Original structure remains unchanged
   - Skipped in CI if xtb not available

## Parameters (Step Parameters)

xTB relax steps accept these parameters in `step.yaml`:

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `gfn_level` | int | 2 | GFN parametrization (0, 1, 2, or -1 for GFN-FF) |
| `opt_level` | str | `"normal"` | Convergence: crude/sloppy/loose/normal/tight/verytight/extreme |
| `charge` | int | 0 | Molecular charge |
| `uhf` | int | 0 | Number of unpaired electrons |
| `solvent` | str | null | Implicit solvation solvent name |
| `solvent_model` | str | `"alpb"` | Solvation model: "alpb" or "gbsa" |
| `max_iterations` | int | 250 | Max SCF iterations |
| `accuracy` | float | 1.0 | SCC accuracy (lower = better) |

## Why xTB Is a Good Stress Test

xTB tests the runner abstraction because it is unlike any existing engine:
- **Non-DFT**: Semi-empirical, not ab-initio
- **Non-MPI**: Single binary, OpenMP only
- **Structure-only**: No electronic state output to chain
- **Minimal I/O**: Just XYZ in, XYZ out
- **No pseudopotentials**: No external files to stage
- **No restart**: Fast enough to recompute
- **No complex workflows**: Single-step relax only

If xTB integrates cleanly as a driver plugin without modifying any kernel routing code, the runner design is sound.

## Risks & Mitigations

| Risk | Mitigation |
|------|------------|
| Need to add handler to relax_artifacts.py | Follows established pattern (5 engines already have handlers there). Small, self-contained change. |
| xTB not available on CI runners | Skip integration tests via `pytest.mark.skipif(not shutil.which("xtb"))` |
| Exit code inconsistency (1 vs 128) | Check for non-zero exit code, not specific value |
| Large MD trajectory files | Not in scope (initial integration is relax-only) |
| Periodic systems | xTB supports periodic via lattice in XYZ, but initial scope is molecular only |

## Implementation Order

1. Create `src/quantumvitas/drivers/xtb/` directory structure
2. Implement `writer.py` (adapted from exploration utility)
3. Implement `parser.py` (adapted from exploration utility)
4. Implement `driver.py` (XTBDriver class)
5. Implement `recipe.py` (XTBRecipe)
6. Implement `handler.py` (xtb_step_handler)
7. Implement `__init__.py` (registration)
8. Add import to `src/quantumvitas/drivers/__init__.py`
9. Add `_handle_xtb_xyz` to `relax_artifacts.py`
10. Add tests (unit + integration)
11. Run full test suite to verify no regressions
