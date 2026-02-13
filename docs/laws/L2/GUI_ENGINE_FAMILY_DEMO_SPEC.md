# GUI Engine-Family & Demo System Specification

**Status**: ACTIVE (binding design spec)
**Version**: 1.1
**Date**: 2026-02-07
**Authority**: Derived from GUI/Demo audit (`docs/history/audits/GUI_ENGINE_DEMO_AUDIT.md`), Constitution, ENGINE_RECIPE_AND_RUNNER_CONSTITUTION, B1_ENGINE_PLAYBOOK

---

### Changelog

**v1.1 (2026-02-07)** — UNDECIDED/DECIDED model, base/postproc classification, companion allowlist

- **EF1 rewritten**: `engine_family` is now nullable (UNDECIDED) when a calculation has zero base steps; becomes immutable once set (DECIDED). Replaces "required at creation" from v1.0.
- **EF3 rewritten**: Cross-engine steps now use an explicit **companion allowlist** per base family. Replaces "StepTypeRegistry first-match" from v1.0.
- **EF4 updated**: UNDECIDED state is legal under strict constraints. Silent `"qe"` default remains banned.
- **New §2.1**: Base vs Postprocessing engine classification with evidence table.
- **New §2.2**: Postprocessing gen step collision report (proves UNDECIDED safety).
- **New §2.3**: Base-family companion allowlist (explicit compatibility matrix).
- **New §2.4**: UNDECIDED/DECIDED state machine with formal transition rules.
- **Laws EF7-EF9 added**: Base-step trigger, postproc uniqueness, companion completeness.
- **§4 rewritten**: Materialization now branches on UNDECIDED vs DECIDED.
- **§5.1-5.2 updated**: Calc init UI supports UNDECIDED; step palette separates base vs postproc.
- **§7 updated**: Demo guidance simplified; reference artifact format left open for future AnalysisObject primitives.
- **§8 updated**: Phase 1 expanded for UNDECIDED/DECIDED model.
- **§9 updated**: New gate tests for postproc uniqueness and companion completeness.
- **NG2 relaxed**: Calculations no longer force engine_family at creation; they can start UNDECIDED.

**v1.0 (2026-02-07)** — Initial spec.

---

## 0. Purpose

This document specifies the long-term (10-year) architecture for:
1. How QMatSuite handles **engine families** in calculations — the UNDECIDED/DECIDED lifecycle, selection, materialization, parameter editing.
2. How the **GUI** routes on `engine_family` to be engine-agnostic.
3. How the **metadata/parameter UX** generalizes beyond QE.
4. How the **demo system** is standardized, verified, and consumed.

After implementation, QE becomes one engine among many — no special-cased code paths in GUI, daemon, or service layer.

---

## 1. Goals and Non-Goals

### Goals
- G1: User can create a calculation targeting **any** registered base engine via the GUI.
- G2: The step palette and workflow templates adapt to the chosen engine family.
- G3: Parameter editing works for all engines — **guided** mode via engine metadata + **raw** override.
- G4: Runtime-managed keys are displayed read-only for all engines, not just QE.
- G5: Demo gallery serves verified, runnable project snapshots for multiple engines.
- G6: QE has zero special-case code in the GUI, daemon RPCs, or service layer.
- G7: Users can add postprocessing steps (Wannier90, QMCPACK, Yambo) before choosing a base engine.

### Non-Goals
- NG1: Separate demo repository (demos stay in-repo under `resources/demo_projects/`).
- NG2: ~~Cross-family calculation.~~ *(v1.1: removed — calculations start UNDECIDED and may hold postproc steps from multiple engines before a base family is chosen; once DECIDED, the companion allowlist governs.)*
- NG3: GUI-side input file editor (users edit parameters, not raw input text).
- NG4: Engine binary management in GUI beyond detection + path configuration (no auto-install).
- NG5: Family downgrade/conversion as a user operation. Changing a DECIDED calculation's engine family is not supported. A future "Duplicate calculation (variant)" flow may create a copy targeting a different family, but that is a new calculation, not a mutation of the original.

---

## 2. SSOT, Invariants, and Classification

### Law EF1 — Engine Family Lifecycle: UNDECIDED → DECIDED

`calculation.yaml` carries `engine_family: str | null`.

A calculation exists in exactly one of two states:

| State | `engine_family` value | Permitted steps | Transition |
|-------|----------------------|-----------------|------------|
| **UNDECIDED** | `null` | Postprocessing steps only (§2.1) | → DECIDED when user adds a base step |
| **DECIDED** | non-null string | Base steps + allowed companions (§2.3) | Terminal (immutable) |

**UNDECIDED → DECIDED** is the only legal transition. Once `engine_family` is set to a non-null value, it is immutable for the lifetime of that calculation. There is no DECIDED → UNDECIDED transition and no DECIDED(X) → DECIDED(Y) transition.

Rationale: changing engine family would invalidate all existing base steps' `step_type_spec` values. Postprocessing steps added in UNDECIDED state remain valid because their spec types are globally unique (Law EF8) and their compatibility with the chosen base family is enforced at decision time (Law EF9).

### Law EF2 — Gen→Spec Uniqueness Within a Family

For a given engine `E` with `SUPPORTED_GEN_STEPS = S`:

```
∀ g ∈ S: materialize(E, g) = "{E.PREFIX}_{g}"    [injective by construction]
```

Two engines `E1`, `E2` may share gen names (e.g., both support "scf"), but within one DECIDED calculation only one base engine family is active, so the mapping is unambiguous.

### Law EF3 — Cross-Engine Steps via Companion Allowlist

A DECIDED calculation with `engine_family = F` may contain steps from engines **other** than `F`, but **only** from engines explicitly listed in `F`'s **companion allowlist**.

The companion allowlist is a static declaration on the base engine driver:

```python
# On BaseEngineDriver (or overridden per driver):
COMPANION_ENGINES: frozenset[str] = frozenset()  # Default: no companions
```

Example: QE declares `COMPANION_ENGINES = frozenset({"w90", "qmcpack", "yambo"})`.

For a step with gen key `g` in a DECIDED calculation:
- If `g ∈ F.SUPPORTED_GEN_STEPS`: materialized via `DriverRegistry.materialize_step_type(F, g)`.
- If `g` is a gen step of some engine `C` where `C ∈ F.COMPANION_ENGINES`: materialized via `DriverRegistry.materialize_step_type(C, g)`.
- Otherwise: `UnsupportedStepError`. Hard error, no fallback.

