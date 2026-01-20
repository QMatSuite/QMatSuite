# CP2K Integration Specification

**Version**: v4.0 (Alignment-Compliant - Updated)
**Last Updated**: 2026-01-20
**CP2K Version**: 2025.1

---

## 1. Executive Summary

This specification defines how CP2K integrates with QMatSuite, aligned with the v4 alignment decisions. CP2K is a **directory-state engine** using isolated workdirs per step, following the LAMMPS pattern (NOT reusing any existing recipe).

### Key Alignment Decisions (v4 Update)

| Decision | Implementation |
|----------|----------------|
| **Runtime SSOT** | `raw/<step_ulid>/` - ALWAYS the source of truth |
| **Scan archive** | `raw/scan/<variant_key>/` - POST-RUN ARCHIVE ONLY, never referenced by runtime |
| Workdir cleanup | **DEFAULT OFF** - Do NOT clean directories before runs |
| PROJECT naming | Fixed `PROJECT = "cp2k_calc"` (runtime-managed) |
| Restart semantics | No `restart_from` in step.yaml; runtime resolves predecessor linearly |
| **Latest artifact selection** | **mtime-based** (NOT numeric suffix) |
| Trajectory output | XYZ format; parser finds latest `*-pos-*.xyz` |
| **Cell information** | Separate `.cell` file required for MD trajectories |
| Skip/incremental | Reuse existing semantics; **MD steps disabled** |
| Data/basis policy | **No staging** - users rely on CP2K_DATA_DIR or explicit paths |
| **Preflight checks** | General feature with engine-declared requirements |

---

## 2. Runtime SSOT vs Scan Archive (CRITICAL)

### 2.1 Core Principle

**The scan archive (`raw/scan/`) is NEVER the runtime source of truth.**

| Concept | Location | Purpose | Referenced at Runtime? |
|---------|----------|---------|------------------------|
| **Runtime SSOT** | `calc/raw/<step_ulid>/` | Active execution artifacts | **YES** |
| **Scan Archive** | `calc/raw/scan/<variant_key>/` | Post-run copy for analysis/UI | **NEVER** |

### 2.2 Why This Matters

- Dependency resolution (wfn/restart lookup) MUST read from `raw/<step_ulid>/`
- Scan archive is a snapshot created AFTER variant execution completes
- Runtime code paths have no knowledge of "which variant" - they see only step ULIDs

### 2.3 Archive Structure

For per-step-directory engines (VASP, LAMMPS, CP2K), the archive **preserves relative paths**:

```
calc/raw/
├── <step_ulid_1>/           # Runtime SSOT for step 1
│   ├── input.inp
│   ├── output.log
│   └── cp2k_calc-RESTART.wfn
├── <step_ulid_2>/           # Runtime SSOT for step 2
│   └── ...
└── scan/
    └── <variant_key>/       # Archive copy (post-run)
        ├── <step_ulid_1>/   # Copied from raw/<step_ulid_1>/
        │   ├── input.inp
        │   ├── output.log
        │   └── cp2k_calc-RESTART.wfn
        └── <step_ulid_2>/   # Copied from raw/<step_ulid_2>/
            └── ...
```

**CP2K MUST follow this exact pattern.** The archive ends up as `raw/scan/<variant_key>/<step_ulid>/*`.

---

## 3. Directory Layout

### 3.1 Step Working Directory

Each CP2K step executes in its own isolated directory:

```
calculation/
├── calculation.yaml
├── steps/
│   ├── <step_ulid_1>.step.yaml    # e.g., 01HY2Q9W8A1234ABCDEF.step.yaml
│   └── <step_ulid_2>.step.yaml
├── raw/
│   ├── <step_ulid_1>/              # Working directory for step 1 (RUNTIME SSOT)
│   │   ├── input.inp               # CP2K input file
│   │   ├── output.log              # CP2K stdout
│   │   ├── cp2k_calc-RESTART.wfn   # Wavefunction restart
│   │   ├── cp2k_calc-1.restart     # Full restart
│   │   ├── cp2k_calc-pos-1.xyz     # Trajectory
│   │   ├── cp2k_calc-1.ener        # Energy log
│   │   └── cp2k_calc-1.cell        # Cell evolution (NPT)
│   └── <step_ulid_2>/              # Working directory for step 2 (RUNTIME SSOT)
│       └── ...
└── .run_tmp_info/
    └── manifest.json
```

