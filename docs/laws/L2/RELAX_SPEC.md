# RELAX Step Specification (Constitution Amendment)

**Version**: 1.0.0
**Date**: 2026-01-18
**Status**: RATIFIED

---

## 1. Purpose and Scope

This specification defines the behavior of `relax` and `vc-relax` (collectively "relax steps")
in the QMatSuite system. Relax steps are **GEN step types** that:
- Optimize atomic positions (relax) or both positions and cell (vc-relax)
- Produce a **structure artifact** (not a ULID resource)
- Do NOT produce reusable electronic state for downstream steps

---

## 2. Core Invariants

### 2.1 Structure SSOT

**Invariant**: `calculation.structure` remains the SINGLE SOURCE OF TRUTH for the calculation's
reference structure. It is immutable during run.

- The structure referenced by `calculation.structure_id` is NEVER mutated by relax.
- Relax output is a **private artifact**, not a project resource.
- Promoting relax output to a project resource is an explicit user action.

### 2.2 No Reusable Electronic State

**Invariant**: Relax steps do NOT contribute to the electronic state dependency chain.

- QC engines (ORCA/PySCF): Relax is always a **standalone chain** (length=1).
- QE: Relax may write to outdir, but downstream steps MUST NOT depend on relax's charge density.
- Registry: `produces_charge_density = False` for all relax step types.

### 2.3 Artifact Semantics (Not ULID)

**Invariant**: Generated structures are artifacts, not ULID-tracked resources.

```
Path: calculations/<calc_id>/generated_structures/step_<relax_step_ulid>/current.json
```

- `current.json` uses the same schema as `project/structures/*.json` (pymatgen-compatible)
- Includes optional `provenance` field for traceability
- NOT registered in ResourceIndex
- NOT assigned a ULID until promoted

---

## 3. File Layout

### 3.1 Generated Structures Directory

```
project_root/
├── calculations/
│   └── <calc_id>/
│       ├── calculation.yaml
│       ├── steps/
│       │   └── relax.step.yaml
│       ├── generated_structures/
│       │   └── step_<relax_step_ulid>/
│       │       └── current.json
│       └── raw/
│           └── relax.out
```

### 3.2 current.json Schema

```json
{
  "__qv_meta__": {
    "type": "generated_structure",
    "source_step_ulid": "<step_ulid>",
    "source_run_id": "<run_id>",
    "generated_at": "<iso8601>",
    "provenance": {
      "method": "qe_vc_relax",
      "input_structure_ulid": "<original_structure_ulid>",
      "calculation_ulid": "<calc_ulid>"
    }
  },
  "@module": "pymatgen.core.structure",
  "@class": "Structure",
  "lattice": { ... },
  "sites": [ ... ]
}
```

---

## 4. Run Semantics

### 4.1 Effective Structure (Runtime Only)

During execution, the runner maintains an **effective structure** in memory:

1. **Initial**: Load from `calculation.structure_id`
2. **After Relax Success**: Update to parsed relaxed structure (and write `current.json`)
3. **Missing Relax Output**: Hard error (see §5.2)

**Note**: Effective structure is NOT persisted. On resume, it's reconstructed from:
- Initial structure (always available)
- `current.json` for any completed relax steps

### 4.2 Pre-Run Cleanup (Scoped)

Before each job starts:
- Identify relax steps covered by this job
- Delete ONLY those steps' `current.json` files
- Purpose: Ensure `current.json` existence implies success in THIS run

### 4.3 Post-Relax Success

After a relax step completes successfully:
1. Parse output using `read_final_geometry_from_output_text()`
2. Canonicalize using `structure_from_qe_geometry_snapshot()` (unified entry point)
3. Write `current.json` with provenance
4. Update in-memory effective structure
5. Mark step as done in manifest

### 4.4 Relax Failure Semantics

If relax step fails:
- `current.json` is NOT written (pre-run cleanup already deleted it)
- Job aborts (fail-fast)
- Downstream steps do NOT execute

---

## 5. Error Semantics

### 5.1 QC Topology Errors (Run-Time Verify)

For QC engines (ORCA/PySCF), topology is verified BEFORE execution:

| Violation | Error Message |
|-----------|---------------|
| Non-relax step's nearest SCF is blocked by relax | `TOPOLOGY_ERROR: Step '{step_name}' (index {i}) cannot trace to SCF root. A relax step at index {j} blocks the dependency chain. Relax steps are not electronic state providers; they must be in standalone chains.` |
| Non-relax, non-SCF step has no SCF ancestor | `TOPOLOGY_ERROR: Step '{step_name}' (index {i}) requires SCF root but none found. Add an SCF step before this step.` |

### 5.2 Missing Generated Structure

When a step requires effective structure from a previous relax:

```
MISSING_ARTIFACT_ERROR: Step '{step_name}' requires the relaxed structure from
step '{relax_step_name}' (ULID: {relax_ulid}), but generated_structures/step_{relax_ulid}/current.json
is missing.

This typically means:
- The relax step has not been executed yet
- The relax step failed before producing output
- The generated_structures directory was deleted

To fix: Run the calculation from the beginning, or run the relax step first.
DO NOT manually create this file.
```

### 5.3 Relax Output Parse Failure

```
PARSE_ERROR: Failed to extract final structure from relax output '{output_file}'.
The output file may be incomplete (calculation crashed or was interrupted).

Details: {parse_error_message}
```

---

## 6. QC vs QE Topology Rules

### 6.1 QC Family (ORCA/PySCF) — Strong Chain + Relax Isolation

