# LAMMPS Core Delta Analysis

**Version**: 1.0.0  
**Date**: 2026-01-19  
**Status**: Research & Design Phase  
**Constitution Reference**: All sections

---

## 1. Executive Summary

After thorough analysis of QMatSuite's existing architecture and LAMMPS requirements, the verdict is:

> **Minimal core changes required.** Most LAMMPS integration can be implemented at the engine level by reusing existing abstractions. Only 2-3 small generalizations would improve elegance but are NOT blockers.

---

## 2. Architecture Compatibility Analysis

### 2.1 What Already Works

| Component | Current State | LAMMPS Compatibility |
|-----------|--------------|---------------------|
| **Engine Registry** | Supports multiple engines (qe, vasp, orca, pyscf) | ✅ Add `lammps` engine |
| **Step Types** | GEN→SPEC mapping pattern | ✅ Add `lammps_*` types |
| **Manifest System** | 3-SHA skip logic | ✅ Works as-is |
| **Run Lock** | `run.lock` / `edit.lock` | ✅ Reuse directly |
| **Trajectory Spec** | Engine-agnostic Frame schema | ✅ Map LAMMPS outputs |
| **Scan Expansion** | Parameter sweep infrastructure | ✅ Reuse directly |
| **JobGraph Execution** | Unified execution pipeline | ✅ Add LAMMPS handler |

### 2.2 What Needs Extension

| Component | Current State | LAMMPS Need | Severity |
|-----------|--------------|-------------|----------|
| **Asset Management** | `pseudo_dir`/`species_map` for QE | `potential_map` for classical | Optional enhancement |
| **Manifest SHA** | `pseudo_set_sha` | `potential_assets_sha` | Trivial addition |
| **Parser Registry** | Implicit per-engine parsers | LAMMPS dump/log parsers | Add parsers (no core change) |
| **Units Normalization** | Assumed consistent | Multi-unit-system support | Engine-level conversion |

---

## 3. Detailed Delta Analysis

### 3.1 CHANGE NOT NEEDED: Core Asset System

**Current State:**
The pseudo management in `core/pseudo.py` and `core/pseudo_runtime.py` is heavily QE-specific (UPF files, element→pseudo mapping).

**Analysis:**
For MVP LAMMPS, we do NOT need to generalize the core asset system. Instead:

1. Implement `potential_map` at the **engine level** (in `engine/lammps_engine.py`)
2. Store potential definitions in `calculation.yaml` under `engine_params.lammps.potential_map`
3. Handle staging in `materialize_lammps_input()`

**Rationale:**
- Keeps core unchanged
- Follows existing pattern of engine-specific parameter handling
- Can refactor to shared asset abstraction later if VASP/other engines need similar

**Verdict:** ❌ No core change needed

---

### 3.2 TRIVIAL ADDITION: Manifest potential_assets_sha

**Current State:**
`ManifestStepEntry` has `pseudo_set_sha` for tracking pseudopotential identity.

```python
@dataclass
class ManifestStepEntry:
    pseudo_set_sha: str  # SHA256 of pseudo set
    structure_sha: str   # SHA256 of structure
    step_sha: str        # SHA256 of step YAML
```

**LAMMPS Need:**
Track potential file identity for skip logic.

**Proposed Change:**
Add one optional field:

```python
@dataclass
class ManifestStepEntry:
    pseudo_set_sha: str
    structure_sha: str
    step_sha: str
    potential_assets_sha: Optional[str] = None  # NEW: For classical potentials
```

**Impact:**
- Backward compatible (optional field)
- Existing engines ignore it
- LAMMPS uses it instead of `pseudo_set_sha`

**Verdict:** ✅ Minimal, backward-compatible addition

---

### 3.3 CHANGE NOT NEEDED: Parser Plugin System

**Current State:**
Parsers are implemented per-engine in `parsers/` directory:
- `parsers/qe/` - QE parsers
- `parsers/registry.py` - Parser dispatch

**Analysis:**
The current pattern already supports adding new engine parsers:

```python
# parsers/registry.py
def get_parser(engine: str, output_type: str) -> Parser:
    if engine == "qe":
        return QE_PARSERS[output_type]
    elif engine == "lammps":
        return LAMMPS_PARSERS[output_type]  # Add this
```

**Verdict:** ❌ No core change needed, just add LAMMPS parsers

---

### 3.4 CHANGE NOT NEEDED: Units System

**Current State:**
QMatSuite uses canonical units (Å, eV, fs) in trajectory spec.

**LAMMPS Challenge:**
LAMMPS supports multiple unit systems (metal, real, lj, etc.) with different physical unit mappings.

**Solution:**
Handle units conversion **entirely within LAMMPS engine/parser**:

```python
# In lammps_parser.py
class LammpsUnitsConverter:
    """Convert LAMMPS units to canonical QMatSuite units."""
    
    def __init__(self, units: str):
        self.conversions = UNIT_CONVERSIONS[units]
    
    def convert_energy(self, value: float) -> float:
        return value * self.conversions["energy"]  # → eV
```

The parser reads the `units` setting from step parameters and converts all values before creating Frame objects.

**Verdict:** ❌ No core change needed, handle in LAMMPS parser

---

### 3.5 CHANGE NOT NEEDED: Binary Discovery

**Current State:**
Each engine has its own resolver (e.g., `vasp_resolver.py`, `qe_resolver.py`).

**LAMMPS:**
Add `lammps_resolver.py` following existing pattern.

**Verdict:** ❌ No core change needed, add resolver module

---

### 3.6 OPTIONAL ENHANCEMENT: Generic Asset Abstraction

**If we wanted to be elegant**, we could create a generalized asset system:

