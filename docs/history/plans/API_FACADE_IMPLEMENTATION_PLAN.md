# API Façade Implementation Plan

**Version**: 1.0
**Date**: 2026-01-23
**Status**: IMPLEMENTATION SPECIFICATION
**Audience**: Auto agent (naive executor)
**Author**: Claude Opus 4.5

---

# PART A: PRINCIPLES AND RULES (PREAMBLE)

This preamble defines the binding rules that Auto MUST follow for every PR. These are not suggestions—they are LAW.

---

## A.1 Capability→DTO Minimalism

### The Problem
Today `quantumvitas.api` re-exports ~600+ kernel symbols. CLI and daemon import kernel dataclasses directly (`Step`, `Calculation`, `ResourceMeta`, etc.). This creates tight coupling:
- Kernel refactors break frontends
- Frontends depend on kernel internals (`.manifest`, `._cache`, internal methods)
- No stable contract for external tools/agents

### The Solution: Capability-Centric DTOs
DTOs are defined ONLY for capability inputs/outputs. We are NOT duplicating the kernel object graph.

**Target**: ~20-40 capability endpoints total, each with minimal DTOs.

**Rules**:
1. DTOs are "ABI structs" for stable external contract
2. CLI + daemon + Jupyter share the SAME DTO shapes
3. DTOs MUST NOT contain kernel dataclasses as fields
4. DTOs MUST NOT expose kernel internals (`.manifest`, `.resource_index`, etc.)
5. DTO design is additive-only: add fields freely, never remove/rename without 2-version deprecation

**What goes in a DTO**:
- Identifiers (ULIDs)
- Status strings
- Small scalar metadata
- References to large data (NOT the data itself)
- Timestamps (ISO strings)

**What does NOT go in a DTO**:
- Kernel objects
- Large arrays (bands, DOS, trajectories)
- Internal state (caches, locks, file handles)
- Merged/computed parameters by default

---

## A.2 ULID vs Slug

### The Problem
Prior specs used `id: str` containing slugs. Slugs are human-readable but:
- Not guaranteed unique across projects
- Can be renamed
- Conflate identity with naming

### The Solution: ULIDs for Identity

**ULID** (Universally Unique Lexicographically Sortable Identifier):
- 26-character string: `01ARZ3NDEKTSV4RRFFQ69G5FAV`
- Sortable by creation time
- Globally unique

**Rules**:
1. All DTO identity fields MUST be ULIDs:
   - `calc_id`: Calculation identity
   - `step_id`: Step identity (scoped to calculation)
   - `run_id`: Execution run identity
   - `structure_id`: Structure identity
2. `slug` is separate metadata, stored in `meta.slug` or similar
3. Selectors (user input) can be slugs, ULIDs, or patterns—resolution is API's job
4. APIs accept selectors, return ULIDs

**Example**:
```python
# User provides selector (slug)
calc = svc.calculation.get("si-scf")

# DTO returns ULID identity
calc.calc_id  # "01HX7YPVK8DQNZPMJ4GHAB1234"
calc.meta.slug  # "si-scf"
```

---

## A.3 Fail-Closed JSON Conversion

### The Problem
Prior BaseDTO had:
```python
# BAD: silent fallback
return str(obj)  # Silently converts unknown types to strings
```

This hides bugs. Unknown objects become garbage strings in JSON.

### The Solution: Fail-Closed Whitelist

**Rules**:
1. DTO serialization MUST be fail-closed
2. Unknown object types MUST raise `TypeError`
3. Only convert a strict whitelist:

| Python Type | JSON Type | Conversion |
|-------------|-----------|------------|
| `None` | `null` | Direct |
| `bool` | `boolean` | Direct |
| `int` | `number` | Direct |
| `float` | `number` | Direct; `nan`/`inf` → raise `ValueError` |
| `str` | `string` | Direct |
| `list` | `array` | Recursive (each element must be whitelisted) |
| `dict` | `object` | Recursive (keys must be str, values whitelisted) |
| `tuple` | `array` | Convert to list, then recursive |
| `datetime` | `string` | `.isoformat()` |
| `date` | `string` | `.isoformat()` |
| `Path` | `string` | `str(path)` |
| `Enum` | `string` | `.value` (must be str) |
| `UUID` | `string` | `str(uuid)` |
| `Decimal` | `string` | `str(decimal)` |

**Forbidden** (must raise TypeError):
- numpy arrays (use reference pattern instead)
- kernel objects
- arbitrary classes
- functions
- any type not in whitelist

**Implementation**:
```python
def to_json_value(obj: Any) -> JsonValue:
    """Convert to JSON-friendly value. Raises TypeError for unknown types."""
    if obj is None:
        return None
    if isinstance(obj, bool):  # Must be before int check
        return obj
    if isinstance(obj, int):
        return obj
    if isinstance(obj, float):
        if math.isnan(obj) or math.isinf(obj):
            raise ValueError(f"Cannot serialize {obj} to JSON")
        return obj
    if isinstance(obj, str):
        return obj
    if isinstance(obj, (list, tuple)):
        return [to_json_value(v) for v in obj]
    if isinstance(obj, dict):
        if not all(isinstance(k, str) for k in obj.keys()):
            raise TypeError(f"Dict keys must be strings, got {type(list(obj.keys())[0])}")
        return {k: to_json_value(v) for k, v in obj.items()}
    if isinstance(obj, datetime):
        return obj.isoformat()
    if isinstance(obj, date):
        return obj.isoformat()
    if hasattr(obj, '__fspath__'):  # Path-like
        return str(obj)
    if isinstance(obj, Enum):
        if not isinstance(obj.value, str):
            raise TypeError(f"Enum value must be str, got {type(obj.value)}")
        return obj.value
    if isinstance(obj, UUID):
        return str(obj)
    if isinstance(obj, Decimal):
        return str(obj)
    # Fail-closed: unknown type
    raise TypeError(f"Cannot serialize {type(obj).__name__} to JSON")
```

---

## A.4 Large Data by Reference

### The Problem
Analysis results can be huge:
- Band structure: 100+ k-points × 100+ bands × 2 spins = millions of floats
- DOS: thousands of energy points
- MD trajectories: thousands of frames × hundreds of atoms

Embedding in JSON:
- Explodes response size (MB+)
- Breaks daemon performance
- Not needed for most use cases (list/get operations)

