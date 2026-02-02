# Step Type GEN/SPEC Constitution

**Status**: Final  
**Version**: 1.0  
**Location**: `src/quantumvitas/workflow/gen_steps.py` (GenStepRegistry), `src/quantumvitas/drivers/*/driver.py` (engine recipes)

---

## 1. Goal

The repository MUST maintain exactly two step type namespaces:

- **`step_type_gen`**: Intent/workflow/preset/paramspace/UI layer (engine-agnostic)
- **`step_type_spec`**: Execution/persistence/dispatch/step.yaml layer (engine-specific)

All other step type identity concepts are **FORBIDDEN**:
- Legacy "public" / "machine" / "generalized" / "enum" / "alias" / bare `step_type` fields
- Third namespaces (e.g., `GEN_*` format with underscores)
- Hardcoded mapping tables that duplicate SSOT

---

## 2. Representation

### 2.1 String Format

Both `step_type_gen` and `step_type_spec` are **plain lowercase strings without spaces**.

Examples:
- `step_type_gen`: `"scf"`, `"relax"`, `"wannierprep"`, `"bandspw"`
- `step_type_spec`: `"qe_scf"`, `"vasp_relax"`, `"w90_wannierprep"`, `"qe_bandspw"`

### 2.2 SSOT Sources

- **`step_type_gen` values**: MUST come from `GenStepRegistry.GEN_STEPS` (SSOT)
  - Location: `src/quantumvitas/workflow/gen_steps.py`
  - All valid gen step names are declared in this frozen set

- **`engine_prefix`**: MUST come from engine recipe `PREFIX` class attribute (SSOT)
  - Location: `src/quantumvitas/drivers/*/driver.py`
  - Example: `QEDriver.PREFIX = "qe"`

- **`supported_gen_steps`**: MUST come from engine recipe `SUPPORTED_GEN_STEPS` class attribute (SSOT)
  - Location: `src/quantumvitas/drivers/*/driver.py`
  - Example: `QEDriver.SUPPORTED_GEN_STEPS = frozenset({"scf", "nscf", ...})`
  - MUST satisfy: `supported_gen_steps ⊆ GenStepRegistry.GEN_STEPS` (enforced by gate)

---

## 3. Derivation Rule (Core Law)

The **only valid derivation** from gen to spec is:

```
step_type_spec = join(engine_prefix, step_type_gen)
```

Where `join(prefix, gen)` is implemented as `f"{prefix}_{gen}"`.

**Reverse derivation** (spec → gen) MUST use `split(spec)`, which returns `(prefix, gen)` by splitting on the first underscore.

**Canonical Implementation**: These operations MUST be implemented using:
- `spec_from(prefix, gen)` from `src/quantumvitas/workflow/step_type_convert.py` for join
- `gen_from(spec)` from the same module for split (returns gen only)
- `prefix_from(spec)` from the same module for split (returns prefix only)

**No exceptions**. No special cases. No overrides. If an engine needs a different mapping, the gen step name in `GenStepRegistry` MUST be chosen to make the derivation valid.

### 3.1 Conversion API Law (Repo-Wide Ban)

**The entire repository is ONLY allowed to perform step type conversions via the canonical functions above.**

**FORBIDDEN everywhere else**:
- `spec.split("_", 1)` or any manual underscore parsing
- `f"{prefix}_{gen}"` or any manual concatenation for step type derivation
- `startswith(prefix+"_")`, strip-prefix helpers, custom `is_spec` checks that reimplement the underscore rule
- Any ad-hoc parsing or string manipulation for step type conversion

**Helper predicates** (e.g., `is_step_type_spec(s)`, `is_step_type_gen(s)`) MAY exist, but:
- MUST be implemented internally in terms of the canonical join/split + underscore rule
- MUST NOT be reimplemented elsewhere
- MUST call the canonical functions, not duplicate their logic