### 3.2 Scan Variant Layout

Scan variants use the **existing** scan machinery. The archive copies are created AFTER execution by `ArchiveToSlotAction`:

```
calculation/
├── raw/
│   ├── <step_ulid>/                # Runtime SSOT (active)
│   │   └── ...
│   └── scan/
│       ├── scan_a1b2c3d4e5f6g7h8/  # Variant 0 archive (POST-RUN COPY)
│       │   ├── <step_ulid>/        # Preserves step structure
│       │   │   ├── input.inp
│       │   │   ├── output.log
│       │   │   └── cp2k_calc-*
│       │   └── ...
│       └── slots.json              # Audit log
```

**Important**: CP2K MUST use the **existing** variant_id generation algorithm. DO NOT create a new algorithm.

### 3.3 Workdir Cleanup Policy

**CRITICAL: CP2K does NOT clean workdirs before runs.**

| Engine | Cleanup Behavior | Rationale |
|--------|------------------|-----------|
| VASP | **Yes** - `shutil.rmtree()` before each run | VASP expects clean workdir |
| LAMMPS | **No** - creates if not exist, accumulates | No cleanup needed |
| QE | **No** - uses `outdir/` for state | Shared scratch model |
| **CP2K** | **No** - accumulates artifacts | Latest selection handles old files |

This is documented in the handler and must be enforced in `cp2k_step_handler()`:
```python
# CORRECT for CP2K:
working_dir.mkdir(parents=True, exist_ok=True)
# DO NOT add shutil.rmtree() here
```

---

## 4. Managed Keys and PROJECT Naming

### 4.1 Runtime-Managed Keys

The following CP2K input keys are **runtime-managed** (injected by the engine, never from step.yaml):

| Key | Location | Value | Rationale |
|-----|----------|-------|-----------|
| `PROJECT` | `&GLOBAL` | `"cp2k_calc"` (fixed) | Predictable output naming |
| `RUN_TYPE` | `&GLOBAL` | Derived from step_type | Controls CP2K behavior |

### 4.2 Fixed PROJECT Name

**Decision**: Use a **fixed** PROJECT name for all steps:
```
PROJECT = "cp2k_calc"
```

This means all output files follow predictable patterns:
- `cp2k_calc-RESTART.wfn`
- `cp2k_calc-pos-1.xyz`
- `cp2k_calc-1.restart`
- `cp2k_calc-1.ener`
- `cp2k_calc-1.cell`

**Rationale**: Directory isolation provides uniqueness. Fixed naming enables deterministic artifact selection.

---

## 5. Restart Semantics

### 5.1 No `restart_from` in step.yaml

**CRITICAL**: CP2K integration does NOT persist `restart_from` in step.yaml.

| What | Where | How |
|------|-------|-----|
| Restart policy | step.yaml `parameters` section | User-specified B-class parameter |
| Predecessor resolution | Runtime | Linearly from topological predecessor |
| Artifact paths | Runtime | Resolved relative paths to predecessor workdir |

### 5.2 Restart Policy in step.yaml

Users MAY specify restart behavior via parameters (B-class freedom):
```yaml
# step.yaml
parameters:
  restart_policy:
    use_restart: true       # Use .restart file from predecessor
    use_wfn_guess: true     # Use .wfn file for SCF_GUESS
```

### 5.3 Runtime Resolution (From Runtime SSOT)

The `cp2k_step_handler()` resolves predecessor artifacts at runtime:
1. Find topological predecessor step in the job's step chain
2. Check for artifacts in predecessor's workdir (`raw/<predecessor_ulid>/`)
3. **NEVER reference `raw/scan/`** - always use runtime SSOT
4. Generate appropriate `&EXT_RESTART` section or `WFN_RESTART_FILE_NAME`