**The `StepTypeRegistry.get(g)` first-match path is eliminated.** Cross-engine allowance is always explicit.

### Law EF4 — No Silent Fallbacks

If a base step is added and `engine_family` is `null` (UNDECIDED), the system MUST prompt the user to choose a family before materializing. No defaulting to `"qe"`.

**Current violations** (to be fixed):
- `service.py:3825`: `engine_family = getattr(calc_model, 'engine_family', None) or "qe"`
- `service.py:3182`: `engine = step_spec.engine if step_spec else "qe"`
- `service.py:7267`: default `engine_family: str = "qe"` parameter
- `service.py:6244`: `engine_family = "pyscf" if structure_kind == "molecule" else "qe"`

All four MUST become hard errors or explicit user prompts.

### Law EF5 — Spec Type Encodes Engine

`step_type_spec` is always `"{PREFIX}_{gen}"`. The prefix is the canonical engine identifier. The runner extracts the engine from the spec via `prefix_from(spec)` and dispatches via `DriverRegistry.get_handler()`. No other dispatch path exists.

### Law EF6 — Demo Integrity

Every demo snapshot under `resources/demo_projects/` MUST satisfy:
- Every step's `step_type_spec` prefix matches either the calculation's `engine_family` or an engine in that family's companion allowlist (Law EF3).
- `engine_family` is explicit on every calculation (demos are always DECIDED).
- The demo has been materialized and either run to completion or explicitly marked as "structural only" if the engine binary is not freely available.

**Current violations** (to be fixed):
- `water_orca_scf.yml`: `engine_family: orca`, `step_type_spec: qe_scf`
- `methane_orca_freq.yml`: `engine_family: orca`, `step_type_spec: qe_scf`
- `formaldehyde_orca_tddft.yml`: `engine_family: orca`, steps use `qe_scf` and `pyscf_td`
- 14 QE demos + 3 W90 demos + 1 PySCF demo: missing explicit `engine_family`

### Law EF7 — Base-Step Trigger