**Rationale**: Scattered ad-hoc parsing creates inconsistency and violates the single source of truth. All conversion logic MUST flow through the canonical functions.

---

## 4. Execution Layering (Route A - Required)

### 4.1 Persistence SSOT

**`step.yaml` files store ONLY `step_type_spec`** (SSOT for execution).

Runner/dispatch/driver_registry external lookup keys remain SPEC-centric because `step.yaml` provides SPEC.

### 4.2 Engine Recipe Structure

**Engine recipes MUST NOT maintain a spec→handler/executable mapping table** (avoids "second truth").

Engine recipes store only:
- `engine_prefix` (required, from `PREFIX` class attribute)
- `supported_gen_steps` (subset of global `GenStepRegistry.GEN_STEPS`)
- `handlers_by_gen` / `executables_by_gen` (keys are GEN only, not SPEC)

### 4.3 Execution Conversion Choke Point

**Runner/dispatch performs exactly ONE spec→(prefix, gen) "unpack" at a SINGLE choke point** before recipe lookup:

```
(prefix, gen) = split(spec)  # Canonical split function
recipe = recipe_registry[prefix]
handler/executable = recipe.handlers_by_gen[gen]
```

**This is the ONLY permitted place where spec→gen conversion happens in execution.** It MUST NOT spread to other execution-layer code.

**Rationale**: Centralizing the conversion at a single choke point ensures consistency and prevents drift. Execution layer code after this point uses GEN keys for recipe lookup, but the input (from `step.yaml`) remains SPEC.

### 4.4 Driver Registry Responsibility

- **DriverRegistry/runner accepts SPEC inputs** (because `step.yaml` SSOT is SPEC)
- **Engine recipes accept GEN keys internally** (handlers/executables keyed by GEN)
- **No per-driver "override maps" or special-case spec↔gen mapping tables are allowed**

Any such overrides violate the derived law and MUST be deleted (no compatibility layer).

### 4.5 Conversion Layering (Architecture Decision)

**Default rule**: Daemon/CLI MUST NOT perform gen/spec conversions.

**Data flow**:
- **UI → API**: Sends `step_type_gen`
- **Kernel/API**: Creates step by deriving `step_type_spec` using calculation engine prefix and persists ONLY `step_type_spec` in `step.yaml`
- **Step/DTO objects**: MAY carry both `step_type_gen` + `step_type_spec` (to avoid daemon/CLI doing conversions)
- **Runner**: Reads `step_type_spec` from `step.yaml` and performs exactly one `split(spec)` at a single choke point to `(prefix, gen)` for recipe lookup

**Rationale**: Centralizing conversion at kernel/API boundaries prevents daemon/CLI from needing conversion logic and ensures consistency.

---

## 5. Underscore Ban (Disambiguation Law)

To enable unambiguous string classification:

- **`engine_prefix` MUST NOT contain `_` (underscore)**
- **`step_type_gen` MUST NOT contain `_` (underscore)**

**Consequence**: If a string contains `_`, it is spec; otherwise, it is gen.

This is a **property of the system**, not a recommendation. Code MUST NOT pass ambiguous strings that violate this rule.

**Examples**:
- ✅ Valid gen: `"scf"`, `"relax"`, `"wannierprep"`, `"bandspw"`
- ❌ Invalid gen: `"w90_preproc"`, `"bands_post"` (contains underscore)
- ✅ Valid spec: `"qe_scf"`, `"w90_wannierprep"` (contains exactly one underscore)
- ❌ Invalid spec: `"qe_vc_relax"` (contains two underscores; violates §8 - VC is a parameter, not a step type)

---

## 6. Mapping Cardinality Law

For a given engine:

- **gen → spec**: 0 or 1
  - 0 means the engine does not support that gen step
  - 1 means exactly one spec step exists for that gen step
  - Example: `"scf"` → `"qe_scf"` (1), `"scf"` → `"pyscf_scf"` (1), `"scf"` → `"vasp_scf"` (1)

