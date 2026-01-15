# Global YAML / Dict Usage Review
## Preparation for YamlDoc / StepDoc Refactor with Future Journal Support

---

## Section A — Current YAML / Dict Usage Inventory

### A1. YAML Read Entry Points

**Preset System:**
- `presets/integration.py:359` - `apply_presets_to_step()`: `yaml.safe_load(step_path.read_text())` → full `content` dict
- `presets/integration.py:228, 279` - `_load_step_parameters()`: Loads full YAML, extracts `parameters` + `cards` only, returns `List[Dict[str, Dict[str, Any]]]` (list of step param dicts)
- `presets/integration.py:736` - `get_step_preset_params()`: Loads full YAML, extracts subset of preset-related keys
- `presets/detector.py:692` - `detect_all_presets()`: Receives `List[Dict[str, Dict[str, Any]]]` (only parameters/cards, not full YAML)

**Calculation / Step System:**
- `calculation/structure_steps.py:164` - `StructureStepSpec.from_yaml()`: `yaml.safe_load(spec_path.read_text())` → full content dict → `StructureStepSpec` object
- `calculation/calculation.py:298` - `load_calculation()`: `yaml.safe_load(path.read_text())` → full `calculation.yaml` dict
- `core/models.py:298` - `CalculationModel.from_dict()`: Receives full dict, extracts sections

**API / CLI:**
- `api.py:6283` - `extract_structure_from_step_output()`: `yaml.safe_load(step_resolved.absolute_path.read_text())` → full dict
- `api.py:800+` - `create_step()`: Loads defaults, constructs `StructureStepSpec`, writes via `spec.to_dict()`
- `cli/main.py:2195, 2873` - Various step creation commands: Load defaults, write via `yaml.safe_dump(spec.to_dict())`

**Project System:**
- `project/storage.py:28` - `load_settings()`: `yaml.safe_load(settings_file.read_text())` → settings dict
- `project/snapshot.py:135, 162, 169` - Snapshot loading: Multiple `yaml.safe_load()` calls for project/calc/step files

**Pattern Summary:**
- **Full tree loading**: Most entry points load complete YAML tree
- **Partial extraction**: Preset detect extracts only `parameters` + `cards` for downstream processing
- **Downstream receives**: Either full dict or extracted subset (no consistent pattern)

### A2. YAML Write Entry Points

**Preset Apply (Primary Write Path):**
- `presets/integration.py:701` - `apply_presets_to_step()`: `yaml.safe_dump(content, ...)` where `content` is mutated in-place
  - **Mutation pattern**: Load → extract → mutate working copies → reassign to `content` → dump
  - **Meta handling**: `content` dict preserves `meta` (not explicitly modified, but could be overwritten if `content` is reconstructed)

**Step Creation:**
- `api.py:877` - `create_step()`: `yaml.safe_dump(spec.to_dict(), ...)` where `spec.to_dict()` reconstructs dict (excludes `structure_id`, `parent_calculation_id`, `structure`)
- `calculation/importers.py:254` - Step import: `yaml.safe_dump(spec.to_dict(), ...)`
- `cli/main.py:2195, 2873` - CLI step creation: `yaml.safe_dump(spec.to_dict(), ...)`

**Step Update (Structure Extraction):**
- `api.py:6376` - `extract_structure_from_step_output()`: `step_yaml_data["produced_structure_ulid"] = meta.id` (direct mutation) → `yaml.safe_dump(step_yaml_data, ...)`

**Calculation Write:**
- `core/models.py:347` - `save_calculation()`: `yaml.safe_dump(model.to_dict(), ...)` (reconstructs dict)

**Project Write:**
- `project/storage.py:33` - `save_settings()`: `yaml.safe_dump(settings.data, ...)`

**Write Pattern Classification:**
- **In-place mutation**: `integration.py:701` (mutates `content` dict directly)
- **Reconstruct + dump**: `api.py:877`, `calculation/importers.py:254` (via `spec.to_dict()`)
- **Direct mutation + dump**: `api.py:6376` (mutates loaded dict, then dumps)
- **Meta preservation**: `spec.to_dict()` explicitly preserves `meta`; `integration.py:701` preserves `meta` implicitly (not deleted)

### A3. Dict Read Patterns