Adding a **base gen step** (any gen step belonging to a base engine's `SUPPORTED_GEN_STEPS`) to an UNDECIDED calculation **forces** the UNDECIDED → DECIDED transition. The user MUST select an engine family before the step can be materialized. See §2.1 for the definition of base gen steps.

### Law EF8 — Postprocessing Gen Step Global Uniqueness

Every postprocessing engine's gen step names MUST be globally unique — no gen step name may appear in more than one postprocessing engine's `SUPPORTED_GEN_STEPS`, and no postprocessing gen step name may appear in any base engine's `SUPPORTED_GEN_STEPS`.

This invariant is what makes UNDECIDED-state postprocessing safe: since each postprocessing gen step maps to exactly one engine worldwide, materialization is unambiguous without knowing the base family.

If a future engine registration would violate this uniqueness, that engine's conflicting gen steps MUST NOT be allowed in UNDECIDED state. The gate test (§9) enforces this at CI time.

### Law EF9 — Companion Completeness

When a calculation transitions from UNDECIDED to DECIDED with family `F`, every postprocessing step already present in the calculation MUST belong to an engine in `F.COMPANION_ENGINES`. If any existing postprocessing step belongs to an engine not in `F.COMPANION_ENGINES`, the transition MUST be rejected with a clear error naming the incompatible steps.

---

### 2.1 Base vs Postprocessing Engine Classification

**Classification criterion**: A **base engine** can produce an electronic ground state (or classical equilibrium) from scratch — it needs only a structure and parameters. A **postprocessing engine** requires artifacts (wavefunctions, charge densities, or databases) produced by a prior base-engine calculation.

#### Base Engines (12)

| Engine | `engine_family` | `PREFIX` | `SUPPORTED_GEN_STEPS` | Category | Evidence |
|--------|----------------|----------|-----------------------|----------|----------|
| Quantum ESPRESSO | `qe` | `qe` | scf, nscf, relax, bands, bandspw, dos, pw2wannier, ph, md, custom | Periodic (PW-DFT) | `drivers/qe/driver.py:10-13` |
| VASP | `vasp` | `vasp` | scf, nscf, relax, md, bandspw | Periodic (PW-DFT) | `drivers/vasp/driver.py:23-25` |
| ABINIT | `abinit` | `abinit` | scf, nscf, relax | Periodic (PW-DFT) | `drivers/abinit/driver.py:21-23` |
| CP2K | `cp2k` | `cp2k` | scf, relax, md, bandspw, dos | Periodic (mixed basis) | `drivers/cp2k/driver.py:25-27` |
| Siesta | `siesta` | `siesta` | scf, relax, md, bands, dos | Periodic (NAO-DFT) | `drivers/siesta/driver.py:26-28` |
| GPAW | `gpaw` | `gpaw` | scf, nscf, relax, bandspw, dos, md | Periodic (PW-DFT) | `drivers/gpaw/driver.py:24-26` |
| ORCA | `orca` | `orca` | scf, hf, relax, td | Molecular (QC) | `drivers/orca/driver.py:21-23` |
| Gaussian | `gaussian` | `gaussian` | scf, hf, relax, freq, mp2, td | Molecular (QC) | `drivers/gaussian/driver.py:27-29` |
| Psi4 | `psi4` | `psi4` | scf, hf, mp2, relax, td | Molecular (QC) | `drivers/psi4/driver.py:22-24` |
| PySCF | `pyscf` | `pyscf` | scf, relax, mp2, td | Molecular (QC) | `drivers/pyscf/driver.py:23-25` |
| xTB | `xtb` | `xtb` | relax | Molecular (semi-empirical) | `drivers/xtb/driver.py:27` |
| LAMMPS | `lammps` | `lammps` | minimize, md, relax | Classical MD | `drivers/lammps/driver.py:29-31` |

#### Postprocessing Engines (3)

| Engine | `engine_family` | `PREFIX` | `SUPPORTED_GEN_STEPS` | Depends On | Evidence |
|--------|----------------|----------|-----------------------|-----------|----------|
| Wannier90 | `w90` | `w90` | wannierprep, wannier | QE (pw2wannier90.x bridge) | `drivers/w90/driver.py:32-34`, `workflow/registry.py:316-345` |
| QMCPACK | `qmcpack` | `qmcpack` | vmc, dmc, wfopt | QE (pw2qmcpack.x bridge) | `drivers/qmcpack/driver.py:21-23`, `core/engines/qmcpack_resolver.py:117-172` |
| Yambo | `yambo` | `yambo` | setup, gw, bse, optics | QE (p2y converter in yambo binary) | `drivers/yambo/driver.py:28-30`, `drivers/yambo/artifact_resolver.py:18-58` |

**Why these three are postprocessing**:
- **Wannier90**: Constructs maximally-localized Wannier functions from Bloch states. Requires `.amn`, `.mmn`, `.eig` files produced by the QE-specific `pw2wannier90.x` utility. No standalone ground-state capability.
- **QMCPACK**: Quantum Monte Carlo solver. Requires an HDF5 trial wavefunction produced by the QE-specific `pw2qmcpack.x` utility. Cannot generate its own electronic structure.
- **Yambo**: Many-body perturbation theory (GW, BSE). Requires a DFT database converted from QE's `.save/` directory via the `p2y` converter (embedded in the yambo binary). Cannot perform DFT.

### 2.2 Postprocessing Gen Step Collision Report

For UNDECIDED calculations to safely allow postprocessing steps, every postprocessing gen step name must be globally unique.

**Postprocessing gen step inventory**:

| Engine | Gen Steps |
|--------|-----------|
| w90 | `wannierprep`, `wannier` |
| qmcpack | `vmc`, `dmc`, `wfopt` |
| yambo | `setup`, `gw`, `bse`, `optics` |

**Cross-postprocessing collision check**: 9 distinct gen step names across 3 engines. **Zero collisions** — no gen step name appears in more than one postprocessing engine.

**Postprocessing-vs-base collision check**: None of the 9 postprocessing gen step names (`wannierprep`, `wannier`, `vmc`, `dmc`, `wfopt`, `setup`, `gw`, `bse`, `optics`) appear in any base engine's `SUPPORTED_GEN_STEPS`.

All base engine gen steps (union):
`scf, nscf, relax, bands, bandspw, dos, pw2wannier, ph, md, custom, hf, freq, mp2, td, minimize`

Intersection with postprocessing gen steps: **empty set**.

**Conclusion**: Law EF8 is satisfied for the current 15-engine set. All postprocessing gen steps can be safely materialized in UNDECIDED state without ambiguity.

### 2.3 Base-Family Companion Allowlist

Each base engine explicitly declares which postprocessing engines it can host. This is the SSOT for cross-engine compatibility in DECIDED calculations.

| Base Family | `COMPANION_ENGINES` | Evidence |
|-------------|---------------------|----------|
| `qe` | `{"w90", "qmcpack", "yambo"}` | QE provides pw2wannier90.x (`registry.py:326`), pw2qmcpack.x (`qmcpack_resolver.py:117`), and .save/ directory for p2y (`yambo/artifact_resolver.py:18`) |
| `vasp` | `{}` (empty) | No VASP→W90/QMCPACK/Yambo bridge implemented. Future: vasp2wannier90 interface exists in the wild but is not wired in QMatSuite. |
| `abinit` | `{}` (empty) | ABINIT→Yambo bridge (a2y) exists in the wild but is not wired. No W90/QMCPACK bridge. |
| `cp2k` | `{}` (empty) | No bridge utilities implemented. |
| `siesta` | `{}` (empty) | No bridge utilities implemented. |
| `gpaw` | `{}` (empty) | No bridge utilities implemented. |
| `orca` | `{}` (empty) | Molecular code; postproc engines are periodic-only. |
| `gaussian` | `{}` (empty) | Molecular code; postproc engines are periodic-only. |
| `psi4` | `{}` (empty) | Molecular code. |
| `pyscf` | `{}` (empty) | Molecular code. |
| `xtb` | `{}` (empty) | Semi-empirical; no postproc bridge. |
| `lammps` | `{}` (empty) | Classical MD; no electronic structure for postproc. |

**Unknown / needs evidence** (future candidates, not currently wired):
- `vasp` → `w90`: VASP has a native Wannier90 interface (`LWANNIER90=.TRUE.`), but QMatSuite does not implement this bridge yet. When implemented, `w90` would be added to VASP's companion set.
- `abinit` → `yambo`: ABINIT's `a2y` converter exists upstream but is not wired. When wired, `yambo` would be added to ABINIT's companion set.
- `gpaw` → `w90`: GPAW has ASE-Wannier interface. Not wired.

**Conservative default**: If an engine's companion support is not proven by implemented code, `COMPANION_ENGINES` is empty. Adding a companion requires implementing the bridge utility and wiring the artifact resolver.

### 2.4 UNDECIDED / DECIDED State Machine

```
                              ┌─────────────────────────────────┐
                              │                                 │
    create_calculation()      │  UNDECIDED                      │
    ──────────────────────►   │  engine_family = null            │
                              │  allowed: postproc steps only    │
                              │                                 │
                              └──────────┬──────────────────────┘
                                         │
                                         │  user adds BASE gen step
                                         │  (scf, relax, md, etc.)
                                         │
                                         │  GUI forces engine_family choice
                                         │  + validates existing postproc
                                         │    steps against chosen family's
                                         │    COMPANION_ENGINES (Law EF9)
                                         │
                                         ▼
                              ┌─────────────────────────────────┐
                              │                                 │
                              │  DECIDED                        │
                              │  engine_family = F (immutable)  │
                              │  allowed: F's gen steps          │
                              │         + companion gen steps    │
                              │                                 │
                              └─────────────────────────────────┘
```

**Shortcut**: The GUI MAY offer engine family selection at calculation creation time (skipping UNDECIDED entirely). This is the common path for users who know what engine they want. In this case the calculation is created directly in DECIDED state.

**Duplicate-as-variant** (planned, not yet implemented): A future "Duplicate calculation" operation may create a new calculation from an existing DECIDED one, targeting a different engine family. This produces a new UNDECIDED or DECIDED calculation — it does NOT mutate the original.

---

## 3. Data Model

### 3.1 Calculation

```yaml
# calculation.yaml (SSOT)
meta:
  ulid: <ULID>
  name: <string>
  slug: <string>
  kind: calculation
mode: normal
working_dir: raw
engine_family: <string|null>     # null = UNDECIDED; non-null = DECIDED (immutable)
structure_kind: periodic|molecule # Optional hint for GUI filtering.
structure_ulid: <ULID|null>
steps:
  - step_ulid: <ULID>
    step_type_spec: <string>     # Always SPEC format: "{prefix}_{gen}"
```

`engine_family` is the SSOT for which base engine family governs this calculation. When `null`, the calculation is UNDECIDED and may only contain postprocessing steps.

`structure_kind` is an optional tag that informs the GUI which engines are appropriate to offer. It does NOT constrain engine_family at the model level — the user may override (e.g., using a periodic code for a molecule).

### 3.2 Step

```yaml
# step.yaml (SSOT)
meta:
  ulid: <ULID>
  name: <string>
  slug: <string>
  kind: step
step_type_spec: <string>         # SPEC format: "{prefix}_{gen}"
parameters: <dict>               # Engine-specific structure (see §3.4)
```

`step_type_spec` is the ground-truth step type. The gen type is derived via `gen_from(spec)` — never stored separately in step.yaml. DTO/RPC responses carry both `step_type_spec` and `step_type_gen` (the latter computed on read).

### 3.3 Engine Family Declaration

Each engine declares its identity and capabilities via the `EngineDriver` protocol (`core/driver_protocol.py`):

```python
class EngineDriver(Protocol):
    engine_family: str                        # Unique lowercase id ("qe", "vasp", ...)
    display_name: str                         # Human-readable ("Quantum ESPRESSO", "VASP", ...)
    PREFIX: str                               # Prefix for SPEC types ("qe", "vasp", ...)
    SUPPORTED_GEN_STEPS: frozenset[str]       # Gen steps this engine can materialize
    ENGINE_ROLE: str                          # "base" or "postprocessing"
    COMPANION_ENGINES: frozenset[str]         # (base only) Allowed postproc engine families
```

The SSOT for "what engines exist" is the set of drivers registered via `DriverRegistry.register()` at import time in `drivers/__init__.py`. No separate configuration file.

`ENGINE_ROLE` is `"base"` for engines that can produce ground state from scratch, `"postprocessing"` for engines that depend on upstream artifacts. This is a declaration, not inference.

`COMPANION_ENGINES` is only meaningful for base engines. It lists which postprocessing engine families are allowed as cross-engine steps in a DECIDED calculation governed by this base family. Postprocessing engines have `COMPANION_ENGINES = frozenset()`.

### 3.4 Parameter Structure by Engine

Parameters are stored as engine-specific dicts. There is no universal parameter schema — each engine family defines its own structure:

| Engine | Parameter Structure | Example |
|--------|-------------------|---------|
| QE | `{NAMELIST: {key: value}}` | `{"SYSTEM": {"ecutwfc": 30}, "CONTROL": {"calculation": "scf"}}` |
| VASP | `{key: value}` (flat INCAR) | `{"ENCUT": 400, "ISMEAR": 0, "SIGMA": 0.05}` |
| ORCA | `{key: value}` (mixed) | `{"functional": "B3LYP", "basis": "def2-SVP", "charge": 0}` |
| LAMMPS | `{key: value} + _commands` | `{"units": "metal", "pair_style": "eam/alloy", "_commands": [...]}` |
| Gaussian | `{key: value}` | `{"method": "B3LYP", "basis": "6-31G*", "opt": true}` |
| ABINIT | `{key: value}` (flat) | `{"ecut": 30, "nband": 8, "toldfe": "1.0d-8"}` |

The GUI does NOT impose a universal parameter schema. It renders parameters using engine-specific metadata (§6).

### 3.5 Managed (Runtime-Injected) Keys

Each engine may declare a set of **managed keys** — parameters that the runner injects or overrides at execution time. Users should see these in the GUI as read-only.

Current QE managed keys (hard-coded in `daemon/server.py:1751-1766`):
- `CONTROL.prefix` — runtime_overridden (set by runner)
- `CONTROL.outdir` — runtime_overridden (set by runner)
- `CONTROL.pseudo_dir` — runtime_overridden (set by runner)
- `CONTROL.calculation` — step_type_owned (derived from gen step type)

The generalized model: each engine driver declares its managed keys via a method on `BaseEngineDriver`:

```python
def get_managed_keys(self) -> dict[str, str]:
    """Return {param_path: reason} for runtime-managed parameters.

    reason is one of: "runtime_overridden", "step_type_owned"
    param_path is engine-specific (e.g., "CONTROL.prefix" for QE, "SYSTEM" for VASP).
    """
    return {}  # Default: no managed keys
```

---

## 4. Materialization Logic

### 4.1 Gen→Spec Mapping (DECIDED State)

Given a DECIDED calculation with `engine_family = F` and a user-selected gen step `g`:

```
materialize_decided(F, g) =
  if g ∈ F.SUPPORTED_GEN_STEPS:
    return "{F.PREFIX}_{g}"                        # Base engine's own step
  else:
    for C in F.COMPANION_ENGINES:
      let driver_C = DriverRegistry.get_driver(C)
      if g ∈ driver_C.SUPPORTED_GEN_STEPS:
        return "{driver_C.PREFIX}_{g}"             # Companion engine step
    raise UnsupportedStepError(F, g)               # Hard error, no fallback
```

Note: companion lookup iterates `COMPANION_ENGINES` in declaration order. Since Law EF8 guarantees postprocessing gen steps are globally unique, at most one companion will match.

### 4.2 Gen→Spec Mapping (UNDECIDED State)

Given an UNDECIDED calculation (`engine_family = null`) and a user-selected gen step `g`:

```
materialize_undecided(g) =
  let postproc_engines = {E : E.ENGINE_ROLE == "postprocessing"}
  let matching = {E ∈ postproc_engines : g ∈ E.SUPPORTED_GEN_STEPS}
  if |matching| == 1:
    let E = the single element of matching
    return "{E.PREFIX}_{g}"                        # Unique postproc step
  elif |matching| == 0:
    raise BaseStepRequiresFamilyError(g)           # This is a base step → force decision
  else:
    raise AmbiguousPostprocError(g, matching)      # Should not happen if EF8 holds
```

Law EF8 guarantees `|matching| ≤ 1` for all currently registered engines. If a future engine violates this, the gate test (§9) will catch it, and the ambiguous gen step will be disallowed in UNDECIDED state.

### 4.3 Uniqueness Proof

**Within DECIDED state**: For `g ∈ F.SUPPORTED_GEN_STEPS`, the mapping `g → "{F.PREFIX}_{g}"` is injective because PREFIX is constant and gen step names are distinct within the frozenset. For companion steps, Law EF8 guarantees no postprocessing gen step name appears in any base engine's gen steps, and no postprocessing gen step appears in two postprocessing engines. Therefore the companion lookup produces at most one match.

**Within UNDECIDED state**: Law EF8 guarantees every postprocessing gen step maps to exactly one engine globally. No ambiguity.

### 4.4 Unsupported Step (0-Mapping)

- **DECIDED, base gen step not in family**: Hard error. GUI prevents by only offering the family's gen steps.
- **DECIDED, postproc gen step not in companions**: Hard error. GUI prevents by only offering compatible companion steps.
- **UNDECIDED, base gen step requested**: Triggers UNDECIDED → DECIDED transition (Law EF7). User must select a family before the step is materialized.
- **UNDECIDED, unknown gen step**: Hard error.

### 4.5 Workflow Template Materialization

Workflow templates (`workflow/templates.py:_WORKFLOWS`) use gen step sequences:

```python
"dos": WorkflowTemplate(step_sequence=("scf", "nscf", "dos"))
```

Instantiating a workflow always requires DECIDED state (workflows contain base steps by definition). At instantiation (`WorkflowService.instantiate_workflow`):
1. Load `engine_family` from `calculation.yaml`. If UNDECIDED, force decision first.
2. For each gen step in sequence: call `materialize_decided(engine_family, gen)`.
3. If any step fails to materialize: raise error listing unsupported steps.
4. Create step documents with SPEC types.

**Workflow filtering** (§5.2): The GUI should only offer workflows whose entire step sequence can be materialized for the current `engine_family`. In UNDECIDED state, no workflow templates are offered (they all contain base steps).

---

## 5. GUI Routing

### 5.1 Calculation Init UI

**Current**: No engine selection. Defaults to QE (periodic) or PySCF (molecule).

**Target**: The "Create Calculation" dialog supports two paths:

**Path A — Decide now (common)**: User selects engine family at creation time.
1. User selects structure (optional).
2. GUI resolves `structure_kind` from selected structure (periodic/molecule/none).
3. GUI calls new RPC `list_engine_families()` → returns all registered base engines with metadata:
   ```
   [{engine_family: "qe", display_name: "Quantum ESPRESSO", engine_role: "base",
     supports_periodic: true, supports_molecule: false, companion_engines: ["w90","qmcpack","yambo"]}, ...]
   ```
4. GUI filters engines by compatibility with `structure_kind` (soft filter — user can override).
5. User selects engine family. Suggested default: QE for periodic, PySCF for molecule.
6. `create_calculation` RPC payload includes `engine_family: "qe"`.
7. Calculation is created in DECIDED state.

**Path B — Decide later (exploratory)**: User skips engine selection.
1. User creates calculation without selecting engine family.
2. `create_calculation` RPC payload has `engine_family: null`.
3. Calculation is created in UNDECIDED state.
4. Step palette shows only postprocessing steps (§5.2).
5. When user adds a base step (e.g., "scf"), GUI shows engine-family picker. On selection → UNDECIDED→DECIDED transition. If user cancels, step is not added.

**RPC change**: `create_calculation` payload accepts `engine_family: str | null`. The backend removes the `"pyscf" if molecule else "qe"` default logic. `null` is legal.

### 5.2 Step Palette and Workflow Templates

**Current**: Hard-coded QE step types in two dropdowns:
- `CalculationOverviewTab.tsx:453-460` (7 QE types)
- `CalculationListPanel.tsx:1344-1354` (10 QE types)

**Target**: Dynamic step palette with two sections:

**DECIDED calculation**: Step palette shows:
1. **Base steps**: From `engine_family`'s `SUPPORTED_GEN_STEPS`, with display names.
2. **Companion steps**: From each engine in `COMPANION_ENGINES`, their `SUPPORTED_GEN_STEPS`, grouped by companion engine with a section header.
3. **Workflow templates**: Only those whose full step sequence can be materialized for the current family.

**UNDECIDED calculation**: Step palette shows:
1. **Postprocessing steps only**: Gen steps from all postprocessing engines, grouped by engine.
2. **No base steps** (adding one would trigger the decision prompt).
3. **No workflow templates** (they all contain base steps).

Backend implementation: `get_supported_generalized_steps(engine_family)` already exists at `workflow/generalized_steps.py:210`. Extend with a new RPC `list_step_palette(engine_family | null)` that returns the full palette structure including companion steps and role annotations.

### 5.3 Parameter Editor Abstraction

**Current**: `stepTypeToModule()` maps to QE modules. Returns `null` for non-QE → blank parameter UI. `list_qe_ui_parameters` RPC fetches QE-specific curated parameters. `QEParameterBrowserPanel` browses QE metadata only.

**Target**: A two-tier parameter editor that works for all engines.

#### Tier 1: Guided Parameter Editor

The guided editor shows curated, important parameters for the current step type. Each engine provides this via its metadata catalog.

New RPC: `list_engine_ui_parameters(engine_family, step_type_gen)`:
- Returns `[{key, label, type, unit, description, importance, options, section?, is_managed, managed_reason}]`
- Backend dispatches to engine-specific metadata: `drivers/<engine>/data/<engine>_metadata.py`
- QE returns its existing `get_ui_parameters(module, step_type_gen)` output
- VASP returns curated params from `vasp_incar_tags.json` filtered by category
- ORCA returns curated params from `orca_keywords.json`
- Engines without curated UI params return `[]` (falls through to raw editor)

GUI rendering:
- Sections/groups come from the metadata (QE: namelists, VASP: categories, ORCA: keyword groups)
- Each parameter renders as: label + input + unit + description tooltip
- Managed parameters render as read-only with reason badge

#### Tier 2: Raw Parameter Override

Below the guided editor, the **Active Parameters panel** (already exists) shows all parameters from `step.yaml` as key-value pairs. Users can:
- Add arbitrary parameters not in the guided list
- Edit any non-managed parameter
- Remove parameters

This is the escape hatch. It operates on the raw `parameters` dict in step.yaml, agnostic to engine schema.

**No engine-specific conditional logic in the GUI component**. The guided editor receives a generic `UIParameter[]` list from the RPC and renders it uniformly. Engine differences are encoded in the metadata, not in the renderer.

#### QE-Specific Panels Become Generic

| Current QE-Specific | Generalized Replacement |
|---------------------|------------------------|
| `stepTypeToModule()` in StepDetailPanel | Removed. Engine metadata provides parameter grouping. |
| `LEGACY_EDITABLE_PARAMS` dict | Removed. Replaced by `list_engine_ui_parameters` RPC. |
| `list_qe_ui_parameters` RPC | Deprecated. Replaced by `list_engine_ui_parameters`. |
| `QEParameterBrowserPanel` | Becomes `EngineParameterBrowserPanel` — routes on `engine_family`. |
| `list_qe_parameter_metadata` RPC | Replaced by `list_engine_parameter_metadata(engine_family, ...)`. |
| `useQEParameterMetadata` hook | Becomes `useEngineParameterMetadata(engine_family)`. |

### 5.4 Managed / Injected Params Display

**Current**: Hard-coded in `daemon/server.py:1751-1766` — checks for `section == "CONTROL"` and `param in ("prefix", "outdir", "pseudo_dir", "calculation")`.

**Target**: Each engine driver declares managed keys via `get_managed_keys()`. The parameter metadata RPC annotates parameters with `is_managed` and `managed_reason` based on the driver's declaration, not hard-coded QE checks.

GUI renders managed parameters as:
- Grayed-out / read-only input
- Badge: "Set by runner" (runtime_overridden) or "Set by step type" (step_type_owned)
- Tooltip explaining what the runner does with this key

### 5.5 Engine Detection and Configuration

**Current**: QE-only RPCs (`detect_qe`, `list_qe_engines`, `set_qe_engine`).

**Target**: Generic RPCs:
- `detect_engine(engine_family)` → returns binary paths, version, status
- `configure_engine(engine_family, config)` → sets binary path, etc.

Backend dispatches to driver-specific detection logic. Each driver optionally implements detection (many engines have no detection — the user just provides a path).

Settings panel shows a section per detected/configured engine, not just QE.

---

## 6. Metadata System

### 6.1 Centralized Storage

Each engine's parameter metadata lives at `drivers/<engine>/data/<engine>_tags.json` (or equivalent). This is already the pattern for all B1-complete engines:

| Engine | Metadata File | Entry Count |
|--------|--------------|-------------|
| QE | `data/qe_module_parameters.json` + `qe_ui_parameters.json` | ~500+ params across modules |
| VASP | `data/vasp_incar_tags.json` | 232 tags |
| ORCA | `data/orca_keywords.json` | 120+ keywords |
| LAMMPS | `data/lammps_commands.json` | 114 commands |
| Gaussian | `data/gaussian_route_keywords.json` | 130 keywords |
| ABINIT | `data/abinit_tags.json` | 170+ tags |
| CP2K | `data/cp2k_tags.json` | 215 tags |
| QMCPACK | `data/qmcpack_tags.json` | 65 tags |

### 6.2 Access Layer

Each engine has `data/<engine>_metadata.py` with a common pattern:

```python
# Common API (already implemented by all B1 engines):
get_tag_info(name) -> dict | None
list_tags(category=None) -> list[str]
list_categories() -> list[str]
validate_params(params) -> list[Diagnostic]
get_tag_type(name) -> str | None
get_tag_default(name) -> Any
```

The new generic RPC dispatches to the engine's metadata module:

```python
def list_engine_ui_parameters(engine_family: str, step_type_gen: str) -> list[dict]:
    driver = DriverRegistry.get_driver(engine_family)
    if hasattr(driver, 'get_ui_parameters'):
        return driver.get_ui_parameters(step_type_gen)
    return []  # Engine has no curated UI params
```

### 6.3 Versioning Strategy

Metadata JSON files are committed to the repo alongside the driver code. Versioning is implicit in git history. Hot-reload is supported for development via `QV_<ENGINE>_METADATA_HOT_RELOAD=1` env vars.

No separate metadata version number or schema migration is needed. The metadata is consumed by the GUI via RPCs, which abstract the JSON structure. If the JSON format changes, only the access layer (`<engine>_metadata.py`) changes — the RPC contract is stable.

### 6.4 GUI Search/Browse

The `EngineParameterBrowserPanel` (replacement for `QEParameterBrowserPanel`) provides:
1. Engine selector (only for browsing — step editing always knows the engine)
2. Category/section selector (engine-specific groupings)
3. Parameter table with columns: name, type, default, description
4. Global search across all parameters for the selected engine

RPC: `list_engine_parameter_metadata(engine_family, operation, ...)`:
- `operation: "list_categories"` → returns category names
- `operation: "list_parameters"` → returns params for a category, annotated with `is_managed`
- `operation: "search"` → full-text search across params

### 6.5 Raw Override Coexistence

Users can always add arbitrary parameters via the Active Parameters panel. These go directly into `step.yaml:parameters` without validation. The guided editor and the raw editor operate on the same underlying dict. They are not separate storage — the guided editor is a structured view of the same data.

When a user adds a parameter via raw override that conflicts with a guided parameter, the raw value wins (it's the same dict). The guided editor shows the current value from the dict.

---

## 7. Demo System

### 7.1 Standard

A **verified demo** is a project snapshot that:
1. Has been materialized into a working project directory.
2. Has been run to completion (or explicitly marked as "structural only" if the engine binary is not freely available).
3. Contains reference comparison artifacts from the actual run.
4. Passes all demo integrity gates (Law EF6).
5. Is always in DECIDED state (`engine_family` is non-null).

Verified demos are product assets (shown in the demo gallery) and regression assets (tested in CI).

**Reference artifact format**: Reference artifacts (energies, band structures, DOS, etc.) are currently stored as engine-specific JSON files alongside the snapshot. The long-term direction is toward engine-agnostic canonical primitives (the AnalysisObject → Primitives system), but the exact artifact schema is not locked by this spec. What is locked: reference artifacts live in-repo under `resources/demo_projects/` alongside their snapshot, and must be curated (not raw engine output).

### 7.2 Directory Layout

```
resources/demo_projects/
  <demo_id>.yml                    # Project snapshot (YAML)
  <demo_id>.<analysis>.json        # Reference artifacts (optional, per analysis type)
  <demo_id>_README.md              # Human-readable explanation (optional)
```

Demo IDs are lowercase, underscore-separated, descriptive: `si_scf`, `water_orca_scf`, `lih_qmcpack_vmc`.

### 7.3 Snapshot Schema

Every demo snapshot MUST contain:

```yaml
version: 1
project:
  meta: {ulid, name, slug, path: ".", kind: project}
  settings: {}
structures:
  - meta: {ulid, name, slug, path, kind: structure}
    data: <pymatgen Structure or Molecule dict>
calculations:
  - meta: {ulid, name, slug, path, kind: calculation}
    mode: normal
    working_dir: raw
    engine_family: <string>                # REQUIRED — demos are always DECIDED (Law EF6)
    structure_kind: periodic|molecule      # REQUIRED
    structure_ulid: <ULID>
    steps:
      - meta: {name, slug, path, kind: step, ulid}
        parameters: <dict>
        step_type_spec: <string>           # MUST match engine_family or companion allowlist
meta:
  ulid: <demo_id>
  title: <string>                          # Human-readable title
  subtitle: <string>                       # Workflow description
  tags: [<string>, ...]                    # Category tags
  difficulty: beginner|intermediate|advanced
  recommended_analysis: <string|null>      # Default analysis view
  reference_artifacts:                     # Map of analysis type → artifact filename
    scf: <demo_id>.scf.json
```

### 7.4 GUI Consumption

The demo gallery (already engine-agnostic in `DemoGalleryPanel.tsx`) works as:
1. `list_demo_projects` RPC scans `resources/demo_projects/*.yml`
2. GUI renders cards with title, subtitle, tags, difficulty, engine badge
3. User clicks "Create Project" → `create_demo_project(target_dir, name, demo_id)`
4. Backend materializes snapshot into a full SSOT project directory
5. GUI loads the new project

**Engine badge**: The gallery card should display the `engine_family` from the demo's calculation metadata. This helps users find demos for specific engines.

**Reference comparison**: After running a demo, the GUI can compare actual results against reference artifacts. The comparison UI and the canonical primitive format are future work — this spec does not lock the artifact schema beyond requiring that artifacts be curated and stored in-repo.

### 7.5 Generator Organization

**Current state** (`tools/` directory): Scattered generators with no clear verified/experimental separation:
- `generate_demo_snapshots.py` — main QE orchestrator
- `generate_orca_demos.py` — ORCA generator (produces broken demos)
- `generate_pyscf_demo.py` — PySCF generator
- `generate_wannier90_demo.py`, `generate_wannier90_demos.py` — W90 generators (duplicate)
- `regenerate_si_bands_demo.py` — single-demo regenerator
- `verify_demos.py` — validator
- `migrate_demo_projects.py` — migration tool

**Target layout**:

```
tools/
  demo_generators/                         # Canonical folder for ALL demo generators
    README.md                              # Generator conventions and instructions
    verified/                              # Generators for verified (gallery-ready) demos
      generate_qe_demos.py                 # QE demos (formerly generate_demo_snapshots.py)
      generate_orca_demos.py               # ORCA demos (fixed)
      generate_pyscf_demos.py              # PySCF demos
      generate_wannier90_demos.py          # W90 demos
      generate_vasp_demos.py               # VASP demos (new)
      generate_lammps_demos.py             # LAMMPS demos (new)
      generate_gaussian_demos.py           # Gaussian demos (new)
    experimental/                          # Generators under development (not yet verified)
      generate_qmcpack_demos.py
      generate_abinit_demos.py
      generate_cp2k_demos.py
    lib/                                   # Shared generator utilities
      snapshot_builder.py                  # Common snapshot construction
      reference_extractor.py               # Extract reference artifacts from run outputs
    verify_demos.py                        # Demo validation (all engines)
    migrate_demo_projects.py               # Migration tool (schema updates)
```

**Rules**:
- A generator in `verified/` MUST produce demos that pass the demo integrity gate (Law EF6).
- A generator in `experimental/` MAY produce demos that are structurally correct but not run-validated.
- Moving a generator from `experimental/` to `verified/` requires run validation evidence.
- `verify_demos.py` checks all demos in `resources/demo_projects/` regardless of which generator produced them.

---

## 8. Migration Plan

### Phase 1: Fix Data Integrity + UNDECIDED/DECIDED Foundation (no GUI changes)

**Goal**: All demos comply with Laws EF1-EF9. Backend supports UNDECIDED/DECIDED model. No GUI changes.

1. **Fix ORCA demo `step_type_spec` values**: Change `qe_scf` → `orca_scf`, `pyscf_td` → `orca_td` in all 3 ORCA demos.
2. **Add `engine_family` to all demos**: Add explicit `engine_family: qe` to the 14 QE demos, `engine_family: qe` to the 3 W90 demos (primary family is QE; W90 steps are companions), `engine_family: pyscf` to the PySCF demo.
3. **Add `structure_kind` to all demos** that lack it.
4. **Add `ENGINE_ROLE` and `COMPANION_ENGINES`** to all 15 driver classes. Wire into `DriverRegistry`.
5. **Add demo integrity gate test**: `tests/gates/test_demo_integrity.py` — validates Law EF6 for all snapshots.
6. **Add postproc uniqueness gate test**: `tests/gates/test_postproc_gen_uniqueness.py` — validates Law EF8 at CI time.
7. **Add companion completeness gate test**: `tests/gates/test_companion_completeness.py` — validates that every demo's cross-engine steps are in the declared companion allowlist.
8. **Remove silent QE fallbacks** in `service.py` (4 locations). Replace with hard errors or explicit UNDECIDED logic.
9. **Allow `engine_family: null`** in `calculation.yaml` model. Add validation: if `engine_family` is null and any step has a base-engine prefix, raise error.

**Cut-line**: Only `resources/demo_projects/*.yml`, `drivers/*/driver.py` (declarations only), `service.py`, new gate tests. Zero GUI changes.

### Phase 2: Generic Backend RPCs (no GUI changes yet)

**Goal**: New engine-agnostic RPCs exist alongside the QE-specific ones.

1. **Add `list_engine_families` RPC**: Returns all registered engines with metadata including `engine_role` and `companion_engines`.
2. **Add `list_step_palette(engine_family | null)` RPC**: Returns the full step palette structure (base + companion steps in DECIDED; postproc-only in UNDECIDED).
3. **Add `list_engine_ui_parameters(engine_family, step_type_gen)` RPC**: Dispatches to engine metadata.
4. **Add `list_engine_parameter_metadata(engine_family, operation, ...)` RPC**: Generic parameter browser.
5. **Add `get_managed_keys(engine_family)` to driver protocol**: Each engine declares its managed keys.
6. **Update `create_calculation` RPC**: Accept `engine_family: str | null`. Backend no longer infers.
7. **Add `set_engine_family(calculation, engine_family)` RPC**: UNDECIDED→DECIDED transition with Law EF9 validation.

**Cut-line**: New RPCs in `daemon/server.py`, new fields on `BaseEngineDriver`, updated `service.py`. QE-specific RPCs remain but are deprecated. GUI still calls old RPCs — nothing breaks.

### Phase 3: GUI Generalization

**Goal**: GUI uses the new generic RPCs. QE-specific code removed.

3a. **Calculation creation dialog**: Add engine family dropdown (Path A) and "Decide later" option (Path B). Call `list_engine_families` for options. Pass `engine_family` in `create_calculation` payload.

3b. **Step palette**: Replace hard-coded dropdowns with dynamic `list_step_palette` call. Both `CalculationOverviewTab.tsx:453-460` and `CalculationListPanel.tsx:1344-1354`. Show base/companion sections for DECIDED; postproc-only for UNDECIDED. Show engine-family picker prompt when user selects a base step in UNDECIDED state.

3c. **Parameter editor**: Replace `stepTypeToModule()` and `LEGACY_EDITABLE_PARAMS` with `list_engine_ui_parameters` call. Remove QE module concept from StepDetailPanel.

3d. **Parameter browser**: Rename `QEParameterBrowserPanel` to `EngineParameterBrowserPanel`. Route on `engine_family`. Replace `list_qe_parameter_metadata` calls with `list_engine_parameter_metadata`.

3e. **Managed keys**: Replace hard-coded `CONTROL.prefix/outdir/pseudo_dir` checks with `get_managed_keys(engine_family)` dispatch.

3f. **Settings panel**: Replace QE-only detection with per-engine detection sections.

3g. **Delete deprecated QE RPCs**: Remove `list_qe_ui_parameters`, `list_qe_parameter_metadata`, `detect_qe`, `list_qe_engines`, `set_qe_engine`, `import_step_from_qe_input`.

**Sequencing**: 3a through 3f can be done incrementally. At each sub-step, the existing QE UX continues to work — it just routes through the generic path instead of the QE-specific one. Step 3g (deletion) happens last, only after all GUI code is migrated.

### Phase 4: Demo Expansion

**Goal**: Demo gallery covers B1-complete engines beyond QE.

1. **Create VASP demos**: At least `si_vasp_scf`, `si_vasp_relax` (2 demos).
2. **Create LAMMPS demos**: At least `lj_lammps_md`, `eam_lammps_relax` (2 demos).
3. **Create Gaussian demos**: At least `water_gaussian_sp`, `water_gaussian_opt` (2 demos).
4. **Reorganize tools/**: Move generators to `tools/demo_generators/` structure (§7.5).
5. **Create QMCPACK demo**: At least `he_qmcpack_vmc` (1 demo, if binary available for validation).

---

## 9. Acceptance Criteria

### Gate Tests (required before "done")

| Test | What It Validates | Law |
|------|------------------|-----|
| `tests/gates/test_demo_integrity.py` | All demos have correct `engine_family`, `step_type_spec` prefix matches family or companion allowlist, `structure_kind` present | EF6 |
| `tests/gates/test_postproc_gen_uniqueness.py` | No postprocessing gen step name appears in >1 postproc engine's `SUPPORTED_GEN_STEPS`, and no postproc gen step appears in any base engine's `SUPPORTED_GEN_STEPS` | EF8 |
| `tests/gates/test_companion_completeness.py` | Every engine with `ENGINE_ROLE="postprocessing"` appears in at least one base engine's `COMPANION_ENGINES`. Every base engine's `COMPANION_ENGINES` contains only engines with `ENGINE_ROLE="postprocessing"` | EF3, EF9 |
| `tests/gates/test_no_qe_special_case.py` | No QE-specific RPC names in GUI TypeScript, no `"qe"` literal defaults in service.py | G6 |
| `tests/gates/test_engine_family_lifecycle.py` | `create_calculation` with `engine_family=null` succeeds; adding base step to UNDECIDED raises if no family chosen; DECIDED→DECIDED(other) is rejected; DECIDED→UNDECIDED is rejected | EF1, EF4, EF7 |
| `tests/gates/test_decided_companion_validation.py` | UNDECIDED→DECIDED transition rejects if existing postproc steps are not in chosen family's companion set | EF9 |
| Existing `tests/gates/test_no_sensitive_paths.py` | No real paths in demos | S1 |

### Functional Criteria

| Criterion | Definition of Done |
|-----------|-------------------|
| Multi-engine calc creation | User creates calculations for QE, VASP, ORCA, LAMMPS, PySCF via GUI — all work |
| UNDECIDED calc creation | User creates a calculation without engine family, adds a W90 step, then adds an SCF step (triggers family selection), selects QE — calculation becomes DECIDED with both steps |
| Dynamic step palette | Step dropdown shows different options for QE vs VASP vs ORCA calculations |
| Companion steps in palette | QE DECIDED calculation's palette includes W90/QMCPACK/Yambo steps in a companion section |
| Parameter editing for all B1 engines | Guided editor shows curated params for QE, VASP, ORCA, LAMMPS, Gaussian, ABINIT, CP2K, QMCPACK |
| Raw override works | User can add arbitrary key-value params for any engine |
| Demo gallery multi-engine | Gallery shows demos for at least 4 different engines |
| No QE literals in GUI | `grep -r "qe_" gui/src/` returns zero hits (excluding comments/docs) |
| No QE RPCs in daemon | `detect_qe`, `list_qe_engines`, `list_qe_ui_parameters`, `list_qe_parameter_metadata` removed |
| Managed keys for non-QE | VASP managed keys, ORCA managed keys (if any) display correctly |

### What "Done" Means

The refactor is complete when:
1. All gate tests pass.
2. All functional criteria are met.
3. A new user can go from demo gallery → create project → add steps → edit parameters → run for at least 3 different engine families, without encountering any QE-specific UI or error.
4. The existing QE workflow (the current primary path) works identically — no regression.
5. An UNDECIDED → DECIDED lifecycle works end-to-end: create empty calc → add postproc step → add base step → pick family → edit params → run.