- **spec → gen**: exactly 1
  - Every spec step MUST map to exactly one gen step (by splitting on first underscore)
  - Example: `"qe_scf"` → `"scf"` (1), `"w90_wannierprep"` → `"wannierprep"` (1)

**Zero-mapping semantics**: If an engine's `SUPPORTED_GEN_STEPS` omits a gen step, that gen step has no spec step for that engine. This is allowed and represents unsupported functionality (e.g., VASP does not have a separate DOS step; DOS is integrated into NSCF output).

---

## 7. Alias Policy (Hard Ban)

**No alias step type values anywhere in system state.**

The following legacy values are **FORBIDDEN** as step type values in code, tests, tools, docs, persisted YAML, and API responses:

- `"w90_preproc"` → MUST use `"wannierprep"` (gen) / `"w90_wannierprep"` (spec)
- `"w90_run"` → MUST use `"wannier"` (gen) / `"w90_wannier"` (spec)

**Note on executable names**: The string `"pw2wannier90"` MAY appear as an executable name (e.g., `"pw2wannier90.x"`), but MUST NOT appear as a step type value. The step type is `"pw2wannier"` (gen) / `"qe_pw2wannier"` (spec).

**Enforcement**: Gate tests MUST scan for these banned values in step type contexts (not in executable names, file paths, or comments).

---

## 8. VC/OPT are Parameters, Never Step Types (Hard Ban)

**`step_type_gen` MUST NOT encode cell/volume control, optimization style, or MD ensemble style.**

The allowed GEN step types include `"relax"` and `"md"` (and any other already-registered GEN steps), but it is **FORBIDDEN** to create GEN step types:
- `"vcrelax"`, `"vcmd"`, `"opt"`, `"geomopt"`, `"geomeopt"`, `"vc-relax"`, `"vc-md"`, `"vc_relax"`, `"vc_md"`, or any `vc-*` / `*_md` variants

**VC vs non-VC is expressed ONLY via step parameters** (engine parameters), never via step types.

**Examples**:
- QE `CONTROL.calculation` may be `"relax"` / `"vc-relax"` / `"md"` / `"vc-md"` etc — but `step_type_gen` remains `"relax"` or `"md"`.
- ORCA: Even if ORCA manual says `"opt"`, QMatSuite step types are `step_type_gen = "relax"` and `step_type_spec = "orca_relax"`. The token `"opt"` is never a step type value.

**Consequently**, SPEC step types like `"qe_vc_relax"`, `"qe_vc_md"` (and any `engine_prefix + vcrelax/vcmd` variants) are **FORBIDDEN** because they violate the derivation rule `spec = {engine_prefix}_{step_type_gen}`.

**Any third-namespace enums or symbols** like `"GEN_VC_*"` are **FORBIDDEN**.

**There is NO alias / compatibility mapping layer for step types anywhere in mainline code.**

**Enforcement**: Gate tests MUST scan for these banned values in step type contexts and fail if found.

---

## 9. Key Semantic Decisions

### 9.1 Relax Unification

**Gen layer**: There is only one gen step: `"relax"`.

Engine-specific parameters (e.g., `calculation = "vc-relax"` in QE, `ISIF = 3` in VASP) are stored in step parameters, not in step type names.

**Spec layer**: All engines derive to `{prefix}_relax`:
- `"qe_relax"` (QE)
- `"vasp_relax"` (VASP)
- `"orca_relax"` (ORCA)
- `"cp2k_relax"` (CP2K)
- `"lammps_relax"` (LAMMPS)
- `"pyscf_relax"` (PySCF)

**ORCA naming clarification**: Even if ORCA documentation calls geometry optimization `"opt"`, QMatSuite step types are still:
- `step_type_gen = "relax"`
- `step_type_spec = "orca_relax"`

The token `"opt"` may appear only as human-facing documentation/log/executable context, never as a step type value or alias.

