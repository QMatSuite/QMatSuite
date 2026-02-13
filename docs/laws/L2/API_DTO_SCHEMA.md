# API DTO Schema

**Version**: 2.0
**Date**: 2026-01-23
**Status**: SPECIFICATION (binding)
**Audience**: Auto agent, human reviewers

---

## 1. Overview

This document defines the Data Transfer Objects (DTOs) for `quantumvitas.api`. All DTOs MUST follow these rules.

---

## 2. General Rules

### 2.1 ULID Identity

All entity DTOs use ULIDs for identity:

| Field | Type | Description |
|-------|------|-------------|
| `calc_id` | `str` | Calculation ULID |
| `step_id` | `str` | Step ULID |
| `run_id` | `str` | Run execution ULID |
| `structure_id` | `str` | Structure ULID |

**Slug** is metadata, NOT identity. Stored in `meta.slug`.

### 2.2 Fail-Closed JSON Conversion

**Whitelist** (ONLY these types allowed):

| Python Type | JSON Type | Conversion |
|-------------|-----------|------------|
| `None` | `null` | Direct |
| `bool` | `boolean` | Direct |
| `int` | `number` | Direct |
| `float` | `number` | Direct; `nan`/`inf` → `ValueError` |
| `str` | `string` | Direct |
| `list`, `tuple` | `array` | Recursive |
| `dict` | `object` | Keys must be `str`, recursive |
| `datetime`, `date` | `string` | `.isoformat()` |
| `Path` | `string` | `str(path)` |
| `Enum` | `string` | `.value` (must be str) |
| `UUID` | `string` | `str(uuid)` |
| `Decimal` | `string` | `str(decimal)` |

**FORBIDDEN** (raise `TypeError`):
- numpy arrays → Use reference pattern
- Kernel objects → Map to DTO
- Arbitrary classes → Not allowed
- Functions → Not allowed

**NO FALLBACK**: No `str(obj)` fallback. Unknown types MUST raise `TypeError`.

### 2.3 Stability Rules

1. **Additive-only**: New fields MAY be added
2. **No removal**: Fields MUST NOT be removed without 2-version deprecation
3. **No rename**: Use add-new + deprecate-old pattern
4. **Required stays required**: Once required, always required

---

## 3. Implementation

### 3.1 to_json_value() Function

```python
import math
from datetime import datetime, date
from decimal import Decimal
from enum import Enum
from pathlib import Path
from typing import Any
from uuid import UUID

JsonValue = None | bool | int | float | str | list | dict

def to_json_value(obj: Any) -> JsonValue:
    """
    Convert to JSON-friendly value. FAIL-CLOSED.

    Raises:
        TypeError: For unknown types (no str() fallback)
        ValueError: For nan/inf floats
    """
    if obj is None:
        return None
    if isinstance(obj, bool):  # Must be before int
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
    # FAIL-CLOSED: No str() fallback
    raise TypeError(f"Cannot serialize {type(obj).__name__} to JSON")
```

---

## 4. ErrorDTO

**Purpose**: Structured error for API boundary.

```python
@dataclass
class ErrorDTO(BaseDTO):
    # Required (stable contract)
    type: str           # Error class name
    code: str           # Stable error code
    message: str        # Human-readable
    retryable: bool     # Whether retry may succeed

    # Optional (stable keys per code)
    hint: str | None = None
    context: dict[str, Any] | None = None

    # Debug-only (NOT stable)
    cause: dict[str, Any] | None = None
```

### Example

```json
{
    "type": "NotFoundError",
    "code": "NOT_FOUND",
    "message": "Calculation 'si-scff' not found",
    "retryable": false,
    "hint": "Did you mean 'si-scf'?",
    "context": {
        "selector": "si-scff",
        "resource_type": "calculation",
        "suggestions": ["si-scf"]
    },
    "cause": {
        "origin": "kernel",
        "class": "CalculationNotFoundError",
        "trace_id": "tr-20260123-001"
    }
}
```

---

## 5. MetaDTO

**Purpose**: Common metadata for entities.

```python
@dataclass
class MetaDTO:
    slug: str | None = None          # Human-readable identifier
    name: str | None = None          # Display name
    description: str | None = None
    tags: list[str] | None = None
    created_at: str | None = None    # ISO datetime
    updated_at: str | None = None    # ISO datetime
```

---

## 6. CalculationDTO

**Purpose**: Calculation entity for API consumers.

