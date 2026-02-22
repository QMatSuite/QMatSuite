# CP2K Code Review Notes

**Last Updated**: 2026-01-20 (v2 - Alignment Update)
**Reviewer**: Claude Code (Opus)
**Purpose**: Targeted code review for CP2K integration with updated alignment decisions

---

## 1. Review Scope (Updated)

This review examines QMatSuite code areas relevant to CP2K integration, with specific focus on:
1. **Scan archive semantics** - `raw/scan/` is archive-only, never SSOT
2. **Dependency resolution** - must always read from runtime SSOT (`raw/<step_ulid>/`)
3. **Latest artifact selection** - mtime-based (generalized mechanism)
4. **Preflight checks** - general feature with engine declarations
5. **Workdir cleanup** - which engines clear vs accumulate

---

## 2. Scan Archive Semantics (CRITICAL UPDATE)

### 2.1 Core Principle: raw/scan is Archive-Only

**File**: `src/qmatsuite/execution/post_job.py`

The scan archive is **NEVER the runtime SSOT**. It exists only for post-run analysis/UI inspection.

| Concept | Location | Purpose |
|---------|----------|---------|
| **Runtime SSOT** | `calc/raw/<step_ulid>/` | Active execution artifacts |
| **Scan Archive** | `calc/raw/scan/<variant_key>/` | Post-run copy for analysis |

**Code evidence** (`post_job.py` lines 131-171):
```python
class ArchiveToSlotAction(PostJobAction):
    def execute(self, job_result: Any, context: PostJobContext) -> None:
        """
        Archive job outputs to raw/scan/<variant_key>/.

        Archives on both success and failure (best-effort).
        """
        dest_dir = context.calc_raw_dir / "scan" / self.variant_key
        dest_dir.mkdir(parents=True, exist_ok=True)

        # Compute diff (files created/modified during variant execution)
        new_modified = compute_snapshot_diff(before=pre_snapshot, after=post_snapshot, ...)

        # Copy files to slot - PRESERVES RELATIVE PATHS
        for rel_path in new_modified:
            src = context.calc_raw_dir / rel_path
            dst = dest_dir / rel_path  # <-- preserves <step_ulid>/file structure
            shutil.copy2(src, dst)
```

### 2.2 Archive Structure for Per-Step Engines

For engines using per-step workdirs (VASP, LAMMPS, CP2K), the archive **preserves relative paths**:

```
calc/raw/
├── <step_ulid_1>/           # Runtime SSOT for step 1
│   ├── POSCAR
│   └── OUTCAR
├── <step_ulid_2>/           # Runtime SSOT for step 2
│   └── ...
└── scan/
    └── <variant_key>/       # Archive copy
        ├── <step_ulid_1>/   # Copied from raw/<step_ulid_1>/
        │   ├── POSCAR
        │   └── OUTCAR
        └── <step_ulid_2>/   # Copied from raw/<step_ulid_2>/
            └── ...
```

**CP2K must follow this exact pattern**. The archive ends up as `raw/scan/<variant_key>/<step_ulid>/*`.

### 2.3 What This Means for Dependency Resolution

**CRITICAL**: Dependency resolution (restart/wfn lookup) must **NEVER** reference `raw/scan/`.

**File**: `src/qmatsuite/engine/lammps_engine.py` (lines 376-380)
```python
def _resolve_restart_artifact(self, step, calculation):
    # Find artifact in reference step's workdir
    ref_workdir = calculation.io.raw_dir / ref_step_ulid  # <-- Runtime SSOT
    # NOT: calculation.io.raw_dir / "scan" / variant_key / ref_step_ulid
```

---

## 3. Dependency Resolution Code Paths

### 3.1 Current Implementation (VASP)

**Files**:
- `src/qmatsuite/execution/reference_resolver.py` - Finds reference SCF step
- `src/qmatsuite/execution/vasp_staging.py` - Stages CHGCAR/WAVECAR