```python
# core/assets.py (NEW)
@dataclass
class AssetDefinition:
    """Generic asset definition."""
    name: str
    type: str  # "pseudo" | "potential" | "basis" | "model"
    files: List[Path]
    elements: List[str]
    metadata: Dict[str, Any]

class AssetManager(ABC):
    """Abstract asset management interface."""
    
    @abstractmethod
    def resolve(self, ref: str) -> AssetDefinition:
        """Resolve asset reference to definition."""
        pass
    
    @abstractmethod
    def stage(self, definition: AssetDefinition, target: Path) -> Path:
        """Stage asset files to target directory."""
        pass
    
    @abstractmethod
    def compute_digest(self, definition: AssetDefinition) -> str:
        """Compute content digest for skip logic."""
        pass
```

This would unify:
- `species_map`/`pseudo_dir` (QE)
- `potential_map` (LAMMPS)
- `basis_sets` (ORCA, future)
- `model_files` (ML potentials, future)

**However:** This is a refactoring that can happen AFTER LAMMPS MVP works. It's not a blocker.

**Verdict:** 📌 Nice to have, not required for MVP

---

## 4. Summary: Minimal Core Delta

### 4.1 Must-Have Changes (Blocking MVP)

| Change | Location | Lines Changed | Risk |
|--------|----------|---------------|------|
| Add `potential_assets_sha` field | `calculation/manifest.py` | ~5 | Very Low |

**That's it.** One optional field addition.

### 4.2 Nice-to-Have Changes (Post-MVP)

| Change | Benefit | Effort |
|--------|---------|--------|
| Generic AssetManager abstraction | Unified pseudo/potential handling | Medium |
| Parser plugin registry formalization | Cleaner parser dispatch | Low |
| Build-time package detection caching | Engine capability discovery | Low |

### 4.3 Engine-Level Implementation (No Core Changes)

All of the following can be implemented WITHOUT touching core:

| Component | Implementation Location |
|-----------|------------------------|
| `LammpsEngine` class | `engine/lammps_engine.py` (new) |
| Binary resolver | `core/engines/lammps_resolver.py` (new) |
| Input templates | `resources/calculation_templates/lammps/` (new) |
| Log parser | `parsers/lammps/log_parser.py` (new) |
| Dump parser | `parsers/lammps/dump_parser.py` (new) |
| Data file I/O | `io/lammps/data_io.py` (new) |
| Potential staging | `engine/lammps_engine.py` |
| Units converter | `parsers/lammps/units.py` (new) |

---

## 5. Constitution Compliance Verification

### 5.1 SSOT (Single Source of Truth)

| Principle | LAMMPS Compliance |
|-----------|------------------|
| `calculation.yaml` + `step.yaml` are truth | ✅ All parameters from YAML |
| No parsing old inputs for merge | ✅ Templates generate fresh |
| Manifest is bookkeeping only | ✅ Same pattern |

### 5.2 History/.analysis

| Principle | LAMMPS Compliance |
|-----------|------------------|
| Analysis objects are engine-agnostic | ✅ Use canonical Frame |
| Cache in `.analysis/` optional | ✅ Same pattern |
| Not treated as SSOT | ✅ Same pattern |

### 5.3 Manifest/Skip

| Principle | LAMMPS Compliance |
|-----------|------------------|
| Skip based on input digest | ✅ Use potential_assets_sha |
| No output hash dependency | ✅ Not using output hash |

### 5.4 ID/Slug

| Principle | LAMMPS Compliance |
|-----------|------------------|
| Internal: ULID only | ✅ Same step ULID pattern |
| Slug in resource meta only | ✅ Same pattern |

### 5.5 Parameters

| Principle | LAMMPS Compliance |
|-----------|------------------|
| A-class: strictly typed | ✅ Defined in workflows.md |
| B-class: free-form pass-through | ✅ `engine_params.lammps.*` |

---

## 6. Regression Risk Assessment

### 6.1 Impact on Existing Engines

| Engine | Risk from LAMMPS Changes |
|--------|-------------------------|
| QE | None - no shared code modified |
| VASP | None - parallel implementation |
| ORCA | None - parallel implementation |
| PySCF | None - parallel implementation |

### 6.2 Testing Strategy

| Test Category | Scope |
|---------------|-------|
| Existing engine tests | All must pass (regression) |
| Manifest field addition | Test backward compat with old manifests |
| LAMMPS-specific tests | New test suite (unit + integration) |

---

## 7. Conclusion

**LAMMPS can be integrated with essentially zero core changes.**

The only strongly-recommended change is adding `potential_assets_sha` to `ManifestStepEntry` for proper skip logic with classical potentials. This is a trivial, backward-compatible addition.

All other functionality can be implemented at the engine level by:
1. Creating new files in `engine/`, `parsers/`, `io/`
2. Adding templates in `resources/`
3. Registering new step types in workflow registry

The architecture is already general enough to accommodate LAMMPS. This is a testament to good design.

---

## 8. Recommended Implementation Order

1. **Phase 1: Core Prep** (1 day)
   - Add `potential_assets_sha` to ManifestStepEntry
   - Add regression tests

2. **Phase 2: Engine Skeleton** (2-3 days)
   - Create `LammpsEngine` class
   - Implement binary resolver
   - Register step types

3. **Phase 3: Materialize** (2-3 days)
   - Structure → LAMMPS data conversion
   - Template-based input generation
   - Potential staging

4. **Phase 4: Run** (1-2 days)
   - Binary execution
   - Output collection

5. **Phase 5: Parse** (3-4 days)
   - Log parser (thermo)
   - Dump parser (trajectory)
   - Data parser (structure)
   - Units conversion

6. **Phase 6: Integration** (2-3 days)
   - JobGraph handler
   - Manifest integration
   - End-to-end tests