**Legacy aliases FORBIDDEN**: `"vc-relax"`, `"opt"`, `"geomopt"` MUST NOT appear as step type values. They are parameter values only.

### 9.2 Wannier Workflow Naming

**Gen steps** (in execution order):
1. `"wannierprep"` → Wannier90 preprocessing (generate .nnkp)
2. `"pw2wannier"` → QE to Wannier90 interface (compute overlaps)
3. `"wannier"` → Wannier90 MLWF optimization

**Spec steps** (derived by prefix + gen):
- `"w90_wannierprep"` (Wannier90 engine)
- `"qe_pw2wannier"` (QE engine)
- `"w90_wannier"` (Wannier90 engine)

**Note**: `"pw2wannier"` is a QE step (uses `pw2wannier90.x`), so its spec is `"qe_pw2wannier"`, not `"w90_pw2wannier"`.

### 9.3 Bands Semantics

Two distinct gen steps exist:

- **`"bandspw"`**: Compute k-path eigenvalues (engine run)
  - This is the "compute" step

- **`"bands"`**: Post-processing step
  - This is the "postprocess" step

**Mapping cardinality**:

- **QE has both**:
  - `"qe_bandspw"` (compute) and `"qe_bands"` (postprocess)

- **VASP has `"vasp_bandspw"` ONLY**:
  - `"vasp_bandspw"` exists
  - `"vasp_bands"` MUST NOT exist (gen `"bands"` maps to 0 spec steps for VASP; gen→spec=0 is valid)

**Naming note**: The gen step for computation is `"bandspw"` (not `"bands_pw"` or `"bands-pw"`) to avoid underscores.

---

## 10. UI vs Persistence Rule

### 10.1 Output Naming

**UI and user-facing filenames use GEN names by default** (e.g., `relax.out`, `wannierprep.out`).

**Persisted YAML/dispatch SSOT uses SPEC names** (e.g., `step_type_spec="qe_relax"` in `step.yaml`).

### 10.2 UI/User-Facing Layer

**MUST use gen names**:
- User-visible step type labels
- Output filenames (e.g., `relax.out`, `wannierprep.out`)
- Workflow template step sequences
- Preset variant `applies_to_step_types` declarations
- ParamSpace dimension declarations

### 10.3 Persistence/Execution Layer

**MUST use spec names** (SSOT):
- `step.yaml` files: `step_type_spec` field
- Execution dispatch/routing
- Calculation step entries (if used for execution routing)
- RPC payloads that specify engine context

**Conversion**: Code that bridges UI and persistence MUST convert gen → spec before writing to disk, and spec → gen before displaying to users. Conversions MUST use canonical `join()`/`split()` functions (§3.1).

---

## 11. "No Bare step_type" Rule

**The repository MUST NOT have any DTO/dataclass fields or function parameters named `step_type` (bare).**

Everything MUST be explicitly:
- `step_type_gen` if engine/persistence info is not required (workflow/preset/UI layer)
- `step_type_spec` if engine/persistence info is required (execution/persistence layer)

**Rationale**: Bare `step_type` is ambiguous and leads to drift (is it gen or spec?).

**Enforcement**: Gate tests MUST scan for bare `step_type` field/parameter names and fail if found.

---

## 12. SSOT Boundaries

### 12.1 Gen Step Registry

**`GenStepRegistry.GEN_STEPS`** (`src/quantumvitas/workflow/gen_steps.py`) is the **only SSOT** of valid gen step names.

No other code, test, or tool MAY maintain a list of valid gen steps. All validation MUST query `GenStepRegistry.is_valid(gen)`.

### 12.2 Engine Recipe Declarations

**Engine recipe classes** (`src/quantumvitas/drivers/*/driver.py`) are the **only SSOT** of:
- `engine_prefix` (via `PREFIX` class attribute)
- `supported_gen_steps` (via `SUPPORTED_GEN_STEPS` class attribute)