**Pattern**:
```python
# reference_resolver.py - finds the step object
ref_result = find_reference_scf(steps_list, current_idx)
ref_idx, ref_scf_step = ref_result

# vasp_staging.py - reads from runtime SSOT
ref_workdir = calc_raw_dir / reference_scf_step.meta.id  # <-- raw/<step_ulid>
chgcar_src = ref_workdir / "CHGCAR"
```

### 3.2 Current Implementation (LAMMPS)

**File**: `src/qmatsuite/engine/lammps_engine.py` (lines 314-438)

```python
def _resolve_restart_artifact(self, step, calculation):
    restart_from = params.get("restart_from")

    # Find referenced step in calculation
    ref_step = ...

    # Read from runtime SSOT directory
    ref_workdir = calculation.io.raw_dir / ref_step_ulid

    # Search for artifacts
    restart_bin = ref_workdir / "restart.bin"
    if restart_bin.exists():
        return restart_bin
    # ... pattern search ...

    raise FileNotFoundError(f"No restart artifact found for step {restart_from}")
```

### 3.3 CP2K Dependency Resolution (Must Implement)

CP2K must follow the same pattern:
1. Resolve predecessor step linearly (topological order)
2. Read artifacts from `calc/raw/<predecessor_ulid>/`
3. NEVER reference `raw/scan/`
4. Hard error if required artifact missing (preflight check)

---

## 4. Latest Artifact Selection (NEW: mtime-based)

### 4.1 Previous Approach (Deprecated)

The previous spec proposed numeric suffix parsing (e.g., `cp2k_calc-5.restart > cp2k_calc-1.restart`).

### 4.2 Updated Approach: mtime-based Selection

**Rationale**: More robust short-term; doesn't rely on CP2K naming conventions.

**Implementation pattern** (to be generalized, not CP2K-only):

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

### 4.3 Engine Recipe Declaration

Each engine recipe should declare its artifact patterns and selection strategy:

```python
class CP2KRecipe(BaseRecipe):
    # Artifact patterns for latest selection
    ARTIFACT_PATTERNS = {
        "restart": "cp2k_calc-*.restart",
        "wfn": "cp2k_calc-RESTART.wfn",  # No mtime needed (single file)
        "trajectory": "cp2k_calc-pos-*.xyz",
        "energy": "cp2k_calc-*.ener",
        "cell": "cp2k_calc-*.cell",
    }
```

---

## 5. Preflight Checks (NEW: General Feature)

### 5.1 Current Implementation (VASP)

**File**: `src/qmatsuite/execution/vasp_staging.py`

VASP already has preflight-style checks:
```python
if not chgcar_src.exists():
    if is_current_scf:
        return  # Optional for SCF
    else:
        raise MissingArtifactError(
            f"CHGCAR not found in reference SCF workdir: {ref_workdir}."
        )
```

### 5.2 Current Implementation (LAMMPS)

**File**: `src/qmatsuite/engine/lammps_engine.py`

LAMMPS has similar checks:
```python
raise FileNotFoundError(
    f"No restart artifact found for step {restart_from}. "
    f"Expected restart.bin or final.data in {ref_workdir}"
)
```

### 5.3 Generalized Preflight Checker (To Implement)

**Goal**: Extract preflight logic into a reusable component.

```python
# Proposed: src/qmatsuite/execution/preflight.py

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
        """
        Check all requirements before launching engine.

        Raises:
            PreflightError: If required artifact missing
        """
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
```

**Engine recipe declares requirements**:
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

---

## 6. Workdir Cleanup Analysis

### 6.1 Current Cleanup Behavior by Engine

| Engine | Cleans Workdir? | Code Location | Behavior |
|--------|-----------------|---------------|----------|
| **VASP** | **YES** | `handlers.py:350-355` | `shutil.rmtree(working_dir)` |
| LAMMPS | No | `handlers.py:519-521` | `mkdir(parents=True, exist_ok=True)` |
| QE | No | `handlers.py:191-192` | Shared outdir model |
| ORCA | No | `handlers.py:926-928` | Chain namespace folder |
| PySCF | No | `handlers.py:797-798` | Chain namespace folder |
| **CP2K** | **No** (required) | TBD | Accumulate like LAMMPS |

