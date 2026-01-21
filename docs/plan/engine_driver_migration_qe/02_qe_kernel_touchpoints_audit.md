# QE Kernel Touchpoints Audit

> This document identifies all places where the kernel (engine-agnostic code) has QE-specific logic, defaults, or special-casing that must be removed or generalized.

## Definition: Kernel vs Driver

**Kernel**: Engine-agnostic infrastructure that should work with any engine via DriverRegistry
- `src/quantumvitas/calculation/` (except engine-specific files)
- `src/quantumvitas/core/` (except `core/engines/`)
- `src/quantumvitas/execution/` (except engine handlers/recipes)
- `src/quantumvitas/workflow/`
- `src/quantumvitas/presets/` (core infrastructure)

**Driver**: Engine-specific code that should live under `src/quantumvitas/drivers/<engine>/`

---

## 1. Critical Kernel Touchpoints (Breaking Changes)

### 1.1 `calculation/step.py:28` - DEFAULT ENGINE
```python
@dataclass
class Step:
    ...
    engine: str = "qe"  # <-- QE IS THE DEFAULT ENGINE
```

**Impact**: HIGH - Every step without explicit engine uses QE
**Migration Strategy**:
- Change to `engine: str = None` (no default)
- Or `engine: str = ""` with validation requiring explicit engine
- Calculation creation must specify engine explicitly

**Compatibility Concern**:
- Existing step.yaml files without `engine` field will break
- Need migration path for legacy calculations

### 1.2 `calculation/runner.py:523` - ENGINE FAMILY DEFAULT
```python
if not engine_family:
    engine_family = "qe"  # Default
```

**Impact**: HIGH - Calculation execution defaults to QE
**Migration Strategy**:
- Require explicit engine_family in calculation.yaml
- Remove fallback after migration period
- Add validation error if engine_family missing

### 1.3 `calculation/runner.py:631` - JOB ENGINE DEFAULT
```python
engine_name = job.engine or "qe"
```

**Impact**: MEDIUM - Job execution defaults to QE
**Migration Strategy**:
- Ensure Job always has engine set during materialization
- Remove `or "qe"` fallback

### 1.4 `calculation/runner.py:735,761` - HISTORY ENGINE
```python
engine="qe",  # in create_run_revision
engine="qe",  # in RunStartedEvent
```

**Impact**: LOW - Only affects history recording
**Migration Strategy**:
- Pass actual engine from calculation
- Get engine from step/calculation context

---

## 2. Engine Family Detection (calc_identity.py)

### 2.1 `core/calc_identity.py:103-107` - W90 → QE MAPPING
```python
# Special case: Wannier90 steps are part of QE family toolchain
if engine == "w90" or step_type in ("w90_run", "w90_preproc"):
    engine = "qe"
```

**Impact**: MEDIUM - Affects engine family inference
**Migration Strategy**:
- W90 driver should declare its engine family relationship
- DriverRegistry should handle W90↔QE relationship
- Remove hardcoded mapping from kernel

### 2.2 `core/calc_identity.py:132` - STRUCTURE KIND DEFAULT
```python
return "periodic"  # Default for qe, w90, etc.
```

**Impact**: LOW - Infers periodic for non-pyscf engines
**Migration Strategy**:
- Move structure_kind inference to driver capability
- Each driver declares default structure_kind
- Remove hardcoded mapping

---

## 3. Workflow Registry (registry.py)

### 3.1 QE Step Type Definitions (lines 166-626)
```python
_STEP_TYPES: Dict[str, StepTypeSpec] = {
    "qe_scf": StepTypeSpec(..., engine="qe", ...),
    "qe_nscf": StepTypeSpec(..., engine="qe", ...),
    # ... ~25 QE step types
}
```

**Impact**: HIGH - Step type registry has QE hardcoded
**Migration Strategy**:
- Move QE step type specs to `drivers/qe/step_types.py`
- Driver registers its step types with registry on load
- Registry becomes engine-agnostic

### 3.2 W90 Steps with QE Engine (lines 337-369)
```python
"w90_preproc": StepTypeSpec(
    ...
    engine="qe",  # Legacy: tests expect "qe" for backward compatibility
    ...
),
"w90_run": StepTypeSpec(
    ...
    engine="qe",  # Legacy: tests expect "qe" for backward compatibility
    ...
),
```

**Impact**: MEDIUM - W90 steps claim QE engine
**Migration Strategy**:
- W90 driver owns these step types
- Update tests to expect `engine="w90"`
- Add compatibility shim in W90 driver

### 3.3 Step Type Aliases (line 819)
```python
STEP_TYPE_ALIASES = {
    "vc-relax": "relax",
    "qe_vc_relax": "qe_relax",  # <-- QE-specific alias
    ...
}
```

**Impact**: LOW - Only affects step type normalization
**Migration Strategy**:
- Move QE-specific aliases to driver bundle
- Keep only engine-agnostic aliases in kernel

---

## 4. Execution Layer

### 4.1 `execution/handlers.py:403-413` - QE FALLBACK
```python
# Legacy fallback: ensure QE is always available
if "qe" not in handler_map:
    handler_map["qe"] = make_handler(qe_step_handler)
```