**Rule**: Relax steps are ALWAYS standalone chains (length=1). They cannot be part of an SCF-root chain.

#### 6.1.1 run_step(target) Logic

```python
if is_relax(target):
    # Execute only this relax step
    return execute_single_step(target)
else:
    # Scan backward for nearest SCF
    for j in range(target_idx - 1, -1, -1):
        if is_relax(steps[j]):
            raise TopologyError("Non-relax step cannot trace through relax")
        if is_scf_root(steps[j]):
            # Found SCF root, execute chain [j..target_idx]
            return execute_chain(steps[j:target_idx+1])
    raise TopologyError("No SCF root found for non-relax step")
```

#### 6.1.2 run_calc() Pre-Verification

Before executing any step, verify the entire topology:

```python
for i, step in enumerate(steps):
    if is_relax(step):
        continue  # Relax is standalone, no dependency check
    if is_scf_root(step):
        continue  # SCF root starts a new chain
    # Non-relax, non-SCF: must have SCF ancestor without intervening relax
    for j in range(i - 1, -1, -1):
        if is_relax(steps[j]):
            raise TopologyError(f"Step {i} blocked by relax at {j}")
        if is_scf_root(steps[j]):
            break  # Valid: found SCF root
    else:
        raise TopologyError(f"Step {i} has no SCF root")
```

#### 6.1.3 Allowed/Forbidden Topologies

| Topology | Valid? | Reason |
|----------|--------|--------|
| `scf → tddft → relax → scf → mp2` | ✅ | Relax is standalone; second scf starts new chain |
| `scf → relax → tddft` | ❌ | tddft's nearest scf blocked by relax |
| `relax → scf → tddft` | ✅ | Relax is standalone; scf→tddft is valid chain |
| `scf → mp2 → relax` | ✅ | scf→mp2 is chain; relax is standalone |
| `relax → tddft` | ❌ | tddft has no SCF root |
| `scf → relax → scf → relax → mp2` | ❌ | mp2's nearest scf blocked by second relax |
| `scf → scf → tddft` | ✅ | Second scf starts new chain; tddft uses second scf |

### 6.2 QE Family — Lenient Topology

**Rule**: QE does not enforce SCF-root chains. Relax can appear anywhere.

- `run_step(target)`: Execute only target step
- `run_calc()`: Execute all steps in order

**Warning** (non-blocking): If relax appears between steps that typically share charge density:
```
WARNING: Relax step at index {j} may disrupt charge density continuity between
steps {i-1} and {i}. Consider verifying your workflow topology.
```

---

## 7. Promote UX

### 7.1 Promote API

```python
def promote_relax_structure(
    project_root: Path,
    calculation_selector: str,
    step_selector: str,  # ULID of relax step
    name: Optional[str] = None,
) -> ResolvedResource:
    """
    Promote a relax step's generated structure to a project resource.
    
    Creates a new structure in project/structures with a new ULID.
    Records provenance linking back to source calculation/step/run.
    
    Args:
        project_root: Project root path
        calculation_selector: Calculation ULID or slug
        step_selector: Relax step ULID
        name: Optional name for the new structure
        
    Returns:
        ResolvedResource for the newly created structure
        
    Raises:
        QVServiceError: If step not found, not a relax step, or no current.json
    """
```

### 7.2 UI Behavior

1. Dropdown lists all relax steps in calculation that have `current.json`
2. Default selection: Last relax step
3. Preview shows structure comparison (original vs relaxed)
4. "Promote" button creates new structure resource
5. Success: Navigate to new structure in library

---

## 8. Incremental Run Semantics

### 8.1 Structure SHA in Manifest

Manifest entries include `effective_structure_sha`:
- For non-relax steps: SHA of effective structure at execution time
- For relax steps: SHA of INPUT structure (not output)

### 8.2 Skip Logic with Effective Structure

A step can be skipped if:
1. `done = True` in manifest
2. `step_sha` matches current step YAML
3. `pseudo_set_sha` matches current pseudo set
4. `effective_structure_sha` matches current effective structure

If any SHA changes, step must re-run.

### 8.3 Cascade Invalidation

If a relax step's inputs change:
1. Relax step must re-run
2. Its `current.json` will be regenerated
3. All downstream steps using that effective structure are invalidated
   (their `effective_structure_sha` won't match)

---

## 9. Future Extensions (Not in Scope)

- **Multi-stage relax**: Sequential relax steps with structure chaining
- **Selective atom relaxation**: Freeze certain atoms
- **Convergence criteria customization**: Force/stress thresholds
- **Cross-engine relax**: Use QE relax output for ORCA calculations

---

## Appendix A: Registry Changes

```python
# Before
"qe_relax": StepTypeSpec(
    id="relax",
    machine_type="qe_relax",
    public_type="relax",
    engine="qe",
    executable="pw.x",
    produces_charge_density=True,  # WRONG
)

# After
"qe_relax": StepTypeSpec(
    id="relax",
    machine_type="qe_relax",
    public_type="relax",
    engine="qe",
    executable="pw.x",
    produces_charge_density=False,  # Relax doesn't produce reusable state
    is_structure_transform=True,     # NEW: Marks step as structure transform
)
```

## Appendix B: Existing Step Types to Modify

| Step Type | Change |
|-----------|--------|
| `qe_relax` | `produces_charge_density=False`, `is_structure_transform=True` |
| `qe_vc_relax` | `produces_charge_density=False`, `is_structure_transform=True` |
| `qe_md` | (Future) Similar treatment if needed |
| `qe_vc_md` | (Future) Similar treatment if needed |