No other code MAY hardcode engine prefixes or supported step lists.

### 12.3 Derived Mappings

**Mapping tables** (e.g., materialization maps) MAY exist **only if** they are **purely derived** from:
- `engine_prefix` (from recipe `PREFIX`)
- `supported_gen_steps` (from recipe `SUPPORTED_GEN_STEPS`)
- The derivation rule: `spec_from(prefix, gen)`

**FORBIDDEN**:
- Hardcoded override mappings
- Special-case logic that breaks the derivation rule
- Driver-level `get_materialization_map()` methods that return non-derived mappings
- Any "second truth" that duplicates or contradicts engine recipe declarations
- **DriverRegistry special-case overrides / orphan mappings are FORBIDDEN in mainline**
- **`get_materialization_map()` MAY exist but MUST be purely derived: `{gen: f"{PREFIX}_{gen}"}` for supported gens. No exceptions.**

**Rationale**: If mappings are derived, they cannot drift from SSOT. If they are hardcoded, they can. Special-case overrides create "second truth" that contradicts the SSOT and enables drift.

### 12.4 No Legacy/Compatibility Layers (Hard Ban)

**No compatibility layers, no alias tables, no "accept legacy then normalize" in mainline runtime/API/UI/tests.**

Legacy step type strings may appear **ONLY** in one-off migration/import tooling (if such tooling exists), not in execution paths.

**Mainline code MUST**:
- Reject any step type value that is not a valid `step_type_gen` or `step_type_spec` according to this constitution
- Use only canonical `join()`/`split()` functions for conversion (§3.1)
- Never maintain alias tables or normalization layers that accept legacy values

**Rationale**: Compatibility layers create drift and violate the single source of truth. Legacy values must be converted at import/migration boundaries, not accepted in mainline execution.

---

## 13. Gates / Enforcement

Gates exist to prevent whack-a-mole regressions. Each gate MUST be implemented as an automated test that runs in CI.

### Gate A: No Legacy Identity Keys

**Condition**: No DTO/dataclass fields or function parameters named `step_type` (bare), `id` (should be `ulid`), `calc_id` (should be `calc_ulid`), etc.

**Test**: `tests/gates/test_no_legacy_identity_fields.py`

---

### Gate C1: Declared-Only Enforcement

**Condition**:
- Every `step_type_gen` assignment MUST satisfy: `step_type_gen ∈ GenStepRegistry.GEN_STEPS`
- Every `step_type_spec` assignment MUST satisfy: `step_type_spec ∈ (⋃ engines {prefix}_{gen} for gen in supported_gen_steps)`

**Test**: `tests/gates/test_step_type_declared_sets.py`

**Rationale**: Prevents typos, unregistered steps, and drift from SSOT.

---

### Gate C2: No Gen/Spec Cross-Assignment

**Condition** (hard rules):

Any value assigned to a field/kwarg named exactly `step_type_gen` MUST:
- be in `GenStepRegistry.GEN_STEPS`
- and MUST NOT contain `_` (underscore)

Any value assigned to a field/kwarg named exactly `step_type_spec` MUST:
- contain `_` (underscore)
- and MUST be in the derived SPEC set: `union over engines of {PREFIX}_{gen} for gen in SUPPORTED_GEN_STEPS`

**Enforcement**: This is implemented as a gate test scanning the repository for assignments, kwargs, and literals in step-type contexts. The test MUST fail if:
- A `step_type_gen` field/kwarg receives a value containing `_` or not in `GenStepRegistry.GEN_STEPS`
- A `step_type_spec` field/kwarg receives a value without `_` or not in the derived SPEC set

**Test**: `tests/gates/test_step_type_cross_assignment.py` (or equivalent)

**Rationale**: Prevents cross-namespace contamination. A spec value (with `_`) MUST NOT be assigned to `step_type_gen`, and a gen value (without `_`) MUST NOT be assigned to `step_type_spec`. This makes cross-assignment impossible to "argue away" by making it a hard gate failure.

