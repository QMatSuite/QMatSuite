# CP2K Integration Fit Assessment

**Last reviewed**: 2025-01-19
**CP2K version target**: 2025.1
**QMatSuite modules consulted**:
- `src/qmatsuite/engine/registry.py` - Engine registration
- `src/qmatsuite/engine/vasp_engine.py` - VASP directory-state pattern
- `src/qmatsuite/engine/lammps_engine.py` - LAMMPS directory-state pattern
- `src/qmatsuite/engine/orca_engine.py` - ORCA strong-chain pattern
- `src/qmatsuite/workflow/registry.py` - Step type definitions
- `src/qmatsuite/execution/recipes.py` - Recipe patterns
- `src/qmatsuite/calculation/manifest.py` - Fingerprint/manifest system

---

## 1. Does CP2K Fit the QMatSuite Model?

**Short answer: Yes, CP2K fits well as a directory-state engine.**

### 1.1 Constitution Compliance Check

| Requirement | CP2K Behavior | Fit |
|-------------|---------------|-----|
| SSOT on disk is step.yaml | CP2K uses single .inp file → can be generated from step.yaml | ✅ |
| Engine invocation = Job = Run | One cp2k.ssmp invocation = one job | ✅ |
| YAML → input as clean rewrite | Generator creates .inp from scratch each run | ✅ |
| No engine logic in upper layers | All CP2K specifics in engine backend | ✅ |
| Isolated execution modes | CP2K runs in isolated directories | ✅ |

### 1.2 Comparison with Existing Engines

| Aspect | QE | VASP | LAMMPS | CP2K |
|--------|-----|------|--------|------|
| Input format | Multiple files (`.in`, POSCAR-like) | Multiple files (INCAR, POSCAR, KPOINTS, POTCAR) | Single script + data file | Single `.inp` file |
| Output naming | Controlled by `prefix` | Fixed names (OUTCAR, etc.) | Configurable | Controlled by `PROJECT` |
| Restart mechanism | `outdir` + charge density | WAVECAR, CHGCAR | restart.bin | .restart + .wfn files |
| Data dependencies | pseudo_dir | POTCAR | potential files | BASIS_SET_FILE, POTENTIAL_FILE |
| Parallelism model | MPI | MPI | MPI/OpenMP | MPI/OpenMP |

**Conclusion**: CP2K is most similar to **LAMMPS** in terms of:
- Single input file generation
- CWD-relative output
- Template-based input construction

---

## 2. Recipe Pattern Selection

### 2.1 Available Patterns

From `src/qmatsuite/execution/recipes.py`:

1. **QERecipe** (Directory-state, step-run model)
   - One job per step
   - Jobs share working directory and scratch
   - Used by: QE, Wannier90, (future) VASP, ABINIT

2. **ORCARecipe** (Strong-chain model)
   - One job per subchain (multiple steps fused)
   - Steps share single input file
   - Used by: ORCA

3. **PySCFRecipe** (Weak-chain/session model)
   - Python-native in-memory state passing
   - Used by: PySCF

### 2.2 Recommended Pattern for CP2K: **QERecipe**

**Justification**:

1. **One-to-one job mapping**: Each CP2K `.inp` file = one job. No multi-step fusion.

2. **Directory-state**: CP2K writes outputs to CWD with PROJECT prefix. Each step gets its own directory.

3. **Explicit restart references**: Unlike ORCA (where chains share wavefunction internally), CP2K restarts reference files by path (`WFN_RESTART_FILE_NAME`, `RESTART_FILE_NAME`).

4. **No in-memory state**: CP2K is an external binary, not a Python library.

**Pattern comparison with LAMMPS**:
```
LAMMPS:
  materialize_inputs() → in.lammps, structure.data, potentials/
  run_step() → subprocess.run([lmp, "-in", "in.lammps", ...])

CP2K (proposed):
  materialize_inputs() → input.inp
  run_step() → subprocess.run([cp2k.ssmp, "-i", "input.inp", "-o", "output.log"])
```

---

## 3. Minimal Integration Surface