```python
# Pseudocode for handler
def _resolve_restart_artifacts(step_ulid, calculation):
    # Find predecessor step
    predecessor_ulid = get_linear_predecessor(step_ulid, calculation.steps)
    if predecessor_ulid is None:
        return None

    # Read from RUNTIME SSOT (NOT scan archive)
    predecessor_dir = calculation.io.raw_dir / predecessor_ulid  # raw/<predecessor_ulid>/

    # Find latest artifacts using mtime-based selection
    restart_file = find_latest_by_mtime(predecessor_dir, "cp2k_calc-*.restart")
    wfn_file = predecessor_dir / "cp2k_calc-RESTART.wfn"

    return {"restart_file": restart_file, "wfn_file": wfn_file if wfn_file.exists() else None}
```

---

## 6. Latest Artifact Selection (mtime-based)

### 6.1 Selection Policy (UPDATED)

**CRITICAL**: Latest artifact selection uses **file modification time (mtime)**.

**Rationale**:
- More robust short-term implementation
- Doesn't rely on CP2K naming conventions
- Works uniformly across artifact types

### 6.2 General Implementation

```python
def find_latest_by_mtime(workdir: Path, pattern: str) -> Optional[Path]:
    """
    Find latest file matching pattern by modification time.

    Args:
        workdir: Directory to search
        pattern: Glob pattern (e.g., "cp2k_calc-*.restart", "*.wfn")

    Returns:
        Path to file with most recent mtime, or None if no matches.
    """
    candidates = list(workdir.glob(pattern))
    if not candidates:
        return None

    # Select by mtime (most recent)
    return max(candidates, key=lambda p: p.stat().st_mtime)
```

### 6.3 Artifact Patterns

| Artifact Type | Pattern | Selection |
|---------------|---------|-----------|
| Restart | `cp2k_calc-*.restart` | mtime (max) |
| Wavefunction | `cp2k_calc-RESTART.wfn` | Direct (single file) |
| Trajectory | `cp2k_calc-pos-*.xyz` | mtime (max) |
| Energy | `cp2k_calc-*.ener` | mtime (max) |
| Cell | `cp2k_calc-*.cell` | mtime (max) |

### 6.4 Wavefunction Files (Special Case)

Pattern: `cp2k_calc-RESTART.wfn` (no numeric suffix)

**Selection rule**:
1. If user specifies `WFN_RESTART_FILE_NAME` in parameters, use that (explicit override)
2. Otherwise, use `cp2k_calc-RESTART.wfn` (the canonical latest)

**Note**: CP2K automatically manages backup files (`*.wfn.bak-1`, `*.wfn.bak-2`, etc.). Always use the non-backup file.

### 6.5 Old Artifacts Policy

**Old artifacts are NOT deleted.** They remain in the directory. This is intentional:
- Provides audit trail
- Prevents accidental data loss
- Simplifies recovery from partial failures

---

## 7. Preflight Checks (General Feature)

### 7.1 Overview

Preflight checks verify required artifacts exist BEFORE launching an engine. This is a **general feature** reusable across engines.

### 7.2 Engine Declaration

Each engine recipe/handler declares its preflight requirements:

```python
class CP2KRecipe(BaseRecipe):
    def get_preflight_requirements(self, step) -> List[PreflightRequirement]:
        reqs = []
        params = step.parameters
        restart_policy = params.get("restart_policy", {})

        if restart_policy.get("use_restart"):
            reqs.append(PreflightRequirement(
                artifact_type="restart",
                pattern="cp2k_calc-*.restart",
                source_step="predecessor",
                required=True,
                message="Restart file required but not found in {source_dir}",
            ))

        if restart_policy.get("use_wfn_guess"):
            reqs.append(PreflightRequirement(
                artifact_type="wfn",
                pattern="cp2k_calc-RESTART.wfn",
                source_step="predecessor",
                required=True,
                message="WFN file required but not found in {source_dir}",
            ))

        return reqs
```

### 7.3 Checker Implementation