**Direct Indexing:**
- `presets/integration.py:367, 369, 371, 373` - `step_yaml["SYSTEM"]`, `step_yaml["ELECTRONS"]`, `step_yaml["cards"]`
- `presets/integration.py:690, 692, 698` - `content["parameters"]["SYSTEM"]`, `content["parameters"]["ELECTRONS"]`, `content["cards"]`
- `presets/oracle.py:44` - `self.yaml_state.get("SYSTEM", {})`
- `presets/paramspace.py:966` - `yaml_state.get("SYSTEM", {})`

**`.get()` with defaults:**
- `presets/integration.py:361, 362` - `content.get("parameters", {})`, `content.get("cards", {})`
- `presets/integration.py:376, 377` - `existing_params.get("SYSTEM", {})`, `existing_params.get("ELECTRONS", {})`
- `presets/detector.py:186` - `params.get("cards") or {}`
- `presets/oracle.py:44, 45` - `self.yaml_state.get("SYSTEM", {})`, `system.get("occupations")`
- **165+ occurrences** across codebase (most common pattern)

**Iterating over dicts:**
- `presets/integration.py:644-653` - `for section, patch_dict in compiled_patches.items()`, `for key in patch_dict.keys()`
- `presets/integration.py:705-710` - `compiled_patches["SYSTEM"].keys()`, `compiled_patches["ELECTRONS"].keys()`, `compiled_patches["cards"].keys()`
- `presets/variants_registry.py:290, 291` - `if key in patch["SYSTEM"]`, `value = patch["SYSTEM"][key]`

**Reference passing (sub-dicts passed to functions):**
- `presets/integration.py:441` - `compile_dimension_patch_for_step(..., step_yaml, ...)` where `step_yaml` is a dict reference
- `presets/integration.py:667` - `Oracle(current_yaml_state)` where `current_yaml_state` is a dict reference
- `presets/integration.py:674` - `paramspace.apply_invariants(current_yaml_state, oracle)` where `current_yaml_state` is mutated in-place
- `presets/paramspace.py:966` - `del system["degauss"]` (mutates dict passed by reference)

**Pattern Summary:**
- **Most common**: `.get(key, default)` for safe access
- **Direct indexing**: Used when key existence is guaranteed (after `.get()` check or construction)
- **Reference leakage risk**: High - sub-dicts passed to functions are mutated in-place (e.g., `apply_invariants()` deletes keys)

### A4. Dict Write Patterns

**Direct assignment:**
- `presets/integration.py:367, 369, 371, 373` - `step_yaml["SYSTEM"] = {}`, `step_yaml["ELECTRONS"] = {}`, `step_yaml["cards"] = existing_cards`
- `presets/integration.py:690, 692` - `content["parameters"]["SYSTEM"] = existing_system`, `content["parameters"]["ELECTRONS"] = existing_electrons`
- `api.py:6375` - `step_yaml_data["produced_structure_ulid"] = meta.id`

**`.update()` (merge):**
- `presets/integration.py:448, 450, 452` - `compiled_patches["SYSTEM"].update(patch["SYSTEM"])`, `compiled_patches["ELECTRONS"].update(patch["ELECTRONS"])`, `compiled_patches["cards"].update(patch["cards"])`
- `presets/integration.py:458, 459, 462` - `step_yaml["SYSTEM"].update(compiled_patches["SYSTEM"])`, `step_yaml["ELECTRONS"].update(compiled_patches["ELECTRONS"])`, `step_yaml["cards"].update(compiled_patches["cards"])`
- `presets/integration.py:656, 657, 658` - `existing_system.update(compiled_patches["SYSTEM"])`, `existing_electrons.update(compiled_patches["ELECTRONS"])`, `existing_cards.update(compiled_patches["cards"])`
- `presets/integration.py:698` - `content["cards"].update(existing_cards)`
- **31+ occurrences** in preset system alone

**`.pop()` (delete):**
- `presets/integration.py:637, 639, 641` - `existing_system.pop(key, None)`, `existing_electrons.pop(key, None)`, `existing_cards.pop(key, None)`
- `presets/integration.py:647, 650, 653` - `existing_system.pop(key, None)`, `existing_electrons.pop(key, None)`, `existing_cards.pop(key, None)`
- `presets/paramspace.py:969` - `del system["degauss"]` (direct deletion, not `.pop()`)
- `api.py:936, 937, 939, 940` - `wf_data.pop("structure_name", None)`, `wf_data.pop("structure", None)`