### 6.2 VASP Cleanup Code

**File**: `src/qmatsuite/execution/handlers.py` (lines 350-355)
```python
# Clean workdir completely (rm -rf)
working_dir = job.working_dir
if working_dir.exists():
    import shutil
    shutil.rmtree(working_dir)
working_dir.mkdir(parents=True, exist_ok=True)
```

### 6.3 LAMMPS Accumulate Code

**File**: `src/qmatsuite/execution/handlers.py` (lines 519-521)
```python
# Create workdir (LAMMPS uses isolated workdir per step)
working_dir = job.working_dir
working_dir.mkdir(parents=True, exist_ok=True)
# NOTE: No shutil.rmtree() - accumulates
```

### 6.4 CP2K Requirement

**CP2K MUST NOT cleanup workdir**. Follow LAMMPS pattern exactly:
```python
def cp2k_step_handler(...):
    working_dir = job.working_dir
    working_dir.mkdir(parents=True, exist_ok=True)
    # DO NOT add shutil.rmtree() - CP2K accumulates artifacts
```

---

## 7. Engine Comparison Table (Updated)

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

## 8. Files Requiring Modification

### 8.1 New Files to Create

| File | Purpose |
|------|---------|
| `src/qmatsuite/execution/preflight.py` | General preflight checker |
| `src/qmatsuite/execution/latest_selector.py` | mtime-based artifact selector |
| `src/qmatsuite/core/engines/cp2k_resolver.py` | CP2K binary discovery |
| `src/qmatsuite/engine/cp2k_engine.py` | CP2K engine class |
| `src/qmatsuite/engine/cp2k_writer.py` | Input file generator |
| `src/qmatsuite/engine/cp2k_parser.py` | Output parser |

### 8.2 Files to Modify

| File | Change |
|------|--------|
| `src/qmatsuite/workflow/registry.py` | Add cp2k_scf, cp2k_relax, cp2k_md |
| `src/qmatsuite/workflow/generalized_steps.py` | Add CP2K MATERIALIZATION_MAP entries |
| `src/qmatsuite/execution/recipes.py` | Add CP2KRecipe, update factory |
| `src/qmatsuite/execution/handlers.py` | Add cp2k_step_handler, update handler map |
| `src/qmatsuite/execution/relax_artifacts.py` | Add cp2k_trajectory handler |
| `src/qmatsuite/engine/registry.py` | Register Cp2kEngine |

### 8.3 Files NOT Requiring Modification

| File | Reason |
|------|--------|
| `src/qmatsuite/execution/post_job.py` | Archive logic already correct |
| `src/qmatsuite/execution/scan_expansion.py` | Variant machinery unchanged |
| `src/qmatsuite/calculation/manifest.py` | Fingerprint system unchanged |

---

## 9. Critical Implementation Notes

### 9.1 Non-Negotiable Rules

1. **DO NOT reuse VASPRecipe/LAMMPSRecipe** - Create CP2KRecipe from scratch
2. **DO NOT add workdir cleanup** - CP2K accumulates
3. **DO NOT reference raw/scan/ for dependencies** - Only runtime SSOT
4. **DO NOT skip Phase 0** - Must run real CP2K locally
5. **DO include preflight checks** - General mechanism with CP2K declarations

### 9.2 Uniform Scan Archive

CP2K scan archive must follow the **exact same structure** as VASP/LAMMPS:
- Archive location: `raw/scan/<variant_key>/<step_ulid>/*`
- Created by existing `ArchiveToSlotAction`
- No CP2K-specific archive directories

### 9.3 MD Incremental Skip

For MD steps (cp2k_md):
- `supports_incremental_skip = False` in StepTypeSpec
- Always execute when targeted
- Continuation allowed via `restart_policy` parameter