### The Solution: Reference + Summary + Preview

**DTO for large data returns**:
```python
@dataclass
class AnalysisRefDTO:
    """Reference to large analysis data."""
    # Identity
    calc_id: str          # ULID
    step_id: str          # ULID
    property_name: str    # "band_structure", "dos", "trajectory"

    # Reference (how to load full data)
    artifact_path: str    # Relative path to artifact file
    artifact_format: str  # "hdf5", "npz", "json"
    artifact_sha256: str  # For verification
    artifact_size_bytes: int

    # Summary (always included, small)
    summary: dict         # Property-specific summary scalars

    # Preview (optional, small subset)
    preview: dict | None  # Downsampled/truncated data for quick viz
```

**Example for band structure**:
```json
{
    "calc_id": "01HX7YPVK8DQNZPMJ4GHAB1234",
    "step_id": "01HX7YPVK8DQNZPMJ4GHAB5678",
    "property_name": "band_structure",
    "artifact_path": ".qmatsuite/artifacts/01HX7YPVK8DQNZPMJ4GHAB1234/bands.hdf5",
    "artifact_format": "hdf5",
    "artifact_sha256": "a1b2c3...",
    "artifact_size_bytes": 2456789,
    "summary": {
        "n_bands": 120,
        "n_kpoints": 150,
        "n_spins": 1,
        "fermi_energy_ev": 6.234,
        "band_gap_ev": 0.52,
        "band_gap_type": "indirect",
        "vbm_ev": 5.98,
        "cbm_ev": 6.50
    },
    "preview": {
        "kpoint_labels": ["Γ", "X", "M", "Γ"],
        "kpoint_indices": [0, 37, 75, 149],
        "eigenvalues_sample": [[-5.2, -3.1, 0.5], ...]
    }
}
```

**Loading full data** (Jupyter-only, NOT daemon):
```python
# Get reference
ref = svc.analysis.get_band_structure("si-bands", "bands")

# Load full data (Jupyter only)
full_data = svc.analysis.load_artifact(ref)
# Returns: {"kpoints": np.array(...), "eigenvalues": np.array(...), ...}
```

**Daemon artifact download**:
```
GET /artifacts/{artifact_path}
→ Returns raw file bytes
```

---

## A.5 Structured Errors for Humans + Agents

### The Contract

Every API error MUST provide:

| Field | Type | Required | Stable | Description |
|-------|------|----------|--------|-------------|
| `type` | `str` | YES | YES | Error class name |
| `code` | `str` | YES | YES | Stable error code (from taxonomy) |
| `message` | `str` | YES | NO | Human-readable message |
| `hint` | `str` | NO | NO | Actionable suggestion |
| `context` | `dict` | NO | YES | Structured context (keys stable per code) |
| `retryable` | `bool` | YES | YES | Whether retry may succeed |
| `cause` | `dict` | NO | NO | Debug-only, NOT stable |

**Rules**:
1. Agents MUST use `code` for programmatic decisions
2. Agents MUST use `retryable` for retry logic
3. Agents MUST NOT parse `message` strings
4. Agents MUST NOT depend on `cause` (debug-only)
5. `context` keys are stable per error code (see taxonomy)

**Example**:
```json
{
    "type": "NotFoundError",
    "code": "NOT_FOUND",
    "message": "Calculation 'si-scff' not found",
    "hint": "Did you mean 'si-scf'?",
    "context": {
        "selector": "si-scff",
        "resource_type": "calculation",
        "suggestions": ["si-scf"]
    },
    "retryable": false,
    "cause": null
}
```

---

## A.6 Absolute Prohibitions (Auto MUST enforce)

| Prohibition | Detection | Action |
|-------------|-----------|--------|
| Embedding huge arrays in JSON DTO | Code review; artifact_size check | Use reference pattern |
| Fallback `str(obj)` in serialization | Grep for `str(obj)` fallback | Remove; raise TypeError |
| Kernel dataclasses crossing API | Type hints; gate tests | Map to DTO |
| Endpoint hand-serialization | Grep for `json.dumps` in daemon | Use `dto.to_dict()` |
| Frontends constructing kernel models | Gate test | Use API create methods |
| Using slug as id | DTO field audit | Use ULID; slug in meta |

---

## A.7 Testing Requirements

**Command** (Auto MUST use this exactly):
```bash
source .venv/bin/activate
python -m pytest tests/ -v --tb=short -n auto --dist=loadfile
```

**Contract tests** (MUST add for each DTO):
1. Schema test: required fields present, types correct
2. JSON-friendly test: `json.dumps(dto.to_dict())` succeeds
3. Fail-closed test: unknown types raise TypeError

**Semantic tests** (MUST add for each capability):
1. Round-trip: create → get returns consistent data
2. Update consistency: update → get reflects changes
3. Error mapping: kernel exception → correct API error code

---

# PART B: DETAILED IMPLEMENTATION PLAN

---

## PR Overview

| PR | Name | Focus | Re-exports Removed |
|----|------|-------|-------------------|
| PR0 | Skeleton + Gates | Structure, CI gates | 0 (freeze) |
| PR1 | Error Infrastructure | Errors + mapping | 0 |
| PR2 | Core DTOs + Serialization | Base DTOs, fail-closed | 0 |
| PR3 | Analysis Slice | analysis.* capabilities | ~50 |
| PR4 | Structure Slice | structure.* capabilities | ~30 |
| PR5 | Calculation Read | calculation.get/list | ~100 |
| PR6 | Calculation Write | calculation.create/update | ~50 |
| PR7 | Run APIs | run.* capabilities | ~50 |
| PR8 | Project APIs | project.* capabilities | ~30 |
| PR9 | Engine APIs | engine.* capabilities | ~20 |
| PR10 | Final Cleanup | Remove all remaining | ~270+ |

**Milestones**:
- **Gate 1**: After PR4 (analysis + structure slices proven)
- **Gate 2**: After PR6 (all read/write APIs DTO-ified)
- **Gate 3**: After PR9 (all capabilities migrated)
- **Gate 4**: After PR10 (zero re-exports, DoD complete)

---

## PR0: Skeleton + Gates

### Goal & Scope
Establish directory structure, base classes, and CI gates. Freeze re-export growth.