```python
@dataclass
class CalculationDTO(BaseDTO):
    # Identity (required)
    calc_id: str              # ULID
    engine: str               # Engine family (qe, vasp, etc.)
    status: str               # pending, running, completed, failed

    # Metadata (optional)
    meta: MetaDTO | None = None

    # References (optional)
    structure_id: str | None = None    # Structure ULID
    step_ids: list[str] | None = None  # Step ULIDs

    # Summary (optional)
    step_count: int | None = None
    completed_step_count: int | None = None
```

**NOTE**: No `params` field. Use `svc.calculation.get_effective_params()` for merged parameters.

### Example

```json
{
    "calc_id": "01HX7YPVK8DQNZPMJ4GHAB1234",
    "engine": "qe",
    "status": "completed",
    "meta": {
        "slug": "si-scf",
        "name": "Silicon SCF",
        "description": "SCF calculation for bulk silicon",
        "tags": ["silicon", "scf"],
        "created_at": "2026-01-20T10:30:00Z",
        "updated_at": "2026-01-21T14:15:00Z"
    },
    "structure_id": "01HX7YPVK8DQNZPMJ4GHAB5678",
    "step_ids": ["01HX7YPVK8DQNZPMJ4GHAB9012"],
    "step_count": 1,
    "completed_step_count": 1
}
```

---

## 7. StepDTO

**Purpose**: Calculation step entity.

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

    # Execution details (optional)
    started_at: str | None = None
    completed_at: str | None = None
    duration_seconds: float | None = None
    exit_code: int | None = None
    error_message: str | None = None
```

### Example

```json
{
    "step_id": "01HX7YPVK8DQNZPMJ4GHAB9012",
    "calc_id": "01HX7YPVK8DQNZPMJ4GHAB1234",
    "step_type": "qe_scf",
    "status": "completed",
    "meta": {
        "slug": "scf",
        "name": "SCF Step"
    },
    "started_at": "2026-01-21T14:00:00Z",
    "completed_at": "2026-01-21T14:05:30Z",
    "duration_seconds": 330.5,
    "exit_code": 0,
    "error_message": null
}
```

---

## 8. StructureDTO

**Purpose**: Atomic structure summary (no coordinate arrays).

```python
@dataclass
class StructureDTO(BaseDTO):
    # Identity (required)
    structure_id: str         # ULID
    formula: str              # Chemical formula
    num_atoms: int

    # Metadata (optional)
    meta: MetaDTO | None = None

    # Crystallographic summary (optional)
    space_group: str | None = None
    point_group: str | None = None
    cell_volume_ang3: float | None = None
    lattice_abc: list[float] | None = None     # [a, b, c] Angstrom
    lattice_angles: list[float] | None = None  # [alpha, beta, gamma] degrees
```

**NOTE**: No `positions` or `species` arrays. Use `svc.structure.get_atoms()` for full data.

### Example

```json
{
    "structure_id": "01HX7YPVK8DQNZPMJ4GHAB5678",
    "formula": "Si8",
    "num_atoms": 8,
    "meta": {
        "slug": "si-bulk",
        "name": "Silicon FCC",
        "description": "Conventional FCC silicon cell"
    },
    "space_group": "Fd-3m",
    "point_group": "m-3m",
    "cell_volume_ang3": 160.103,
    "lattice_abc": [5.43, 5.43, 5.43],
    "lattice_angles": [90.0, 90.0, 90.0]
}
```

---

## 9. RunResultDTO

**Purpose**: Execution run result.

```python
@dataclass
class RunResultDTO(BaseDTO):
    # Identity (required)
    run_id: str               # ULID (execution identity)
    calc_id: str              # Calculation ULID
    status: str               # submitted, running, completed, failed, cancelled

    # Steps executed
    step_ids: list[str]       # Step ULIDs that were run

    # Timing (optional)
    started_at: str | None = None
    completed_at: str | None = None
    duration_seconds: float | None = None

    # Result (optional)
    exit_code: int | None = None
    log_path: str | None = None

    # Error (optional, if failed)
    error: ErrorDTO | None = None