**Branch replacement:**
- `presets/integration.py:690, 692` - `content["parameters"]["SYSTEM"] = existing_system` (entire branch replaced)
- `presets/integration.py:687` - `content["parameters"] = {}` (branch created if missing)

**Multi-step merge logic:**
- `presets/integration.py:634-658` - Complex sequence:
  1. Delete keys from `all_deletions` set
  2. Delete keys that will be written (overwrite semantics)
  3. Update with compiled patches
  4. Apply invariants (mutates `current_yaml_state`)
  5. Reassign from `current_yaml_state` to `existing_*` dicts
  6. Reassign to `content["parameters"]` and `content["cards"]`

**Pattern Summary:**
- **Merge-heavy**: Most mutations use `.update()` to merge patches
- **Delete-then-write**: Deletions applied before updates (overwrite semantics)
- **Multi-phase**: Preset apply uses 5+ mutation phases with intermediate state

---

## Section B — Implicit Semantic Contracts

### B1. Branch vs Leaf Assumptions

**Branches treated as containers:**
- `presets/integration.py:365` - `step_yaml: Dict[str, Dict[str, Any]]` - Top-level keys (`SYSTEM`, `ELECTRONS`, `cards`) are branches
- `presets/integration.py:412-416` - `compiled_patches` structure: `{"SYSTEM": {...}, "ELECTRONS": {...}, "cards": {...}}` - Sections are branches
- `presets/integration.py:662-666` - `current_yaml_state` structure: `{"SYSTEM": {...}, "ELECTRONS": {...}, "cards": {...}}` - Sections are branches

**Leaves are primitive values:**
- `presets/integration.py:388` - `patch["SYSTEM"]["degauss"] = degauss_map[profile_name]` - `degauss` is a leaf (float)
- `presets/integration.py:656` - `existing_system.update(compiled_patches["SYSTEM"])` - Values in `compiled_patches["SYSTEM"]` are leaves

**Entire subtree replacement:**
- `presets/integration.py:690` - `content["parameters"]["SYSTEM"] = existing_system` - Entire `SYSTEM` branch replaced (not merged into existing)
- `presets/integration.py:687` - `content["parameters"] = {}` - Entire `parameters` branch replaced if missing

**Assumption Summary:**
- **Two-level hierarchy**: `{section: {key: value}}` where sections are branches, keys are leaves
- **Branch replacement**: Sections are replaced entirely, not merged (when assigned via `=`)
- **Leaf merge**: Keys within sections are merged (via `.update()`)

### B2. Copy vs Reference Assumptions

**Explicit copying:**
- `presets/integration.py:362` - `existing_cards = dict(content.get("cards", {}))` - Shallow copy
- `presets/integration.py:365` - `step_yaml: Dict[str, Dict[str, Any]] = dict(existing_params)` - Shallow copy
- `presets/integration.py:376, 377` - `existing_system = dict(existing_params.get("SYSTEM", {}))`, `existing_electrons = dict(existing_params.get("ELECTRONS", {}))` - Shallow copies
- `calculation/importers.py:82, 86` - `merged_params[section] = dict(default_params.get(section, {}))`, `merged_cards = dict(default_cards)` - Shallow copies

**Reference passing (mutation risk):**
- `presets/integration.py:441` - `compile_dimension_patch_for_step(..., step_yaml, ...)` - `step_yaml` passed by reference, may be read but not mutated by compiler
- `presets/integration.py:667` - `Oracle(current_yaml_state)` - `current_yaml_state` passed by reference, Oracle reads only
- `presets/integration.py:674` - `paramspace.apply_invariants(current_yaml_state, oracle)` - `current_yaml_state` passed by reference, **mutated in-place** (line 969: `del system["degauss"]`)
- `presets/integration.py:677-679` - `existing_system = current_yaml_state["SYSTEM"]` - Reference reassignment (not copy)

**Assumption Summary:**
- **Working copies**: `existing_*` dicts are shallow copies to avoid mutating `content` prematurely
- **Shared references**: `current_yaml_state` shares references with `existing_*` dicts (invariants mutate shared state)
- **Bypass risk**: If Doc returns live references, mutations could bypass Doc isolation