### 3.1 Required New Components

| Component | Location | Description |
|-----------|----------|-------------|
| `Cp2kEngine` | `src/qmatsuite/engine/cp2k_engine.py` | Engine backend class |
| `cp2k_writer.py` | `src/qmatsuite/engine/cp2k_writer.py` | Input file generator |
| `cp2k_parser.py` | `src/qmatsuite/engine/cp2k_parser.py` | Output parser |
| `cp2k_resolver.py` | `src/qmatsuite/core/engines/cp2k_resolver.py` | Binary discovery |
| Step type entries | `src/qmatsuite/workflow/registry.py` | Registry additions |

### 3.2 Core Changes Required?

**Answer: Minimal to none.**

The existing architecture supports CP2K without core changes:

| Area | Core Change Needed? | Reason |
|------|---------------------|--------|
| Engine registry | No | Just add `Cp2kEngine` to `create_default_registry()` |
| Step type registry | No | Add entries to `_STEP_TYPES` dict |
| Recipe system | No | Use existing `QERecipe` |
| Manifest system | No | Same fingerprint strategy works |
| History system | No | Same event recording |
| Calculation runner | No | Dispatches to engine.run_step() |

### 3.3 Optional Enhancements (Not Required for v0)

1. **Basis/potential management**: Similar to QE pseudo_dir but simpler (just reference by name)
2. **Preset system**: CP2K-specific presets (precision, functional)
3. **Structure artifact extraction**: Parse final geometry from relaxation

---

## 4. Job Boundary Definition

### 4.1 What Constitutes One Job/Run?

**One CP2K job = One `.inp` file invocation = One `cp2k.ssmp` process**

```
Job boundary:
  INPUT:  step.yaml → materialize → input.inp
  EXEC:   cp2k.ssmp -i input.inp -o output.log
  OUTPUT: output.log, *.wfn, *.restart, *.xyz, etc.
```

### 4.2 Job ID and Run ID

Following QMatSuite convention:
- `job_id` = ULID generated at run start
- `run_id` = same as `job_id`
- Recorded in history events

### 4.3 Working Directory

```
calculations/<calc_id>/raw/<step_ulid>/
```

Each step runs in its own directory (consistent with QE, VASP, LAMMPS patterns).

---

## 5. File Management Strategy

### 5.1 Managed PROJECT Name

**Requirement**: Predictable output filenames for parsing and restart references.

**Strategy**: Use fixed PROJECT name per step.

```python
# In cp2k_writer.py
PROJECT_NAME = "cp2k_calc"  # Fixed, predictable

# Resulting files:
# cp2k_calc-RESTART.wfn
# cp2k_calc-pos-1.xyz
# cp2k_calc.restart
```

**Alternative considered**: Use step ULID as PROJECT name.
- Pro: Unique across all steps
- Con: Long names, harder to debug manually
- Decision: Fixed name is simpler; directory isolation provides uniqueness.

### 5.2 Runtime-Managed Keys

Like QE's `prefix` and `outdir`, CP2K needs runtime injection of:

| Key | Location | Purpose |
|-----|----------|---------|
| `PROJECT` | `&GLOBAL` | Output file prefix (managed) |
| `RESTART_FILE_NAME` | `&EXT_RESTART` | Restart path (if restart_from) |
| `WFN_RESTART_FILE_NAME` | `&DFT/SCF` | Wavefunction path (if restart) |

**Implementation**:
```python
def materialize_inputs(self, step, working_dir, calculation):
    # Build input sections from step.parameters
    sections = self._build_sections(step)

    # Inject managed keys
    sections["GLOBAL"]["PROJECT"] = "cp2k_calc"

    # Handle restart_from reference
    if "restart_from" in step.parameters:
        restart_path = self._resolve_restart_artifact(step, calculation)
        sections["EXT_RESTART"] = {
            "RESTART_FILE_NAME": str(restart_path)
        }

    # Generate input file
    input_content = self._render_input(sections)
    (working_dir / "input.inp").write_text(input_content)
```

---