### Files to Create
```
src/quantumvitas/api/
├── __init__.py          # ONLY: QVService, errors, DTOs (stub)
├── service.py           # QVService class (stub)
├── types/
│   ├── __init__.py      # DTO exports
│   ├── base.py          # BaseDTO, to_json_value()
│   └── error.py         # ErrorDTO
├── errors.py            # APIError hierarchy
├── _mapping/
│   ├── __init__.py
│   ├── dto_mapping.py   # Kernel→DTO (stub)
│   └── exc_mapping.py   # Kernel exc→API error (stub)
└── _internal/
    └── __init__.py      # Internal helpers
```

### Files to Modify
- `src/quantumvitas/api/__init__.py`: Replace massive re-exports with stub exports

### Capabilities Introduced
None (stubs only)

### DTOs Introduced
- `BaseDTO` (abstract base)
- `ErrorDTO` (structure only)

### Error Codes Introduced
None yet (error classes only)

### Call-sites Migrated
None

### Re-export Deletions
**NONE** in this PR. But add gate to FREEZE growth:
```python
# Gate: No new re-exports allowed after this PR
# Current count recorded: N (measure before PR)
```

### Tests to Add
```
tests/api/
├── __init__.py
├── test_api_exports.py      # Export count gate
├── test_dto_base.py         # BaseDTO serialization
└── test_error_dto.py        # ErrorDTO structure
```

**test_api_exports.py**:
```python
def test_api_export_count_frozen():
    """Top-level api exports must not grow."""
    import quantumvitas.api as api
    exports = [x for x in dir(api) if not x.startswith('_')]
    # Record baseline on first run; fail if grows
    BASELINE = 650  # Measure actual
    assert len(exports) <= BASELINE, f"Export count grew: {len(exports)} > {BASELINE}"

def test_no_new_kernel_reexports():
    """Forbid specific kernel symbols."""
    import quantumvitas.api as api
    FORBIDDEN = ['Step', 'Calculation', 'ResourceMeta', 'EngineConfig',
                 'CalculationStepEntry', 'ResourceIndex', 'Manifest']
    for name in FORBIDDEN:
        assert not hasattr(api, name), f"Forbidden re-export: {name}"
```

### Gates/Acceptance Criteria
1. `python -m pytest tests/ -v --tb=short -n auto --dist=loadfile` passes
2. `test_api_export_count_frozen` passes with recorded baseline
3. `test_no_new_kernel_reexports` passes
4. Directory structure matches spec

### Rollback Strategy
Delete new directories, restore old `__init__.py`.

---

## PR1: Error Infrastructure

### Goal & Scope
Implement complete error hierarchy and kernel→API exception mapping.

### Files to Create
None (use stubs from PR0)

### Files to Modify
- `src/quantumvitas/api/errors.py`: Full implementation
- `src/quantumvitas/api/types/error.py`: ErrorDTO full implementation
- `src/quantumvitas/api/_mapping/exc_mapping.py`: Full mapping logic

### Capabilities Introduced
None (infrastructure only)

### DTOs Introduced/Updated
- `ErrorDTO` (complete implementation)

### Error Codes Introduced (complete taxonomy)
```python
# Resolution errors
NOT_FOUND = "NOT_FOUND"
AMBIGUOUS_SELECTOR = "AMBIGUOUS_SELECTOR"
INVALID_SELECTOR = "INVALID_SELECTOR"

# Input errors
VALIDATION_FAILED = "VALIDATION_FAILED"

# Concurrency errors
EDIT_LOCK_HELD = "EDIT_LOCK_HELD"
RUN_LOCK_HELD = "RUN_LOCK_HELD"

# Execution errors
ENGINE_EXEC_FAILED = "ENGINE_EXEC_FAILED"
ENGINE_OUTPUT_PARSE_FAILED = "ENGINE_OUTPUT_PARSE_FAILED"
ENGINE_NOT_AVAILABLE = "ENGINE_NOT_AVAILABLE"

# Configuration errors
PROJECT_SSOT_MISSING = "PROJECT_SSOT_MISSING"
MODE_MISMATCH = "MODE_MISMATCH"

# System errors
FILESYSTEM_ERROR = "FILESYSTEM_ERROR"
INTERNAL_ERROR = "INTERNAL_ERROR"
```

### Error Classes
```python
class APIError(Exception): ...
class NotFoundError(APIError): code = "NOT_FOUND"
class AmbiguousError(APIError): code = "AMBIGUOUS_SELECTOR"
class ValidationError(APIError): code = "VALIDATION_FAILED"
class ConflictError(APIError): ...  # EDIT_LOCK_HELD, RUN_LOCK_HELD
class EngineError(APIError): ...    # ENGINE_* codes
class ConfigError(APIError): ...    # PROJECT_*, MODE_*
class FilesystemError(APIError): code = "FILESYSTEM_ERROR"
class InternalError(APIError): code = "INTERNAL_ERROR"
```

### Call-sites Migrated
None yet

### Re-export Deletions
**NONE** in this PR.

### Tests to Add
```
tests/api/test_errors.py
tests/api/test_exc_mapping.py
```

**test_errors.py**:
```python
def test_error_dto_required_fields():
    """ErrorDTO has all required fields."""
    err = NotFoundError(
        message="Not found",
        context={"selector": "x", "resource_type": "calculation"}
    )
    dto = err.to_dto()
    d = dto.to_dict()
    assert d["type"] == "NotFoundError"
    assert d["code"] == "NOT_FOUND"
    assert d["message"] == "Not found"
    assert d["retryable"] is False
    assert "context" in d

def test_error_dto_json_serializable():
    """ErrorDTO.to_dict() is JSON-serializable."""
    err = NotFoundError(message="test", context={"selector": "x"})
    import json
    json.dumps(err.to_dto().to_dict())  # Must not raise
```

**test_exc_mapping.py**:
```python
def test_calculation_not_found_maps_correctly():
    """CalculationNotFoundError → NOT_FOUND."""
    from quantumvitas.core.exceptions import CalculationNotFoundError
    from quantumvitas.api._mapping.exc_mapping import map_kernel_exception

    kernel_exc = CalculationNotFoundError("si-scf")
    api_err = map_kernel_exception(kernel_exc)

    assert api_err.code == "NOT_FOUND"
    assert api_err.context["resource_type"] == "calculation"

def test_unknown_exception_maps_to_internal():
    """Unknown exceptions → INTERNAL_ERROR with trace_id."""
    api_err = map_kernel_exception(RuntimeError("unexpected"))
    assert api_err.code == "INTERNAL_ERROR"
    assert "trace_id" in api_err.context
```