---

### Gate: Underscore Bans

**Condition**:
- Every `engine_prefix` (from recipe `PREFIX`) MUST NOT contain `_`
- Every `step_type_gen` (from `GenStepRegistry.GEN_STEPS`) MUST NOT contain `_`

**Test**: `tests/gates/test_step_type_constitution.py` (or equivalent)

**Rationale**: Enforces disambiguation law (§5).

---

### Gate: Supported Gen Steps Subset Check

**Condition**: For every engine recipe, `SUPPORTED_GEN_STEPS ⊆ GenStepRegistry.GEN_STEPS`

**Test**: `tests/gates/test_step_type_constitution.py` (or equivalent)

**Rationale**: Ensures engines only declare support for registered gen steps.

---

### Gate: No Manual Join/Split

**Condition**: Runtime code paths MUST NOT perform manual string parsing/concatenation for step type conversion:
- ❌ `spec.split("_", 1)` or any manual underscore parsing
- ❌ `f"{prefix}_{gen}"` or any manual concatenation for step type derivation
- ❌ `startswith(prefix+"_")`, strip-prefix helpers, custom `is_spec` checks that reimplement the underscore rule

**Required**: All conversions MUST use canonical functions:
- ✅ `spec_from(prefix, gen)` for join
- ✅ `gen_from(spec)` for split (returns gen)
- ✅ `prefix_from(spec)` for split (returns prefix)

**Scope note**: This gate applies to runtime code paths. Tests/docs may contain literal spec strings but MUST NOT implement conversion logic.

**Test**: `tests/gates/test_no_manual_join_split.py` (or equivalent)

**Rationale**: Enforces §3.1 (Conversion API Law). Prevents scattered ad-hoc parsing that creates inconsistency.

---

### Gate: Recipe Roundtrip Invariant

**Condition**: For every engine recipe and every gen in `supported_gen_steps`:
```
spec = join(prefix, gen)
split(spec) == (prefix, gen)
```

**Test**: `tests/gates/test_recipe_roundtrip.py` (or equivalent)

**Rationale**: Ensures canonical join/split functions are inverse operations for all valid engine/gen combinations.

---

### Gate: Declared-Only Invariants

**Condition**:
- Every `step_type_gen` MUST be in global `GenStepRegistry.GEN_STEPS`
- Every `step_type_spec` MUST split to `(prefix, gen)` where:
  - `prefix` is a registered `engine_prefix` (from recipe `PREFIX`)
  - `gen` is in `GenStepRegistry.GEN_STEPS`

**Test**: `tests/gates/test_step_type_declared_sets.py` (extends Gate C1)

**Rationale**: Prevents typos, unregistered steps, and drift from SSOT. Ensures all step types are declared-only.

---

### Gate: No Bare step_type Fields/Parameters

**Condition**: No function parameter, dataclass field, or dict key named `step_type` (must be `step_type_gen` or `step_type_spec`)

**Test**: `tests/gates/test_no_legacy_identity_fields.py` (extends Gate A)

**Rationale**: Enforces §11 (no bare step_type rule).

---

### Gate: Banned Legacy Alias Values

**Condition**: The following strings MUST NOT appear as step type values (not in executable names, file paths, or comments):
- `"w90_preproc"`
- `"w90_run"`

**Test**: New gate test (or extend existing)

**Rationale**: Enforces §7 (alias policy).

---

### Gate: Forbid Third Namespaces

**Condition**: No code, test, or persisted data MAY use step type values in formats like:
- `"GEN_SCF"` (GEN_ prefix with underscore)
- `"SCF"` (uppercase enum values)
- Any format other than lowercase `step_type_gen` or `{prefix}_{gen}` `step_type_spec`

**Test**: Scan for patterns like `GEN_`, `GeneralizedStep`, uppercase step type literals

