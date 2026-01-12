# Phase 3C: PySCF Runner Semantics + UI Behavior Alignment

**Status**: Specification (Final)  
**Target**: PySCF v0 Runner Implementation  
**Last Updated**: 2025-01-10

---

## A1. Generalized Step Naming Alignment

### Rule: Generalized Step Key "td"

**Generalized step key MUST be "td"** (not "tddft" or "tdhf").

**QE Family Materialization**:
- Generalized `"td"` materializes to existing QE TDDFT step (machine type remains `qe_tddft` or equivalent)
- **No behavior change for QE**: Only generalized naming/template semantics change
- QE machine types remain unchanged to avoid breakage

**PySCF Family Materialization**:
- Generalized `"td"` materializes to `pyscf_td` (machine type)
- At runtime, `pyscf_td` uses TDDFT or TDHF backend depending on the immediately-provided SCF reference (see state rules below)
- Backend selection is automatic, not a user parameter

**Generalized "scf"**:
- Remains `"scf"` across QE and PySCF (name only; no attempt to unify physics yet)

---

## A2. PySCF Linear Dependency Model (NO DAG)

### Model: Linear Ordered List with State Dependencies

**Steps are a linear ordered list** (not a DAG). Each machine step declares:
- **`consumes_state`**: At most one dependency state type (optional)
- **`produces_state`**: Optional state type that this step produces

**Execution Resolution**:
- For a step that `consumes_state=X`, scan **left** (backward) in the step list for the **nearest** step that `produces_state=X`
- If no provider is found: **HARD ERROR**, do not run anything
- No molecule/basis consistency checks beyond this nearest-provider rule (the `mf` object already encodes molecule/basis)

**State Types (v0)**:
- `"mf"`: Produced by `pyscf_scf` (mean-field wavefunction/density)
- `"ccsd"`: Produced by `pyscf_ccsd` (if implemented/planned, v1)
- `"none"`: For read-only property steps that don't produce reusable state
  - Examples: `pyscf_mp2`, `pyscf_td`, `pyscf_freq`, `pyscf_analysis`, `pyscf_nmr`

**Step Type Registry Extensions**:
- Add `consumes_state: Optional[str]` to `StepTypeSpec`
- Add `produces_state: Optional[str]` to `StepTypeSpec`
- Default: `None` (no dependency, no production)

**Example**:
```
Steps: [scf, mp2, td]
- scf: produces_state="mf", consumes_state=None
- mp2: produces_state=None, consumes_state="mf"  → resolves to scf (nearest left)
- td: produces_state=None, consumes_state="mf"  → resolves to scf (nearest left)
```

---

## A3. Run Semantics (Must Match QE Mental Model)

### Three Run Modes

**1. Run Calc (Default) = Incremental**:
- For PySCF:
  - SCF may use `chkfile` as initial guess (`init_guess='chkfile'`) when available, but SCF still runs a kernel pass
  - All non-SCF steps are **ALWAYS full rerun** (no restart/skip, even if theoretically equivalent)
- For QE:
  - Preserve existing incremental behavior (unchanged)

**2. Run Calc → Dropdown "Full Run"**:
- Full Run means **fresh start for all steps**
- For PySCF:
  - SCF must **NOT** use `chkfile` init guess (fresh start)
  - Non-SCF: always rerun anyway (no change)
- For QE:
  - Preserve existing full run behavior (unchanged)

**3. Run Step(X)**:
- **First**: Resolve the dependency chain from X back to chain root (usually SCF), using the nearest-provider rule
- **Then**: Execute the chain in **one session** to produce needed in-memory objects
- **HARD RULE**: The target step X must **always** be a full rerun
- **For PySCF**:
  - If X is SCF: SCF must **NOT** use `chkfile` init guess (fresh start for that step)
  - For prerequisite steps in the chain (before X): Use normal incremental semantics (SCF may use `chkfile` init guess) **unless** they are also "the target"

**UI Consistency**:
- Run Calc button: Default incremental + dropdown "Full Run"
- This UI must apply to QE and PySCF consistently
- Only difference: PySCF SCF behavior regarding `chkfile` init guess

---

## A4. Checkpointing Policy (v0 Conservative)

**Only PySCF SCF produces a restartable on-disk checkpoint** (`chkfile`).

**Do NOT attempt**:
- "mf shim" restoration (injecting `mo_coeff` into a new `mf` object)
- Post-HF restart from disk

**If a post step requires an object not available in the current session**:
- You must run the dependency chain **in-session** (one PySCF process)
- Do not auto-recover post-HF from disk

**Conservative Policy Rationale**:
- PySCF best practice: Rerun SCF kernel to ensure consistency (especially for DFT with grid-dependent quantities)
- Post-HF calculations are fast relative to SCF; rerunning ensures correctness

---

## A5. Step Spec Storage Invariants

### SSOT: step.yaml

**step.yaml must contain**:
- `meta` (ULID, slug, name, path as applicable)
- `step_type` (machine type, engine-prefixed, e.g., `pyscf_scf`)
- `parameters` (only what this step controls)

**step.yaml MUST NOT contain**:
- Structure data (atoms, coordinates, charge, spin, unit, basis)
  - Structure is defined in `calculation.yaml` (via `structure_id` reference)
- Redundant SCF selections in downstream steps
  - SCF step.yaml: Contains SCF-relevant choices (`method`, `xc` if DFT, `basis`, `charge`, `spin`, etc.)
  - Downstream steps: **MUST NOT** redundantly store SCF selections (avoid double truth)

**chkfile path**:
- Keep as fixed convention (constant), do not store as a parameter
- Convention: `{step_artifacts_dir}/checkpoint.chk` for SCF step
- Unless existing contract forces it (then document deviation)

---

## Implementation Notes

### Chain Execution in PySCF Runner

**Session Model**:
- One PySCF subprocess session per dependency chain execution
- Import `pyscf` once in the session
- Execute required steps in order, building in-memory objects (`mol`, `mf`, etc.)
- Write artifacts per step (before each step run, clear that step's artifacts directory)

**Dependency Resolution**:
- Given target step ULID, compute chain root and run sequence
- Chain root: First step in the dependency chain (usually SCF)
- Run sequence: All steps from chain root to target (inclusive)

**Init Guess Control**:
- Incremental mode: Allow `chkfile` init guess when present (still run kernel)
- Full mode OR RunStep(target=scf): Forbid `chkfile` init guess

**Non-SCF Steps**:
- Always rerun regardless of done flags
- No checkpoint/restart for non-SCF steps in v0

---

## Deviations from Existing Architecture

**None anticipated**. This spec aligns with existing Phase 2 + Phase 3A/3B architecture:
- Workflow materialization (Phase 3B)
- Step type registry (Phase 2)
- Incremental run semantics (Phase 2)
- SSOT constraints (Phase 3A)

**If deviations are required**, document them explicitly in implementation.

---

**Document Status**: ✅ Complete (Specification)  
**Next Step**: Update execution plan, then implement