### Gates/Acceptance Criteria
1. `python -m pytest tests/ -v --tb=short -n auto --dist=loadfile` passes
2. All 13 error codes have corresponding tests
3. Mapping covers all kernel exceptions listed in taxonomy

### Rollback Strategy
Revert error.py, exc_mapping.py changes.

---

## PR2: Core DTOs + Fail-Closed Serialization

### Goal & Scope
Implement core DTO classes and fail-closed serialization.

### Files to Modify
- `src/quantumvitas/api/types/base.py`: `to_json_value()` implementation
- `src/quantumvitas/api/types/__init__.py`: Export DTOs

### Files to Create
- `src/quantumvitas/api/types/common.py`: MetaDTO, StatusEnum
- `src/quantumvitas/api/types/calculation.py`: CalculationDTO, StepDTO
- `src/quantumvitas/api/types/structure.py`: StructureDTO
- `src/quantumvitas/api/types/run.py`: RunResultDTO
- `src/quantumvitas/api/types/analysis.py`: AnalysisRefDTO, AnalysisSummaryDTO

### DTOs Introduced

**MetaDTO** (embedded in all entity DTOs):
```python
@dataclass
class MetaDTO:
    slug: str | None = None       # Human-readable name
    name: str | None = None       # Display name
    description: str | None = None
    tags: list[str] | None = None
    created_at: str | None = None  # ISO datetime
    updated_at: str | None = None  # ISO datetime
```

**CalculationDTO**:
```python
@dataclass
class CalculationDTO(BaseDTO):
    # Identity (required)
    calc_id: str              # ULID
    engine: str               # Engine family
    status: str               # pending, running, completed, failed

    # Metadata (optional)
    meta: MetaDTO | None = None

    # References (optional)
    structure_id: str | None = None   # ULID
    step_ids: list[str] | None = None # List of step ULIDs

    # Minimal info (optional)
    step_count: int | None = None
    completed_step_count: int | None = None
```

**NOTE**: No `params` field. Use `svc.calculation.get_effective_params()` if needed.

**StepDTO**:
```python
@dataclass
class StepDTO(BaseDTO):
    # Identity (required)
    step_id: str              # ULID
    calc_id: str              # Parent calculation ULID
    step_type: str            # e.g., "qe_scf", "vasp_relax"
    status: str               # pending, running, completed, failed

    # Metadata (optional)
    meta: MetaDTO | None = None

    # Status details (optional)
    started_at: str | None = None
    completed_at: str | None = None
    duration_seconds: float | None = None
    exit_code: int | None = None
    error_message: str | None = None
```

**StructureDTO**:
```python
@dataclass
class StructureDTO(BaseDTO):
    # Identity (required)
    structure_id: str         # ULID
    formula: str              # Chemical formula
    num_atoms: int

    # Metadata (optional)
    meta: MetaDTO | None = None

    # Crystallographic (optional)
    space_group: str | None = None
    point_group: str | None = None
    cell_volume_ang3: float | None = None

    # Minimal lattice info (optional, for display only)
    lattice_abc: list[float] | None = None  # [a, b, c] in Angstrom
    lattice_angles: list[float] | None = None  # [alpha, beta, gamma] in degrees
```

**NOTE**: No `positions` or `species` arrays. Use `svc.structure.get_atoms()` for full data.

**RunResultDTO**:
```python
@dataclass
class RunResultDTO(BaseDTO):
    # Identity (required)
    run_id: str               # ULID (was job_id)
    calc_id: str
    status: str               # submitted, running, completed, failed, cancelled

    # Steps executed
    step_ids: list[str]

    # Timing (optional)
    started_at: str | None = None
    completed_at: str | None = None
    duration_seconds: float | None = None

    # Result (optional)
    exit_code: int | None = None
    log_path: str | None = None
    error: ErrorDTO | None = None
```

**AnalysisRefDTO** (reference to large data):
```python
@dataclass
class AnalysisRefDTO(BaseDTO):
    # Identity
    calc_id: str
    step_id: str
    property_name: str        # "band_structure", "dos", "trajectory"

    # Artifact reference
    artifact_path: str
    artifact_format: str      # "hdf5", "npz", "json"
    artifact_sha256: str
    artifact_size_bytes: int

    # Summary (always present, small)
    summary: dict[str, Any]   # Property-specific scalars

    # Preview (optional, small)
    preview: dict[str, Any] | None = None
```

**AnalysisSummaryDTO** (quick overview, no refs):
```python
@dataclass
class AnalysisSummaryDTO(BaseDTO):
    calc_id: str
    step_id: str
    converged: bool | None = None
    total_energy_ev: float | None = None
    fermi_energy_ev: float | None = None
    band_gap_ev: float | None = None
    band_gap_type: str | None = None
    total_magnetization: float | None = None
    available_properties: list[str] | None = None
```

### Serialization Implementation

**to_json_value()** in `base.py` (FAIL-CLOSED):
```python
def to_json_value(obj: Any) -> JsonValue:
    """
    Convert to JSON-friendly value.

    FAIL-CLOSED: Raises TypeError for unknown types.
    NO FALLBACK to str(obj).
    """
    if obj is None:
        return None
    if isinstance(obj, bool):  # Before int!
        return obj
    if isinstance(obj, int):
        return obj
    if isinstance(obj, float):
        if math.isnan(obj) or math.isinf(obj):
            raise ValueError(f"Cannot serialize {obj} to JSON (nan/inf)")
        return obj
    if isinstance(obj, str):
        return obj
    if isinstance(obj, (list, tuple)):
        return [to_json_value(v) for v in obj]
    if isinstance(obj, dict):
        for k in obj.keys():
            if not isinstance(k, str):
                raise TypeError(f"Dict keys must be str, got {type(k).__name__}")
        return {k: to_json_value(v) for k, v in obj.items()}
    if isinstance(obj, (datetime, date)):
        return obj.isoformat()
    if hasattr(obj, '__fspath__'):
        return str(obj)
    if isinstance(obj, Enum):
        v = obj.value
        if not isinstance(v, str):
            raise TypeError(f"Enum value must be str, got {type(v).__name__}")
        return v
    if isinstance(obj, UUID):
        return str(obj)
    if isinstance(obj, Decimal):
        return str(obj)
    # FAIL-CLOSED
    raise TypeError(
        f"Cannot serialize {type(obj).__name__} to JSON. "
        f"Use reference pattern for large data."
    )
```