**Rationale**: Prevents namespace proliferation and confusion.

---

### Gate: No Non-Derived Mapping Tables

**Condition**: Any mapping dict where a `step_type_gen` key maps to a value that is not exactly `spec_from(prefix, gen)` for some engine prefix MUST NOT exist. Any hardcoded mapping list/table outside the derivation utilities MUST NOT exist.

**What to scan for** (doc-level spec):
- Any mapping dict where a `step_type_gen` key maps to a value that is not exactly `spec_from(prefix, gen)` for some engine prefix
- Any hardcoded mapping list/table outside the derivation utilities (e.g., `step_type_convert.py`, `DriverRegistry._build_materialization_map()`)

**Test**: Scan for dict literals, mapping tables, or override methods that contain step type mappings not derivable from `PREFIX + SUPPORTED_GEN_STEPS + spec_from()`

**Rationale**: Enforces §12.3 (derived mappings only). Prevents "second truth" mapping tables that can drift from SSOT. Makes non-derived overrides impossible to justify.

---

### Why Gates Exist

Gates prevent whack-a-mole regressions. Without gates, a developer might:
1. Add a new step type with an underscore in the gen name
2. Add a hardcoded mapping table instead of using SSOT
3. Use a bare `step_type` field instead of `step_type_gen`/`step_type_spec`
4. Accept legacy alias values in new code

Gates catch these violations immediately, before they propagate through the codebase.

---

## 14. Migration Notes

When migrating step type names or adding new engines:

### Checklist

1. **Update GenStepRegistry** (`src/quantumvitas/workflow/gen_steps.py`)
   - Add/remove gen step names in `GEN_STEPS` frozenset
   - Ensure no underscores in gen names

2. **Update Engine Recipes** (`src/quantumvitas/drivers/*/driver.py`)
   - Update `SUPPORTED_GEN_STEPS` to include new gen steps (if engine supports them)
   - Ensure `PREFIX` has no underscores

3. **Update Tests/Golden Fixtures**
   - Use generator patching at the generator end (minimal patch)
   - Do NOT hand-edit golden artifacts
   - Regenerate fixtures if they contain step type values

4. **Verify Output File Naming**
   - Ensure output filenames use gen names (e.g., `relax.out`, not `qe_relax.out`)
   - Update any hardcoded filename patterns

5. **Rerun Full Test Suite**
   - Use project's standard test command (e.g., `.venv/bin/pytest -n auto --dist=loadfile`)
   - Verify all gates pass
   - Verify no legacy alias values remain

6. **Update Documentation**
   - Update any docs that reference step type names
   - Ensure examples use canonical gen/spec names

---

## Acceptance Criteria

The repository is compliant with this constitution when:

- ✅ **No bare `step_type` fields/parameters anywhere** (Gate A + extension)
- ✅ **No underscores in gen names or engine prefixes** (Underscore ban gate)
- ✅ **All step types are declared-only** (Gate C1 + Declared-Only Invariants gate)
- ✅ **No legacy alias step type values** (`w90_preproc`, `w90_run` banned)
- ✅ **`step.yaml` uses spec only; UI/output uses gen only** (verified by inspection + gates)
- ✅ **No third namespaces** (`GEN_*`, enum values, etc.)
- ✅ **All mappings are derived from SSOT** (no hardcoded override tables)
- ✅ **No gen/spec cross-assignment** (Gate C2 passes)
- ✅ **No non-derived mapping tables** (Gate: No Non-Derived Mapping Tables passes)
- ✅ **No manual join/split** (Gate: No Manual Join/Split passes)
- ✅ **Recipe roundtrip invariant holds** (Gate: Recipe Roundtrip Invariant passes)
- ✅ **Execution conversion at single choke point** (verified by inspection)
- ✅ **Engine recipes use GEN keys internally** (verified by inspection)

---

**End of Constitution**