## 6. Incremental/Skip Semantics

### 6.1 What Should Be Hashed?

For fingerprint calculation (manifest `step_sha`):

**Include**:
- Step type
- All CP2K parameters from step.yaml
- Structure reference (structure_sha)
- Restart reference (if any)

**Exclude** (derived/runtime):
- PROJECT name (always "cp2k_calc")
- Absolute paths (use relative references)
- Timing parameters (don't affect results)

### 6.2 Skip Logic

A step can be skipped if:
1. Manifest entry exists with `done: true`
2. `step_sha` matches current step.yaml hash
3. `structure_sha` matches current structure hash
4. Required artifacts exist (for downstream steps)

### 6.3 Output Artifacts for Skip Decision

| Step Type | Key Output | Existence Check |
|-----------|------------|-----------------|
| cp2k_scf | `cp2k_calc-RESTART.wfn` | Required for skip |
| cp2k_relax | `cp2k_calc-pos-1.xyz` | Required (final structure) |
| cp2k_md | `cp2k_calc-1.restart` | Required (for continuation) |

---

## 7. Scan Expansion

### 7.1 What Can Be Scanned?

Following QMatSuite scan patterns:

```yaml
# step.yaml
step_type: cp2k_scf
parameters:
  cutoff: "@scan:cutoff_scan"

parameter_scan:
  cutoff_scan:
    values: [200, 300, 400, 500]
```

### 7.2 Scan Semantics

**Each scan value = separate job in separate directory.**

```
calculations/<calc_id>/raw/
├── <step_ulid>_scan_0/     # cutoff=200
│   └── input.inp
├── <step_ulid>_scan_1/     # cutoff=300
│   └── input.inp
├── <step_ulid>_scan_2/     # cutoff=400
│   └── input.inp
└── <step_ulid>_scan_3/     # cutoff=500
    └── input.inp
```

### 7.3 Scannable CP2K Parameters

| Parameter | CP2K Location | Typical Scan |
|-----------|---------------|--------------|
| `cutoff` | `&MGRID/CUTOFF` | 200, 300, 400, 500 Ry |
| `rel_cutoff` | `&MGRID/REL_CUTOFF` | 40, 50, 60 Ry |
| `eps_scf` | `&SCF/EPS_SCF` | 1E-5, 1E-6, 1E-7 |
| `basis_set` | `&KIND/BASIS_SET` | SZV, DZVP, TZVP |

### 7.4 Fingerprint and Scans

Per constitution: "Fingerprints hash resolved effective params (scan resolved) and ignore `parameter_scan` section."

This means each scan variant gets its own fingerprint based on the actual parameter value used.

---

## 8. Summary: Integration Fit Assessment

### 8.1 Fit Score

| Criterion | Score | Notes |
|-----------|-------|-------|
| Constitution compliance | 10/10 | Full compliance |
| Recipe fit | 9/10 | QERecipe works well |
| Directory isolation | 10/10 | Clean CWD-based model |
| Restart handling | 8/10 | Requires path management |
| Data file handling | 7/10 | CP2K_DATA_DIR dependency |
| Overall | **9/10** | Excellent fit |

### 8.2 Risk Assessment

| Risk | Likelihood | Mitigation |
|------|------------|------------|
| Binary not found | Medium | Robust resolver with fallbacks |
| Data files missing | Medium | Validate CP2K_DATA_DIR at probe time |
| Output parsing failures | Low | Start with minimal parsing |
| Restart path issues | Medium | Careful relative path handling |

### 8.3 Recommended Implementation Order

1. **Phase 1**: `cp2k_scf` only (single-point)
   - Engine skeleton
   - Input generator
   - Basic output parsing

2. **Phase 2**: `cp2k_relax` (geometry optimization)
   - Structure artifact extraction
   - Restart handling

3. **Phase 3**: `cp2k_md` (molecular dynamics)
   - Trajectory handling
   - Multi-restart support

4. **Phase 4**: Advanced features
   - CELL_OPT
   - Properties (DOS, bands)
   - Preset system