### Tests to Add
```
tests/api/test_dto_serialization.py
tests/api/test_dto_calculation.py
tests/api/test_dto_structure.py
tests/api/test_dto_analysis.py
```

**test_dto_serialization.py**:
```python
def test_fail_closed_on_numpy_array():
    """Numpy arrays must raise TypeError, not silently convert."""
    import numpy as np
    from quantumvitas.api.types.base import to_json_value

    with pytest.raises(TypeError, match="Cannot serialize ndarray"):
        to_json_value(np.array([1, 2, 3]))

def test_fail_closed_on_kernel_object():
    """Kernel objects must raise TypeError."""
    from quantumvitas.core.models import Step
    from quantumvitas.api.types.base import to_json_value

    step = Step(...)  # Create somehow
    with pytest.raises(TypeError):
        to_json_value(step)

def test_nan_raises_value_error():
    """NaN must raise ValueError."""
    import math
    with pytest.raises(ValueError, match="nan"):
        to_json_value(math.nan)

def test_primitives_pass_through():
    """Primitives serialize correctly."""
    assert to_json_value(None) is None
    assert to_json_value(True) is True
    assert to_json_value(42) == 42
    assert to_json_value(3.14) == 3.14
    assert to_json_value("hello") == "hello"

def test_datetime_to_iso():
    """Datetime converts to ISO string."""
    from datetime import datetime
    dt = datetime(2026, 1, 23, 14, 30, 0)
    assert to_json_value(dt) == "2026-01-23T14:30:00"
```

**test_dto_calculation.py**:
```python
def test_calculation_dto_required_fields():
    """CalculationDTO has required ULID fields."""
    dto = CalculationDTO(
        calc_id="01HX7YPVK8DQNZPMJ4GHAB1234",
        engine="qe",
        status="completed"
    )
    d = dto.to_dict()
    assert d["calc_id"] == "01HX7YPVK8DQNZPMJ4GHAB1234"
    assert d["engine"] == "qe"
    assert d["status"] == "completed"

def test_calculation_dto_no_params_field():
    """CalculationDTO must NOT have params field."""
    dto = CalculationDTO(calc_id="x", engine="qe", status="pending")
    d = dto.to_dict()
    assert "params" not in d
```

### Call-sites Migrated
None yet

### Re-export Deletions
**NONE** in this PR.

### Gates/Acceptance Criteria
1. `python -m pytest tests/ -v --tb=short -n auto --dist=loadfile` passes
2. All DTOs have schema tests
3. `test_fail_closed_on_numpy_array` passes
4. No DTO has `params` as default field

### Rollback Strategy
Revert types/ changes.

---

## PR3: Analysis Slice (First Vertical)

### Goal & Scope
Implement analysis capabilities end-to-end: API → DTO → daemon response.
Proves the full pipeline works.

### Files to Modify
- `src/quantumvitas/api/service.py`: Add `svc.analysis.*` domain
- `src/quantumvitas/api/_mapping/dto_mapping.py`: Add analysis mappings
- `src/quantumvitas/daemon/endpoints/analysis.py`: Use DTO responses

### Capabilities Introduced
```python
svc.analysis.get_summary(calc_selector, step_selector) -> AnalysisSummaryDTO
svc.analysis.list_properties(calc_selector, step_selector) -> list[str]
svc.analysis.get_property_ref(calc_selector, step_selector, property_name) -> AnalysisRefDTO
svc.analysis.load_artifact(ref: AnalysisRefDTO) -> dict  # Jupyter-only, returns numpy
```

### DTOs Used
- `AnalysisSummaryDTO`
- `AnalysisRefDTO`

### Daemon Endpoints Updated
- `GET /api/calculations/{calc}/steps/{step}/analysis/summary`
- `GET /api/calculations/{calc}/steps/{step}/analysis/properties`
- `GET /api/calculations/{calc}/steps/{step}/analysis/properties/{name}`

**Before** (hand-serialization):
```python
@router.get("/analysis/summary")
def get_analysis_summary(calc: str, step: str):
    result = kernel_get_analysis(calc, step)
    return {
        "converged": result.converged,
        "energy": result.total_energy,
        # Hand-rolled, inconsistent
    }
```

**After** (DTO response):
```python
@router.get("/analysis/summary")
def get_analysis_summary(calc: str, step: str) -> dict:
    try:
        dto = svc.analysis.get_summary(calc, step)
        return {"data": dto.to_dict()}
    except APIError as e:
        return {"error": e.to_dto().to_dict()}
```

### Call-sites Migrated
1. `src/quantumvitas/daemon/endpoints/analysis.py`
2. `src/quantumvitas/cli/commands/analysis.py` (if exists)

### Re-export Deletions (PR3)

Remove from `api/__init__.py`:
```python
# Analysis-related re-exports to remove (~50 symbols)
- AnalysisResult
- BandStructure
- DOS
- BandStructureAnalyzer
- DOSAnalyzer
- TrajectoryAnalyzer
- get_analysis_summary
- parse_band_structure
- parse_dos
- ... (list all analysis-related exports)
```

**Grep command to find them**:
```bash
grep -E "^from quantumvitas\.(analysis|parsers\.analysis)" src/quantumvitas/api/__init__.py
```

### Tests to Add
```
tests/api/test_analysis_capabilities.py
tests/api/test_analysis_ref_pattern.py
```

**test_analysis_capabilities.py**:
```python
def test_get_summary_returns_dto(svc, completed_calc):
    """get_summary returns AnalysisSummaryDTO."""
    summary = svc.analysis.get_summary(completed_calc, "scf")
    assert isinstance(summary, AnalysisSummaryDTO)
    assert summary.calc_id is not None

def test_get_property_ref_no_embedded_arrays(svc, completed_calc):
    """Property ref must not embed full arrays."""
    ref = svc.analysis.get_property_ref(completed_calc, "bands", "band_structure")
    d = ref.to_dict()
    # Summary has scalars only
    assert isinstance(d["summary"]["n_bands"], int)
    # No eigenvalues array in main response
    assert "eigenvalues" not in d
    assert "eigenvalues" not in d.get("summary", {})
```