```python
@dataclass
class PreflightRequirement:
    """Declaration of required artifact for preflight check."""
    artifact_type: str  # e.g., "restart", "wfn", "chgcar"
    pattern: str        # Glob pattern
    source_step: str    # "predecessor" or specific step_ulid
    required: bool      # Hard error if missing?
    message: str        # Error message template

class PreflightChecker:
    """General preflight checker for missing artifacts."""

    def check(
        self,
        requirements: List[PreflightRequirement],
        calculation: "Calculation",
        current_step: "Step",
    ) -> List[PreflightError]:
        errors = []
        for req in requirements:
            source_dir = self._resolve_source_dir(req, calculation, current_step)
            matches = list(source_dir.glob(req.pattern))
            if not matches and req.required:
                errors.append(PreflightError(
                    requirement=req,
                    message=req.message.format(
                        pattern=req.pattern,
                        source_dir=source_dir,
                    )
                ))
        return errors

    def _resolve_source_dir(self, req, calculation, current_step) -> Path:
        if req.source_step == "predecessor":
            predecessor = get_linear_predecessor(current_step, calculation.steps)
            return calculation.io.raw_dir / predecessor.meta.id
        else:
            return calculation.io.raw_dir / req.source_step
```

---

## 8. Trajectory Output and Parsing

### 8.1 XYZ Format Enforcement

CP2K trajectory output is forced to XYZ format with **default filename**:

```
&MOTION
  &PRINT
    &TRAJECTORY
      FORMAT XYZ
      ! DO NOT set FILENAME - use default PROJECT-pos-N.xyz
    &END TRAJECTORY
  &END PRINT
&END MOTION
```

### 8.2 Cell Information (CRITICAL)

**Problem**: CP2K XYZ (XMOL) format does NOT contain cell information.

**Solution**: Enable cell output for MD simulations:

```
&MOTION
  &PRINT
    &CELL
      &EACH
        MD 1    ! Print every step
      &END EACH
    &END CELL
  &END PRINT
&END MOTION
```

This produces `cp2k_calc-N.cell` with cell vectors at each timestep.

### 8.3 Cell File Format

```
#  Step   Time [fs]       Ax [Angstrom]   Ay [Angstrom]  ...
     1       0.5000        10.000000       0.000000      0.000000  ...
     2       1.0000        10.001234       0.000000      0.000000  ...
```

### 8.4 Trajectory Parsing Strategy

1. Find latest trajectory: `find_latest_by_mtime(workdir, "cp2k_calc-pos-*.xyz")`
2. Find matching cell file: `find_latest_by_mtime(workdir, "cp2k_calc-*.cell")`
3. Parse XYZ for positions (CP2K-specific comment format)
4. Merge cell data from `.cell` file if available
5. If no `.cell` file, use cell from initial structure (static cell approximation)

### 8.5 CP2K XYZ Format

CP2K trajectory XYZ format (per frame):
```
N
 i =        5, E =      -17.12345678
Si        0.000000000     0.000000000     0.000000000
Si        1.357000000     1.357000000     1.357000000
...
```

The comment line contains iteration number `i` and energy `E`.

---

## 9. Skip/Incremental Semantics

### 9.1 Reuse Existing Semantics

CP2K uses the **same** skip semantics as other engines:

| Condition | Skip? |
|-----------|-------|
| `manifest.done = true` AND `fingerprint unchanged` | **YES** (skip, artifacts remain consumable) |
| `manifest.done = false` OR `fingerprint changed` | **NO** (must run) |
| Target step (in TARGET selection mode) | **NO** (must always run) |

### 9.2 MD Incremental Skip (DISABLED)

**CRITICAL**: MD steps (`cp2k_md`) have incremental skip **disabled**.

```python
"cp2k_md": StepTypeSpec(
    ...
    supports_incremental_skip=False,  # MD is non-idempotent
    ...
),
```

**Rationale**: MD produces time-series data; resuming from arbitrary point is complex. Users can use `restart_policy` for continuation.

### 9.3 Fingerprint Computation

Fingerprint hashes the **step.yaml content** as-is:
- Include all parameters
- Include step_type, name, etc.
- **DO NOT** special-case absolute paths

This is consistent with existing implementations. No cross-machine reproducibility guarantees.

---

## 10. Data/Basis/Potential Policy

### 10.1 No Data Staging

**Decision**: QMatSuite does NOT stage CP2K data files into a project-local directory.

| What | Where | QMatSuite Action |
|------|-------|------------------|
| Basis sets | CP2K_DATA_DIR or user path | **None** - just write to input |
| Potentials | CP2K_DATA_DIR or user path | **None** - just write to input |
| Validation | N/A | **None** - CP2K validates at runtime |