### B3. Ordering / Atomicity Assumptions

**Mutation order dependencies:**
- `presets/integration.py:634-658` - **Critical ordering**:
  1. Delete keys from `all_deletions` set (lines 635-641)
  2. Delete keys that will be written (lines 644-653) - **Must happen before update**
  3. Update with compiled patches (lines 656-658)
  4. Apply invariants (line 674) - **Must happen after patches applied**
  5. Reassign from `current_yaml_state` (lines 677-679) - **Must happen after invariants**

**Atomicity assumptions:**
- `presets/integration.py:701` - Single `yaml.safe_dump(content, ...)` - Entire `content` dict written atomically
- `presets/integration.py:656-658` - Three `.update()` calls - Not atomic (could fail mid-update), but no rollback logic

**Patch application semantics:**
- `presets/integration.py:447-455` - Patches merged in loop (prerequisite dimensions first, then dependent)
- `presets/integration.py:458-462` - Patches applied to `step_yaml` for oracle to read latest state
- **Assumption**: Patches are independent (no cross-patch dependencies within a phase)

**Assumption Summary:**
- **Delete-before-write**: Deletions must happen before updates (overwrite semantics)
- **Invariants-after-patches**: Invariants run after all patches applied (they read final state)
- **Single-write**: Final write is atomic (entire dict dumped at once)

---

## Section C — Minimal Required Doc Capabilities (MUST HAVE)

Based on observed code behavior, YamlDoc MUST provide:

### C1. Path-Based Leaf Get
**Required for:**
- `presets/integration.py:361, 362` - `content.get("parameters", {})`, `content.get("cards", {})`
- `presets/oracle.py:44, 45` - `self.yaml_state.get("SYSTEM", {}).get("occupations")`
- `presets/detector.py:186` - `params.get("cards") or {}`

**API requirement:**
```python
doc.get("parameters", default={})  # Returns dict (or default)
doc.get("SYSTEM.ecutwfc", default=None)  # Path-based leaf get
```

### C2. Path-Based Leaf Set
**Required for:**
- `presets/integration.py:388` - `patch["SYSTEM"]["degauss"] = degauss_map[profile_name]`
- `api.py:6375` - `step_yaml_data["produced_structure_ulid"] = meta.id`

**API requirement:**
```python
doc.set("SYSTEM.degauss", 0.02)  # Path-based leaf set
doc.set("produced_structure_ulid", meta.id)
```

### C3. Branch / Leaf Delete
**Required for:**
- `presets/integration.py:637, 639, 641` - `existing_system.pop(key, None)`
- `presets/paramspace.py:969` - `del system["degauss"]`

**API requirement:**
```python
doc.delete("SYSTEM.degauss")  # Delete leaf
doc.delete("parameters")  # Delete branch (if needed)
```

### C4. List Keys of a Branch
**Required for:**
- `presets/integration.py:644-653` - `for key in patch_dict.keys()`
- `presets/integration.py:705-710` - `compiled_patches["SYSTEM"].keys()`

**API requirement:**
```python
keys = doc.keys("SYSTEM")  # Returns list of keys in SYSTEM branch
```

### C5. Recursive Patch Application (apply_patch)
**Required for:**
- `presets/integration.py:656-658` - `existing_system.update(compiled_patches["SYSTEM"])`
- `presets/integration.py:447-452` - Multiple patch merges

**API requirement:**
```python
doc.apply_patch({"SYSTEM": {"ecutwfc": 50, "ecutrho": 200}})  # Merge patch dict
```

### C6. Deep-Copy Semantics for Returned Lists/Dicts
**Required for:**
- `presets/integration.py:376, 377` - `existing_system = dict(existing_params.get("SYSTEM", {}))` - Code expects copy
- `presets/integration.py:677-679` - `existing_system = current_yaml_state["SYSTEM"]` - Code expects reference (but this is a bug risk)

**API requirement:**
```python
system_dict = doc.get("SYSTEM", {})  # Returns copy (not live reference)
# OR
system_dict = doc.get_ref("SYSTEM")  # Returns live reference (if mutation needed)
```

**Critical**: Code currently assumes `.get()` returns a copy (line 376), but also assumes reference sharing (line 677). Doc must provide both patterns.