```

**NOTE**: Uses `run_id` (not `job_id`) for consistent ULID naming.

### Example (success)

```json
{
    "run_id": "01HX7YPVK8DQNZPMJ4GHABCDEF",
    "calc_id": "01HX7YPVK8DQNZPMJ4GHAB1234",
    "status": "completed",
    "step_ids": ["01HX7YPVK8DQNZPMJ4GHAB9012"],
    "started_at": "2026-01-21T14:00:00Z",
    "completed_at": "2026-01-21T14:05:30Z",
    "duration_seconds": 330.0,
    "exit_code": 0,
    "log_path": ".qmatsuite/logs/01HX.../run.log",
    "error": null
}
```

### Example (failure)

```json
{
    "run_id": "01HX7YPVK8DQNZPMJ4GHABCDEF",
    "calc_id": "01HX7YPVK8DQNZPMJ4GHAB1234",
    "status": "failed",
    "step_ids": ["01HX7YPVK8DQNZPMJ4GHAB9012"],
    "started_at": "2026-01-21T14:00:00Z",
    "completed_at": "2026-01-21T14:01:05Z",
    "duration_seconds": 65.0,
    "exit_code": 1,
    "log_path": ".qmatsuite/logs/01HX.../run.log",
    "error": {
        "type": "EngineError",
        "code": "ENGINE_EXEC_FAILED",
        "message": "QE pw.x failed: convergence not achieved",
        "retryable": true,
        "context": {
            "engine": "qe",
            "exit_code": 1
        }
    }
}
```

---

## 10. AnalysisRefDTO

**Purpose**: Reference to large analysis data (NOT embedded).

```python
@dataclass
class AnalysisRefDTO(BaseDTO):
    # Identity
    calc_id: str              # ULID
    step_id: str              # ULID
    property_name: str        # "band_structure", "dos", "trajectory"

    # Artifact reference
    artifact_path: str        # Relative path to file
    artifact_format: str      # "hdf5", "npz", "json"
    artifact_sha256: str      # Content hash
    artifact_size_bytes: int

    # Summary (always present, small scalars only)
    summary: dict[str, Any]

    # Preview (optional, small subset for quick viz)
    preview: dict[str, Any] | None = None
```

### Example (band structure)

```json
{
    "calc_id": "01HX7YPVK8DQNZPMJ4GHAB1234",
    "step_id": "01HX7YPVK8DQNZPMJ4GHAB9012",
    "property_name": "band_structure",
    "artifact_path": ".qmatsuite/artifacts/01HX.../bands.hdf5",
    "artifact_format": "hdf5",
    "artifact_sha256": "a1b2c3d4...",
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
        "kpoint_indices": [0, 37, 75, 149]
    }
}
```

**Loading full data** (Jupyter-only):
```python
ref = svc.analysis.get_property_ref("si-bands", "bands", "band_structure")
full_data = svc.analysis.load_artifact(ref)
# Returns: {"kpoints": np.array(...), "eigenvalues": np.array(...)}
```

---

## 11. AnalysisSummaryDTO

**Purpose**: Quick analysis overview (no large data).

```python
@dataclass
class AnalysisSummaryDTO(BaseDTO):
    # Identity
    calc_id: str              # ULID
    step_id: str              # ULID

    # Status
    converged: bool | None = None

    # Key results (scalars only)
    total_energy_ev: float | None = None
    fermi_energy_ev: float | None = None
    band_gap_ev: float | None = None
    band_gap_type: str | None = None  # "direct", "indirect", "metal"
    total_magnetization: float | None = None

    # Available for detailed fetch
    available_properties: list[str] | None = None
```

### Example

```json
{
    "calc_id": "01HX7YPVK8DQNZPMJ4GHAB1234",
    "step_id": "01HX7YPVK8DQNZPMJ4GHAB9012",
    "converged": true,
    "total_energy_ev": -310.456789,
    "fermi_energy_ev": 6.234,
    "band_gap_ev": 0.52,
    "band_gap_type": "indirect",
    "total_magnetization": null,
    "available_properties": ["band_structure", "dos", "charge_density"]
}
```

---

## 12. DTO Mapping Implementation

All mapping MUST be centralized in `_mapping/dto_mapping.py`:

```python
# quantumvitas/api/_mapping/dto_mapping.py

def calculation_to_dto(calc: "Calculation") -> CalculationDTO:
    """Map kernel Calculation to DTO. SINGLE SOURCE OF TRUTH."""
    return CalculationDTO(
        calc_id=calc.ulid,  # Use ULID
        engine=calc.engine_family,
        status=_derive_status(calc),
        meta=MetaDTO(
            slug=calc.slug,
            name=calc.name,
            description=calc.description,
            tags=list(calc.tags) if calc.tags else None,
            created_at=_fmt_dt(calc.created_at),
            updated_at=_fmt_dt(calc.updated_at),
        ),
        structure_id=calc.structure_ulid,
        step_ids=[s.ulid for s in calc.steps],
        step_count=len(calc.steps),
        completed_step_count=sum(1 for s in calc.steps if s.completed),
    )
```

**FORBIDDEN**: Inline mapping in API methods.

---

## Changelog

| Version | Date | Changes |
|---------|------|---------|
| 1.0 | 2026-01-22 | Initial schema |
| 2.0 | 2026-01-23 | ULID identity, fail-closed JSON, reference pattern, run_id naming, removed params from CalculationDTO |