### 10.2 User Responsibility

Users can:
1. Rely on `CP2K_DATA_DIR` environment variable (recommended)
2. Specify explicit paths in step.yaml parameters
3. Use absolute paths if needed

Example step.yaml:
```yaml
parameters:
  basis_set_file_name: BASIS_MOLOPT   # Relative to CP2K_DATA_DIR
  potential_file_name: GTH_POTENTIALS
  # OR explicit paths:
  # basis_set_file_name: /path/to/custom/basis.dat
```

### 10.3 Input Generation

The engine writes whatever the user specifies:
```python
def _write_dft_section(params, f):
    if "basis_set_file_name" in params:
        f.write(f"    BASIS_SET_FILE_NAME {params['basis_set_file_name']}\n")
    if "potential_file_name" in params:
        f.write(f"    POTENTIAL_FILE_NAME {params['potential_file_name']}\n")
```

---

## 11. Recipe Declaration

### 11.1 Recipe Pattern

CP2K uses a **dedicated** `CP2KRecipe` class, NOT reusing VASPRecipe or LAMMPSRecipe.

**Rationale**: Per alignment decision - "Do NOT reuse any existing recipe class unless truly identical."

### 11.2 Recipe Characteristics

| Aspect | CP2K Behavior |
|--------|---------------|
| Jobs per step | 1 (one job per step) |
| Working directory | `calc/raw/<step_ulid>/` (Runtime SSOT) |
| Cleanup | **NO** |
| Command | `["cp2k.ssmp", "-i", "input.inp", "-o", "output.log"]` |
| Dependencies | Linear chain (topological predecessor) |
| Preflight | Declared via `get_preflight_requirements()` |

### 11.3 Registry Integration

```python
# In get_recipe_for_engine()
recipes = {
    "qe": QERecipe,
    "orca": ORCARecipe,
    "pyscf": PySCFRecipe,
    "vasp": VASPRecipe,
    "lammps": LAMMPSRecipe,
    "cp2k": CP2KRecipe,  # NEW: dedicated recipe
}
```

---

## 12. Engine Comparison Table

| Aspect | QE | VASP | LAMMPS | CP2K |
|--------|-----|------|--------|------|
| **Runtime SSOT** | `raw/` (shared) | `raw/<step_ulid>/` | `raw/<step_ulid>/` | `raw/<step_ulid>/` |
| **Scan Archive Shape** | `raw/scan/<vk>/` | `raw/scan/<vk>/<ulid>/` | `raw/scan/<vk>/<ulid>/` | `raw/scan/<vk>/<ulid>/` |
| **Workdir Cleanup** | No | **Yes (rm -rf)** | No | **No** |
| **Artifact Accumulation** | N/A | No (cleaned) | Yes | **Yes** |
| **Latest Selection** | By prefix | Fixed names | mtime | **mtime** |
| **Dependency Resolution** | outdir prefix | `raw/<ulid>/CHGCAR` | `raw/<ulid>/restart.bin` | `raw/<ulid>/*.wfn` |
| **Preflight Checks** | No | Yes (CHGCAR) | Yes (restart.bin) | **Yes (wfn/restart)** |
| **MD Incremental Skip** | N/A | N/A | **Disabled** | **Disabled** |

---

## 13. References

- [CP2K Manual - GLOBAL](https://manual.cp2k.org/trunk/CP2K_INPUT/GLOBAL.html)
- [CP2K Restarting Guide](https://www.cp2k.org/restarting)
- [CP2K Output Guide (BioExcel)](https://docs.bioexcel.eu/qmmm_bpg/en/main/running_cp2k/cp2k_output.html)
- [CP2K pwtools Restart Guide](https://elcorto.github.io/pwtools/written/cp2k_restart.html)
- [CP2K TRAJECTORY Section](https://manual.cp2k.org/trunk/CP2K_INPUT/MOTION/PRINT/TRAJECTORY.html)
- [CP2K CELL Print Section](https://manual.cp2k.org/trunk/CP2K_INPUT/MOTION/PRINT/CELL.html)