### C7. Full Tree Dump Back to YAML
**Required for:**
- `presets/integration.py:701` - `yaml.safe_dump(content, ...)`
- `api.py:877` - `yaml.safe_dump(spec.to_dict(), ...)`

**API requirement:**
```python
yaml_str = doc.to_yaml()  # Returns YAML string
# OR
dict_tree = doc.to_dict()  # Returns full dict tree for yaml.safe_dump()
```

### C8. Branch Replacement (Not Just Merge)
**Required for:**
- `presets/integration.py:690` - `content["parameters"]["SYSTEM"] = existing_system` - Entire branch replaced

**API requirement:**
```python
doc.set_branch("parameters.SYSTEM", system_dict)  # Replace entire branch
```

---

## Section D — Strongly Recommended Capabilities (SHOULD HAVE)

### D1. Centralized Mutation Funnel
**Why it matters:**
- `presets/integration.py:701` is the primary write path, but mutations happen in 5+ phases (lines 634-698)
- `api.py:6376` is a secondary write path that mutates directly
- **Risk**: If mutations bypass Doc, Journal cannot track changes

**What could break:**
- Journal misses mutations that happen outside Doc API
- No single point to hook before/after state capture

**Recommendation:**
- All mutations must go through Doc API (no direct dict access)
- Doc tracks all mutations internally (for Journal)

### D2. Leaf-Only Write Enforcement
**Why it matters:**
- `presets/integration.py:690` - `content["parameters"]["SYSTEM"] = existing_system` replaces entire branch
- **Risk**: Branch replacement could overwrite keys not in `existing_system` (if `existing_system` is a subset)

**What could break:**
- If `existing_system` is incomplete, branch replacement loses keys
- Current code assumes `existing_system` is complete (line 656: `existing_system.update(compiled_patches["SYSTEM"])`)

**Recommendation:**
- Doc should warn/error on branch replacement if branch contains keys not in replacement dict
- OR: Doc should merge (not replace) by default, require explicit flag for replacement

### D3. Optional Access Control (Detect / Compile)
**Why it matters:**
- Key-access enforcement already exists (`KeyAccessContext`), but only for `get_yaml_value()`
- **Risk**: Direct dict access bypasses enforcement (e.g., `presets/integration.py:361` uses `content.get("parameters", {})`)

**What could break:**
- Enforcement is incomplete if code uses direct dict access
- Doc could enforce access control at API boundary

**Recommendation:**
- Doc should integrate with `KeyAccessContext` (enforce on `doc.get()`, `doc.set()`, etc.)
- Doc should raise `KeyAccessError` on illegal access (same as current enforcement)

### D4. Normalization Hooks (Case, Alias)
**Why it matters:**
- QE parameters are case-insensitive (e.g., `"SYSTEM"` vs `"system"`)
- Current code uses uppercase consistently, but no enforcement

**What could break:**
- If user YAML has lowercase keys, code might miss them
- Doc could normalize on read/write

**Recommendation:**
- Doc should normalize section/key names (uppercase sections, lowercase keys)
- Doc should handle aliases (if needed)

### D5. Stable Operation Recording Points (for Journal)
**Why it matters:**
- `presets/integration.py:701` is the primary write point, but mutations happen in phases
- **Risk**: Journal needs to capture before/after state, but mutations are scattered

**What could break:**
- If Journal hooks at write time only, it misses intermediate mutations
- If Journal hooks at every mutation, it records too much noise

**Recommendation:**
- Doc should provide `doc.begin_transaction()` / `doc.commit_transaction()` API
- Journal hooks at `commit_transaction()` (single point)
- Doc tracks all mutations within transaction (for diff computation)

### D6. Ability to Reconstruct Before/After States Cleanly
**Why it matters:**
- Journal needs to compute diff between before/after states
- Current code loads YAML, mutates, writes (before = loaded dict, after = mutated dict)

**What could break:**
- If Doc mutates in-place, before state is lost
- Doc must preserve before state until commit

**Recommendation:**
- Doc should maintain snapshot of initial state (loaded from YAML)
- Doc should compute diff on commit (before snapshot vs current state)
- Doc should provide `doc.get_before_state()` / `doc.get_after_state()` for Journal

---

## Section E — Optional / Future-Facing Capabilities (NICE TO HAVE)

These are explicitly out of scope for the refactor, but relevant for long-term design:

### E1. Undo / Redo (Journal Replay)
- Journal could record operations, Doc could replay them
- **Not a blocker**: Can be added later if Journal stores operation log

### E2. Subtree Export/Import
- Export `parameters.SYSTEM` as separate dict, import into another Doc
- **Not a blocker**: Current code doesn't need this

### E3. Dry-Run / Diff-Only Mode
- Compute diff without applying mutations
- **Not a blocker**: Can be implemented via transaction rollback

### E4. Read-Only Documents
- Doc that prevents all mutations (for detect-only code paths)
- **Not a blocker**: Can be implemented via Doc mode flag

### E5. Schema Validation
- Validate YAML structure against schema (e.g., `step.yaml` must have `meta`, `step_type`, `parameters`)
- **Not a blocker**: Can be added as optional validation layer

---

## Section F — Migration Difficulty Assessment

### F1. Step.yaml → StepDoc

**Main mutation patterns:**
- **5-phase mutation** (`presets/integration.py:634-698`): Delete → Delete overwrites → Update → Invariants → Reassign
- **Branch replacement** (`presets/integration.py:690, 692`): Entire `SYSTEM`/`ELECTRONS` branches replaced
- **Direct mutation** (`api.py:6375`): `step_yaml_data["produced_structure_ulid"] = meta.id`

**Ordering dependencies:**
- **Critical**: Delete-before-update (lines 634-653 must happen before 656-658)
- **Critical**: Invariants-after-patches (line 674 must happen after 656-658)
- **Critical**: Reassign-after-invariants (lines 677-679 must happen after 674)

**Highest risk areas:**
- `presets/integration.py:677-679` - Reference reassignment (assumes `current_yaml_state` shares refs with `existing_*`)
- `presets/paramspace.py:969` - `del system["degauss"]` (direct deletion on passed reference)
- `presets/integration.py:690, 692` - Branch replacement (could lose keys if `existing_system` is incomplete)

**Risk level: HIGH**

**Why:**
- Complex 5-phase mutation sequence with ordering dependencies
- Reference sharing assumptions (line 677) could break if Doc returns copies
- Invariants mutate passed dict (line 674) - must work with Doc API
- Branch replacement semantics unclear (merge vs replace)

### F2. Calculation.yaml → CalcDoc

**Main mutation patterns:**
- `core/models.py:347` - `save_calculation()`: Reconstructs dict via `model.to_dict()`, then dumps
- `api.py:880` - `save_calculation(wf_model, calculation_dir)`: Model-based write (not direct dict mutation)