### Gates/Acceptance Criteria
1. `python -m pytest tests/ -v --tb=short -n auto --dist=loadfile` passes
2. `grep -c "AnalysisResult" src/quantumvitas/api/__init__.py` returns 0
3. Daemon analysis endpoints return `{"data": {...}}` with DTO shape
4. No numpy arrays in analysis DTO `to_dict()` output

### Rollback Strategy
Revert analysis.py endpoints, remove new capabilities.

---

## PR4: Structure Slice (Second Vertical)

### Goal & Scope
Implement structure capabilities. Complete Gate 1.

### Capabilities Introduced
```python
svc.structure.get(selector) -> StructureDTO
svc.structure.list(project_selector=None) -> list[StructureDTO]
svc.structure.get_atoms(selector) -> dict  # Jupyter-only, full coords
svc.structure.visualize(selector, format="json") -> dict  # For viz tools
```

### DTOs Used
- `StructureDTO`

### Daemon Endpoints Updated
- `GET /api/structures/{id}`
- `GET /api/structures`

### Call-sites Migrated
1. `src/quantumvitas/daemon/endpoints/structure.py`
2. `src/quantumvitas/cli/commands/structure.py`

### Re-export Deletions (PR4)

Remove from `api/__init__.py`:
```python
# Structure-related re-exports to remove (~30 symbols)
- Structure
- Atoms
- Lattice
- Cell
- StructureBuilder
- read_structure
- write_structure
- convert_structure
- ... (list all structure-related exports)
```

### Tests to Add
```
tests/api/test_structure_capabilities.py
```

**test_structure_capabilities.py**:
```python
def test_structure_dto_no_positions(svc, structure_id):
    """StructureDTO must not have positions array."""
    dto = svc.structure.get(structure_id)
    d = dto.to_dict()
    assert "positions" not in d
    assert "species" not in d  # Full species array
    assert d["num_atoms"] == 8  # Summary only
```

### Gates/Acceptance Criteria
1. Tests pass
2. Structure re-exports removed
3. StructureDTO has no coordinate arrays

### Rollback Strategy
Revert structure endpoints and capabilities.

---

## GATE 1 CHECKPOINT

**After PR4, verify**:
- [ ] Analysis + structure vertical slices complete
- [ ] Reference pattern proven for large data
- [ ] Daemon endpoints use DTO responses
- [ ] ~80 re-exports removed

**Command**:
```bash
python -m pytest tests/ -v --tb=short -n auto --dist=loadfile
grep -c "^from quantumvitas\.(core|calculation|analysis|structure)" src/quantumvitas/api/__init__.py
# Should be significantly reduced
```

---

## PR5: Calculation Read APIs

### Goal & Scope
Convert calculation get/list to DTOs.

### Capabilities Introduced
```python
svc.calculation.get(selector) -> CalculationDTO
svc.calculation.list(project_selector=None, status=None) -> list[CalculationDTO]
svc.calculation.get_step(calc_selector, step_selector) -> StepDTO
svc.calculation.list_steps(calc_selector) -> list[StepDTO]
svc.calculation.get_effective_params(calc_selector) -> dict  # Merged params
```

### DTOs Used
- `CalculationDTO`
- `StepDTO`

### Call-sites Migrated
1. `src/quantumvitas/daemon/endpoints/calculation.py` (GET endpoints)
2. `src/quantumvitas/cli/commands/calc.py` (show, list commands)

### Re-export Deletions (PR5)

Remove from `api/__init__.py`:
```python
# Calculation read re-exports (~100 symbols)
- Calculation
- CalculationStepEntry
- Step
- StepSpec
- StepResult
- get_calculation
- list_calculations
- resolve_calculation
- load_calculation
- ... (all read-related)
```

### Tests to Add
```
tests/api/test_calculation_read.py
```

### Gates/Acceptance Criteria
1. Tests pass
2. `grep "^from quantumvitas.calculation import" api/__init__.py` reduced significantly
3. CLI `show` command works with DTO

---

## PR6: Calculation Write APIs

### Goal & Scope
Convert calculation create/update/delete to DTOs.

### Capabilities Introduced
```python
svc.calculation.create(engine, name=None, structure_selector=None, **kwargs) -> CalculationDTO
svc.calculation.update_meta(selector, **meta_kwargs) -> CalculationDTO
svc.calculation.update_step_params(calc_selector, step_selector, params: dict) -> StepDTO
svc.calculation.duplicate(selector, new_name=None) -> CalculationDTO
svc.calculation.delete(selector) -> None
svc.calculation.add_step(calc_selector, step_type, **params) -> StepDTO
svc.calculation.remove_step(calc_selector, step_selector) -> None
```

### Call-sites Migrated
1. `src/quantumvitas/daemon/endpoints/calculation.py` (POST/PUT/DELETE)
2. `src/quantumvitas/cli/commands/calc.py` (create, update, delete)

### Re-export Deletions (PR6)
```python
# Calculation write re-exports (~50 symbols)
- create_calculation
- update_calculation
- delete_calculation
- CalculationBuilder
- ... (all write-related)
```

### Tests to Add
```
tests/api/test_calculation_write.py
```

---

## GATE 2 CHECKPOINT

**After PR6, verify**:
- [ ] All read/write calculation APIs use DTOs
- [ ] CLI calc commands use API
- [ ] ~230 re-exports removed total

---

## PR7: Run APIs

### Goal & Scope
Convert run/execution to DTOs.

### Capabilities Introduced
```python
svc.run.run_calculation(calc_selector, steps=None) -> RunResultDTO
svc.run.run_step(calc_selector, step_selector) -> RunResultDTO
svc.run.get_status(run_id) -> RunResultDTO
svc.run.cancel(run_id) -> RunResultDTO
svc.run.list_runs(calc_selector=None, status=None) -> list[RunResultDTO]
```

### DTOs Used
- `RunResultDTO` (with `run_id` ULID, not `job_id`)

### Call-sites Migrated
1. `src/quantumvitas/daemon/endpoints/run.py`
2. `src/quantumvitas/cli/commands/run.py`

### Re-export Deletions (PR7)
```python
# Run-related re-exports (~50 symbols)
- run_calculation
- run_step
- JobExecutor
- JobResult
- JobStatus
- ... (all execution-related)
```

---

## PR8: Project APIs

### Goal & Scope
Convert project operations to DTOs.