**Impact**: MEDIUM - Execution has QE fallback
**Migration Strategy**:
- Remove fallback after driver registration is reliable
- Rely entirely on DriverRegistry for handler lookup

### 4.2 `execution/recipes.py` - QERecipe in kernel
**Impact**: LOW - Recipe class is in kernel but registered via driver
**Migration Strategy**:
- Move QERecipe to `drivers/qe/recipe.py`
- Update driver to return recipe from new location

---

## 5. I/O Layer

### 5.1 `io/__init__.py` - QE Type Exports
```python
from .model import QEModule, QECardType, QENamelist, QECard, QEInput
from .parser.qe_parser import QEInputParser
from .generator.qe_generator import QEInputGenerator
from .structure_io import structure_from_qe_input

__all__ = [
    "QEModule", "QECardType", "QENamelist", "QECard", "QEInput",
    "QEInputParser", "QEInputGenerator",
    "structure_from_qe_input",
]
```

**Impact**: MEDIUM - Public API exposes QE types
**Migration Strategy**:
- Move QE models/parsers to driver bundle
- Re-export from `io/__init__.py` for backward compatibility
- Deprecate direct kernel imports in future version

### 5.2 `io/structure_io.py` - QE-Specific Function
```python
def structure_from_qe_input(qe_input: QEInput) -> Structure:
    ...
```

**Impact**: LOW - Utility function in kernel
**Migration Strategy**:
- Move to `drivers/qe/io/structure_io.py`
- Re-export from kernel for compatibility

---

## 6. Core Infrastructure

### 6.1 `core/pseudo.py` - QE-Centric Implementation
```python
def ensure_qe_pseudos(...) -> PseudoResolutionResult:
    ...
    qe_input = QEInputParser.parse_file(input_file)
    atomic_species = qe_input.get_card(QECardType.ATOMIC_SPECIES)
    ...
```

**Impact**: HIGH - Pseudo handling is QE-specific
**Migration Strategy**:
- Create engine-agnostic pseudo interface
- Move QE-specific implementation to driver
- Each driver provides pseudo resolution logic

### 6.2 `core/settings.py` - QE Settings Section
```python
class QESettings:
    bin_dir: Optional[str] = None
```

**Impact**: LOW - Settings has QE section
**Migration Strategy**:
- Keep QE settings in core settings (user-facing config)
- Settings remain engine-specific (per-engine config)
- This is acceptable in kernel

### 6.3 `core/paths.py` - QE Engines Directory
```python
def home_qe_engines_dir() -> Path:
    return Path.home() / ".qmatsuite" / "engines" / "qe"
```

**Impact**: LOW - Path helper is QE-specific
**Migration Strategy**:
- Generalize to `home_engine_dir(engine_name: str)`
- Move QE-specific logic to driver

---

## 7. History/Provenance

### 7.1 `history/run_revision.py` - QE Engine Default
Hardcoded `engine="qe"` in run revision creation.

**Migration Strategy**:
- Pass actual engine from execution context
- No hardcoded defaults

---

## 8. Presets

### 8.1 Preset-Engine Coupling
Presets may have QE-specific parameter mappings.

**Migration Strategy**:
- Move engine-specific preset mappings to driver bundles
- Keep preset infrastructure engine-agnostic

---

## Summary: Required Kernel Changes

### High Priority (Blocking)
| File | Line | Change | Risk |
|------|------|--------|------|
| `calculation/step.py` | 28 | Remove `engine="qe"` default | HIGH |
| `calculation/runner.py` | 523 | Remove `engine_family = "qe"` fallback | HIGH |
| `workflow/registry.py` | 166-626 | Move QE step types to driver | HIGH |
| `core/pseudo.py` | * | Generalize pseudo interface | HIGH |

### Medium Priority (Important)
| File | Line | Change | Risk |
|------|------|--------|------|
| `calculation/runner.py` | 631 | Remove `or "qe"` fallback | MEDIUM |
| `core/calc_identity.py` | 103-107 | Remove W90→QE mapping | MEDIUM |
| `execution/handlers.py` | 403-413 | Remove QE fallback | MEDIUM |
| `io/__init__.py` | * | Move QE types, add re-exports | MEDIUM |

### Low Priority (Polish)
| File | Line | Change | Risk |
|------|------|--------|------|
| `calculation/runner.py` | 735,761 | Pass actual engine to history | LOW |
| `workflow/registry.py` | 819 | Move QE aliases to driver | LOW |
| `core/paths.py` | * | Generalize path helpers | LOW |
| `core/calc_identity.py` | 132 | Move structure_kind to driver | LOW |

---

## Compatibility Guarantees

### Must Maintain
1. Existing `calculation.yaml` files with `engine_family: qe` must work
2. Existing `step.yaml` files with `step_type: qe_scf` must work
3. Public API functions returning QE types must continue to work
4. IR → QE compilation must produce identical output

### May Break (With Migration Path)
1. Step creation without explicit engine (add engine to constructor)
2. Direct imports of QE modules from kernel (update import paths)
3. Custom code relying on QE defaults (add explicit engine)

### Will Not Support
1. Undocumented internal APIs that depend on QE defaults
2. Direct file path assumptions about QE code locations