**Whether strong normalization / access control is required:**
- **Low priority**: Calculation YAML is model-based (not directly mutated)
- **Access control**: Not needed (calculation YAML doesn't have ParamSpace keys)

**Meta vs parameter separation concerns:**
- `core/models.py:242` - `meta = ResourceMeta.from_dict(data.get("meta"), ...)` - Meta extracted, not mutated
- **Low risk**: Meta is read-only for preset operations

**Risk level: LOW**

**Why:**
- Calculation YAML is model-based (not directly mutated)
- Write path is simple (reconstruct + dump)
- No complex mutation sequences
- No ParamSpace keys (no access control needed)

### F3. Project.yaml → ProjectDoc

**Main mutation patterns:**
- `project/storage.py:33` - `save_settings()`: `yaml.safe_dump(settings.data, ...)` - Simple dump
- `api.py:6326` - `structures = config.setdefault("structures", [])` - Direct mutation on loaded dict
- `api.py:6372` - `save_project_config(project_root, config)` - Mutated dict saved

**Rename / path / slug mutations:**
- `core/project_utils.py:356` - `slug = (entry.get("meta") or {}).get("slug") or entry.get("slug")` - Slug read, not mutated in preset code
- **Low risk**: Preset code doesn't mutate project structure

**Cross-file consistency issues:**
- Project YAML references calculations (via `calculations[]` array)
- Step YAML references are implicit (via file location)
- **Risk**: If project YAML is mutated, calculation/step references could become inconsistent

**Risk level: MEDIUM**

**Why:**
- Project YAML has cross-file references (calculations, structures)
- Some direct mutation (`api.py:6326`)
- But preset code doesn't mutate project structure (low risk for preset refactor)

---

## Section G — Journal Readiness Considerations (Design-Level)

### G1. Natural Transaction Boundaries

**Primary transaction:**
- `presets/integration.py:apply_presets_to_step()` - Entire function is one logical transaction
  - **Before**: Loaded YAML state
  - **After**: Mutated YAML state (after all phases)
  - **Boundary**: Function entry (load) → Function exit (write)

**Secondary transactions:**
- `api.py:create_step()` - Step creation is one transaction
- `api.py:extract_structure_from_step_output()` - Structure extraction is one transaction

**Transaction granularity:**
- **File-level**: One transaction per file write (one `step.yaml` write = one transaction)
- **Operation-level**: One transaction per user operation (e.g., "apply precision preset")

### G2. Mutation Centralization

**Current state:**
- **Scattered**: Mutations happen in 5+ phases within `apply_presets_to_step()`
- **Centralized write**: Single write point (`integration.py:701`)
- **Bypass risk**: Direct dict mutation (`api.py:6375`) bypasses preset integration

**With Doc:**
- **Centralized**: All mutations go through Doc API
- **Single write**: Doc provides `doc.commit()` (writes to disk + triggers Journal)
- **No bypass**: Direct dict access eliminated (Doc is only interface)

### G3. Before/After State Capture

**Current feasibility:**
- **Before**: `content = yaml.safe_load(step_path.read_text())` (line 359)
- **After**: `content` dict after mutations (line 701)
- **Feasible**: Yes, but requires manual capture (code must save before state)

**With Doc:**
- **Before**: Doc maintains snapshot of initial state (loaded from YAML)
- **After**: Doc maintains current state (after mutations)
- **Feasible**: Yes, Doc can provide `doc.get_before_state()` / `doc.get_after_state()`

### G4. Doc-Level Mutation Funnel

**Would it simplify Journal integration?**

**Yes:**
- **Single hook point**: Journal hooks at `doc.commit()` (one place)
- **Automatic diff**: Doc computes diff internally (before snapshot vs current state)
- **Operation tracking**: Doc can track operation type (e.g., "apply_preset", "create_step")

**Implementation:**
```python
# Doc design
class StepDoc:
    def __init__(self, path: Path):
        self._before_state = yaml.safe_load(path.read_text())  # Snapshot
        self._current_state = copy.deepcopy(self._before_state)  # Working copy
    
    def commit(self, journal: Optional[Journal] = None):
        after_state = self.to_dict()
        diff = compute_diff(self._before_state, after_state)
        if journal:
            journal.record_transaction(
                target=self.get("meta.id"),
                before=self._before_state,
                after=after_state,
                ops=diff
            )
        # Write to disk
        self._path.write_text(yaml.safe_dump(after_state, ...))
```

**Benefits:**
- Journal integration is mechanical (hook at `commit()`)
- No manual before/after capture needed
- Diff computation is centralized (Doc responsibility)

---

## Section H — Final Recommendation

### H1. Unified YamlDoc Core with Document-Specific Profiles

**Viability: YES**

**Rationale:**
- **Common patterns**: All YAML types use similar access patterns (path-based get/set, branch operations)
- **Document-specific**: Step YAML has `parameters`/`cards` structure, Calculation YAML has `steps[]` array, Project YAML has `calculations[]`/`structures[]` arrays
- **Profile approach**: Core `YamlDoc` class with `StepDoc`, `CalcDoc`, `ProjectDoc` subclasses (or composition via profile/config)

**Design sketch:**
```python
class YamlDoc:
    """Core YAML document wrapper with mutation tracking."""
    def get(self, path: str, default: Any = None) -> Any: ...
    def set(self, path: str, value: Any) -> None: ...
    def delete(self, path: str) -> None: ...
    def apply_patch(self, patch: Dict[str, Any]) -> None: ...
    def commit(self, journal: Optional[Journal] = None) -> None: ...

class StepDoc(YamlDoc):
    """Step-specific YAML document with parameter/card structure."""
    def get_parameters(self) -> Dict[str, Dict[str, Any]]: ...
    def get_cards(self) -> Dict[str, Dict[str, Any]]: ...
    def set_parameter(self, section: str, key: str, value: Any) -> None: ...
```

### H2. Migration Strategy: Staged (Step First)

**Recommendation: STAGED MIGRATION (Step first, then Calculation, then Project)**

**Rationale:**
- **Step is highest risk**: Complex mutation sequences, ordering dependencies, reference sharing
- **Step is highest value**: Primary preset integration point, most mutations
- **Calculation/Project are lower risk**: Model-based, simpler write paths
- **Incremental validation**: Can validate Step migration before tackling Calculation/Project

**Migration order:**
1. **Phase 1**: Step.yaml → StepDoc
   - Replace `presets/integration.py:apply_presets_to_step()` with StepDoc API
   - Replace `api.py:create_step()` with StepDoc API
   - Replace `api.py:extract_structure_from_step_output()` with StepDoc API
   - Validate: All preset tests pass, UI works
2. **Phase 2**: Calculation.yaml → CalcDoc (if needed)
   - Lower priority (model-based, less mutation)
   - Can defer if Step migration is sufficient
3. **Phase 3**: Project.yaml → ProjectDoc (if needed)
   - Lowest priority (preset code doesn't mutate project structure)
   - Can defer indefinitely

### H3. Hard Blockers Discovered

**Blocker 1: Reference Sharing Assumptions**
- **Location**: `presets/integration.py:677-679`
- **Issue**: Code assumes `current_yaml_state["SYSTEM"]` shares reference with `existing_system`
- **Impact**: If Doc returns copies, invariants won't mutate `existing_system`
- **Solution**: Doc must provide `get_ref()` API for cases where mutation is needed, OR invariants must use Doc API

**Blocker 2: Invariant Mutation Pattern**
- **Location**: `presets/paramspace.py:969` - `del system["degauss"]`
- **Issue**: Invariants mutate passed dict directly (not via Doc API)
- **Impact**: Invariants must be refactored to use Doc API, OR Doc must support reference passing
- **Solution**: Refactor `apply_invariants()` to accept Doc (not dict), use Doc API for mutations

**Blocker 3: Branch Replacement Semantics**
- **Location**: `presets/integration.py:690, 692` - `content["parameters"]["SYSTEM"] = existing_system`
- **Issue**: Code replaces entire branch (not merge)
- **Impact**: If `existing_system` is incomplete, keys are lost
- **Solution**: Doc should warn/error on branch replacement, OR code should merge (not replace)

**Blocker 4: Multi-Phase Mutation Ordering**
- **Location**: `presets/integration.py:634-698` - 5-phase mutation sequence
- **Issue**: Ordering is critical (delete → update → invariants → reassign)
- **Impact**: Doc must preserve ordering semantics
- **Solution**: Doc API should support same operations (delete, update, apply_invariants, reassign), OR code should be refactored to single-phase mutation

**No architectural blockers**: All blockers are implementation details that can be resolved with careful API design and code refactoring.

---

## Summary

**Current State:**
- YAML is loaded as dicts, mutated in-place, written back
- Preset apply uses 5-phase mutation sequence with ordering dependencies
- Reference sharing assumptions (invariants mutate passed dicts)
- Branch replacement semantics (entire branches replaced, not merged)

**Required Doc Capabilities:**
- Path-based get/set/delete
- Branch operations (list keys, replace branch)
- Recursive patch application
- Deep-copy semantics for returned dicts (with optional reference passing)
- Full tree dump to YAML

**Recommended Doc Capabilities:**
- Centralized mutation funnel (all mutations via Doc API)
- Transaction API (`begin_transaction()` / `commit_transaction()`)
- Before/after state tracking (for Journal)
- Access control integration (KeyAccessContext)
- Leaf-only write enforcement (warn on branch replacement)

**Migration Strategy:**
- **Staged**: Step first (highest risk/value), then Calculation/Project (if needed)
- **Risk level**: Step = HIGH, Calculation = LOW, Project = MEDIUM
- **Blockers**: Reference sharing, invariant mutation, branch replacement, ordering dependencies (all solvable)

**Journal Readiness:**
- **Natural boundaries**: File-level transactions (one write = one transaction)
- **Centralization**: Doc provides single mutation funnel (all mutations via API)
- **State capture**: Doc maintains before/after snapshots (automatic diff computation)
- **Integration**: Journal hooks at `doc.commit()` (mechanical, no manual capture needed)

**Conclusion:**
- Unified YamlDoc core with document-specific profiles is viable
- Staged migration (Step first) is recommended
- No architectural blockers (all blockers are implementation details)
- Journal integration is straightforward with Doc-level mutation funnel