### Capabilities Introduced
```python
svc.project.get_config() -> dict
svc.project.update_config(patch: dict) -> dict
svc.project.get_species_map() -> dict
svc.project.get_potential_map() -> dict
svc.project.list_calculations() -> list[CalculationDTO]
```

### DTOs Introduced
- `ProjectConfigDTO` (optional, may use plain dict)

### Call-sites Migrated
1. `src/quantumvitas/daemon/endpoints/project.py`
2. `src/quantumvitas/cli/commands/project.py`

### Re-export Deletions (PR8)
```python
# Project re-exports (~30 symbols)
- ProjectConfig
- load_project
- save_project
- ... (all project-related)
```

---

## PR9: Engine APIs

### Goal & Scope
Convert engine discovery to DTOs.

### Capabilities Introduced
```python
svc.engine.list() -> list[dict]
svc.engine.get_info(engine_name) -> dict
svc.engine.list_step_types(engine_name=None) -> list[dict]
svc.engine.validate_installation(engine_name) -> dict
```

### Call-sites Migrated
1. `src/quantumvitas/daemon/endpoints/engine.py`
2. `src/quantumvitas/cli/commands/engine.py`

### Re-export Deletions (PR9)
```python
# Engine re-exports (~20 symbols)
- EngineConfig
- DriverRegistry (should be internal)
- get_engine
- list_engines
- ...
```

---

## GATE 3 CHECKPOINT

**After PR9, verify**:
- [ ] All capabilities migrated to DTOs
- [ ] All daemon endpoints use DTO responses
- [ ] All CLI commands use API
- [ ] ~380 re-exports removed

---

## PR10: Final Cleanup (Zero Re-exports)

### Goal & Scope
Remove ALL remaining re-exports. Achieve Definition of Done.

### Files to Modify
- `src/quantumvitas/api/__init__.py`: Strip to minimal exports

### Final `__init__.py` State
```python
"""
QuantumVITAS API - Stable public interface.

This module exports ONLY:
- QVService: The service entry point
- API-owned errors
- API-owned DTO types
"""

from quantumvitas.api.service import QVService

# Errors
from quantumvitas.api.errors import (
    APIError,
    NotFoundError,
    AmbiguousError,
    ValidationError,
    ConflictError,
    EngineError,
    ConfigError,
    FilesystemError,
    InternalError,
)

# DTOs
from quantumvitas.api.types import (
    ErrorDTO,
    MetaDTO,
    CalculationDTO,
    StepDTO,
    StructureDTO,
    RunResultDTO,
    AnalysisRefDTO,
    AnalysisSummaryDTO,
)

# Error codes (constants)
from quantumvitas.api.errors import (
    NOT_FOUND,
    AMBIGUOUS_SELECTOR,
    INVALID_SELECTOR,
    VALIDATION_FAILED,
    EDIT_LOCK_HELD,
    RUN_LOCK_HELD,
    ENGINE_EXEC_FAILED,
    ENGINE_OUTPUT_PARSE_FAILED,
    ENGINE_NOT_AVAILABLE,
    PROJECT_SSOT_MISSING,
    MODE_MISMATCH,
    FILESYSTEM_ERROR,
    INTERNAL_ERROR,
)

__all__ = [
    # Service
    "QVService",
    # Errors
    "APIError",
    "NotFoundError",
    "AmbiguousError",
    "ValidationError",
    "ConflictError",
    "EngineError",
    "ConfigError",
    "FilesystemError",
    "InternalError",
    # DTOs
    "ErrorDTO",
    "MetaDTO",
    "CalculationDTO",
    "StepDTO",
    "StructureDTO",
    "RunResultDTO",
    "AnalysisRefDTO",
    "AnalysisSummaryDTO",
    # Error codes
    "NOT_FOUND",
    "AMBIGUOUS_SELECTOR",
    "INVALID_SELECTOR",
    "VALIDATION_FAILED",
    "EDIT_LOCK_HELD",
    "RUN_LOCK_HELD",
    "ENGINE_EXEC_FAILED",
    "ENGINE_OUTPUT_PARSE_FAILED",
    "ENGINE_NOT_AVAILABLE",
    "PROJECT_SSOT_MISSING",
    "MODE_MISMATCH",
    "FILESYSTEM_ERROR",
    "INTERNAL_ERROR",
]

__version__ = "..."
```

### Re-export Deletions (PR10)
**ALL REMAINING** (~270+ symbols)

List by grepping current state:
```bash
grep "^from quantumvitas\." src/quantumvitas/api/__init__.py | grep -v "api\."
# Remove ALL of these
```

### Tests to Add
```
tests/api/test_public_surface_final.py
```

**test_public_surface_final.py**:
```python
def test_export_count_final():
    """Final export count must be ≤30."""
    import quantumvitas.api as api
    exports = [x for x in api.__all__]
    assert len(exports) <= 30, f"Too many exports: {len(exports)}"

def test_no_kernel_symbols():
    """No kernel symbols in api namespace."""
    import quantumvitas.api as api
    FORBIDDEN = [
        'Step', 'Calculation', 'CalculationStepEntry', 'ResourceMeta',
        'EngineConfig', 'ResourceIndex', 'Manifest', 'StepSpec', 'StepResult',
        'Structure', 'Atoms', 'Lattice', 'Cell', 'BandStructure', 'DOS',
        'JobExecutor', 'JobResult', 'ProjectConfig', 'DriverRegistry',
    ]
    for name in FORBIDDEN:
        assert not hasattr(api, name), f"Forbidden symbol: {name}"

def test_all_exports_are_api_owned():
    """Every export must be from quantumvitas.api.*"""
    import quantumvitas.api as api
    import inspect

    for name in api.__all__:
        obj = getattr(api, name)
        if inspect.isclass(obj) or inspect.isfunction(obj):
            module = obj.__module__
            assert module.startswith("quantumvitas.api"), \
                f"{name} is from {module}, not api.*"
```

### Gates/Acceptance Criteria
1. `python -m pytest tests/ -v --tb=short -n auto --dist=loadfile` passes
2. `test_export_count_final` passes (≤30 exports)
3. `test_no_kernel_symbols` passes
4. `test_all_exports_are_api_owned` passes

### Rollback Strategy
Re-add necessary re-exports if critical breakage found.

---

## GATE 4 (FINAL): Definition of Done

**Checklist**:

- [ ] `quantumvitas.api` top-level exports ONLY:
  - [ ] `QVService`
  - [ ] API-owned errors (9 classes + 13 code constants)
  - [ ] API-owned DTOs (8 classes)

- [ ] ZERO kernel types exposed:
  ```bash
  grep "^from quantumvitas\.(core|calculation|drivers|execution|workflow)" \
    src/quantumvitas/api/__init__.py
  # Expected: 0 matches
  ```

- [ ] ZERO re-export symbols remain:
  ```bash
  grep -c "^from quantumvitas\." src/quantumvitas/api/__init__.py | \
    grep -v "api\."
  # Expected: 0 (only api.* imports)
  ```

- [ ] Frontends NEVER import kernel:
  ```bash
  grep -rn "^from quantumvitas\.(core|calculation|drivers|execution|workflow)" \
    src/quantumvitas/cli/ src/quantumvitas/daemon/ src/quantumvitas/frontends/
  # Expected: 0 matches
  ```

- [ ] Frontends NEVER instantiate kernel models:
  ```bash
  grep -rn "Calculation\(\|Step\(\|Structure\(" \
    src/quantumvitas/cli/ src/quantumvitas/daemon/
  # Expected: 0 direct instantiations (only via svc.*)
  ```

- [ ] Daemon endpoints NEVER hand-serialize:
  ```bash
  grep -rn "json\.dumps\|__dict__" src/quantumvitas/daemon/endpoints/
  # Expected: 0 (only dto.to_dict())
  ```

- [ ] No huge arrays in DTO:
  ```bash
  grep -rn "eigenvalues\|positions\|trajectory" src/quantumvitas/api/types/
  # Expected: only in preview/summary, not as main fields
  ```

- [ ] All tests pass:
  ```bash
  python -m pytest tests/ -v --tb=short -n auto --dist=loadfile
  ```

---

# PART C: APPENDICES

## Appendix A: ULID Generation

```python
# Use ulid-py library
import ulid

def generate_id() -> str:
    """Generate ULID for new entity."""
    return str(ulid.new())
```

Install: `pip install ulid-py`

## Appendix B: Kernel Exception → API Error Mapping

| Kernel Exception | API Error | Code |
|------------------|-----------|------|
| `CalculationNotFoundError` | `NotFoundError` | `NOT_FOUND` |
| `StepNotFoundError` | `NotFoundError` | `NOT_FOUND` |
| `StructureNotFoundError` | `NotFoundError` | `NOT_FOUND` |
| `AmbiguousSelectorError` | `AmbiguousError` | `AMBIGUOUS_SELECTOR` |
| `ValidationError` | `ValidationError` | `VALIDATION_FAILED` |
| `ValueError` (on params) | `ValidationError` | `VALIDATION_FAILED` |
| `EditLockError` | `ConflictError` | `EDIT_LOCK_HELD` |
| `RunLockError` | `ConflictError` | `RUN_LOCK_HELD` |
| `EngineExecutionError` | `EngineError` | `ENGINE_EXEC_FAILED` |
| `OutputParseError` | `EngineError` | `ENGINE_OUTPUT_PARSE_FAILED` |
| `EngineNotFoundError` | `EngineError` | `ENGINE_NOT_AVAILABLE` |
| `MissingSpeciesMapError` | `ConfigError` | `PROJECT_SSOT_MISSING` |
| `ModeMismatchError` | `ConfigError` | `MODE_MISMATCH` |
| `PermissionError` | `FilesystemError` | `FILESYSTEM_ERROR` |
| `OSError` | `FilesystemError` | `FILESYSTEM_ERROR` |
| `Exception` (unknown) | `InternalError` | `INTERNAL_ERROR` |

## Appendix C: Response Helper for Daemon

```python
# src/quantumvitas/api/_internal/response.py

from typing import TypeVar
from quantumvitas.api.types.base import BaseDTO
from quantumvitas.api.errors import APIError

T = TypeVar("T", bound=BaseDTO)

def success_response(dto: T) -> dict:
    """Standard success response."""
    return {"data": dto.to_dict(), "error": None}

def error_response(err: APIError) -> dict:
    """Standard error response."""
    return {"data": None, "error": err.to_dto().to_dict()}

def list_response(dtos: list[T]) -> dict:
    """Standard list response."""
    return {"data": [d.to_dict() for d in dtos], "error": None}
```

## Appendix D: CI Gate Script

```bash
#!/bin/bash
# scripts/ci_api_gates.sh

set -e

echo "=== API Surface Gates ==="

# Gate 1: Export count
EXPORT_COUNT=$(python -c "
import quantumvitas.api as api
exports = [x for x in api.__all__]
print(len(exports))
")
echo "Export count: $EXPORT_COUNT"
if [ "$EXPORT_COUNT" -gt 30 ]; then
    echo "FAIL: Too many exports ($EXPORT_COUNT > 30)"
    exit 1
fi

# Gate 2: No kernel re-exports
KERNEL_REEXPORTS=$(grep -c "^from quantumvitas\.\(core\|calculation\|drivers\)" \
    src/quantumvitas/api/__init__.py || true)
echo "Kernel re-exports: $KERNEL_REEXPORTS"
if [ "$KERNEL_REEXPORTS" -gt 0 ]; then
    echo "FAIL: Found kernel re-exports"
    exit 1
fi

# Gate 3: No frontend kernel imports
FRONTEND_IMPORTS=$(grep -rn "^from quantumvitas\.\(core\|calculation\|drivers\)" \
    src/quantumvitas/cli/ src/quantumvitas/daemon/ 2>/dev/null | wc -l || true)
echo "Frontend kernel imports: $FRONTEND_IMPORTS"
if [ "$FRONTEND_IMPORTS" -gt 0 ]; then
    echo "FAIL: Frontends import kernel"
    exit 1
fi

# Gate 4: No daemon hand-serialization
HAND_SERIAL=$(grep -rn "json\.dumps.*__dict__" \
    src/quantumvitas/daemon/ 2>/dev/null | wc -l || true)
echo "Hand-serialization: $HAND_SERIAL"
if [ "$HAND_SERIAL" -gt 0 ]; then
    echo "FAIL: Daemon hand-serializes"
    exit 1
fi

echo "=== All gates passed ==="
```

---

## Changelog

| Version | Date | Changes |
|---------|------|---------|
| 1.0 | 2026-01-23 | Initial plan with ULID, fail-closed, ref pattern |
