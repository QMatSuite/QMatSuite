# API Error Taxonomy

**Version**: 2.0
**Date**: 2026-01-23
**Status**: SPECIFICATION (binding)
**Audience**: Auto agent, human reviewers

---

## 1. Overview

This document defines the stable error codes for `quantumvitas.api`. All API errors MUST use codes from this registry.

---

## 2. Error Code Registry

| Code | Type | Retryable | Category |
|------|------|-----------|----------|
| `NOT_FOUND` | NotFoundError | No | Resolution |
| `AMBIGUOUS_SELECTOR` | AmbiguousError | No | Resolution |
| `INVALID_SELECTOR` | ValidationError | No | Input |
| `VALIDATION_FAILED` | ValidationError | No | Input |
| `EDIT_LOCK_HELD` | ConflictError | Yes | Concurrency |
| `RUN_LOCK_HELD` | ConflictError | Yes | Concurrency |
| `ENGINE_EXEC_FAILED` | EngineError | Maybe | Execution |
| `ENGINE_OUTPUT_PARSE_FAILED` | EngineError | No | Execution |
| `ENGINE_NOT_AVAILABLE` | EngineError | Yes | Execution |
| `PROJECT_SSOT_MISSING` | ConfigError | No | Project |
| `MODE_MISMATCH` | ConfigError | No | Project |
| `FILESYSTEM_ERROR` | FilesystemError | Maybe | System |
| `INTERNAL_ERROR` | InternalError | No | System |

---

## 3. Error Class Hierarchy

```python
class APIError(Exception):
    """Base for all API errors."""
    code: str
    message: str
    retryable: bool
    hint: str | None
    context: dict | None
    cause: dict | None  # Debug-only

    def to_dto(self) -> ErrorDTO: ...

class NotFoundError(APIError):
    code = "NOT_FOUND"
    retryable = False

class AmbiguousError(APIError):
    code = "AMBIGUOUS_SELECTOR"
    retryable = False

class ValidationError(APIError):
    code = "VALIDATION_FAILED"  # or "INVALID_SELECTOR"
    retryable = False

class ConflictError(APIError):
    # code = "EDIT_LOCK_HELD" or "RUN_LOCK_HELD"
    retryable = True

class EngineError(APIError):
    # code = "ENGINE_EXEC_FAILED" etc.
    pass

class ConfigError(APIError):
    # code = "PROJECT_SSOT_MISSING" or "MODE_MISMATCH"
    retryable = False

class FilesystemError(APIError):
    code = "FILESYSTEM_ERROR"
    # retryable depends on cause

class InternalError(APIError):
    code = "INTERNAL_ERROR"
    retryable = False
```

---

## 4. Detailed Specifications

### 4.1 NOT_FOUND

**Type**: `NotFoundError`
**Retryable**: `false`

**Context keys** (stable):
| Key | Type | Required |
|-----|------|----------|
| `selector` | `str` | YES |
| `resource_type` | `str` | YES |
| `suggestions` | `list[str]` | NO |

**Kernel mapping**:
- `CalculationNotFoundError` → `resource_type="calculation"`
- `StepNotFoundError` → `resource_type="step"`
- `StructureNotFoundError` → `resource_type="structure"`
- `FileNotFoundError` (on YAML) → `resource_type="calculation"`

**Example**:
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
    }
}
```

---

### 4.2 AMBIGUOUS_SELECTOR

**Type**: `AmbiguousError`
**Retryable**: `false`

**Context keys**:
| Key | Type | Required |
|-----|------|----------|
| `selector` | `str` | YES |
| `matches` | `list[str]` | YES |
| `resource_type` | `str` | YES |

**Kernel mapping**:
- `AmbiguousSelectorError`
- `MultipleMatchesError`

**Example**:
```json
{
    "type": "AmbiguousError",
    "code": "AMBIGUOUS_SELECTOR",
    "message": "Selector 'si-' matches 3 calculations",
    "retryable": false,
    "hint": "Use a more specific selector",
    "context": {
        "selector": "si-",
        "matches": ["si-scf", "si-relax", "si-bands"],
        "resource_type": "calculation"
    }
}
```

---

### 4.3 INVALID_SELECTOR

**Type**: `ValidationError`
**Retryable**: `false`

**Context keys**:
| Key | Type | Required |
|-----|------|----------|
| `selector` | `str` | YES |
| `reason` | `str` | YES |
| `expected_format` | `str` | NO |

**Kernel mapping**:
- `InvalidSelectorError`
- `SelectorParseError`

**Example**:
```json
{
    "type": "ValidationError",
    "code": "INVALID_SELECTOR",
    "message": "Invalid selector: empty string",
    "retryable": false,
    "hint": "Use name or ULID",
    "context": {
        "selector": "",
        "reason": "empty string not allowed",
        "expected_format": "slug or ULID"
    }
}
```

---

### 4.4 VALIDATION_FAILED

**Type**: `ValidationError`
**Retryable**: `false`

**Context keys**:
| Key | Type | Required |
|-----|------|----------|
| `field` | `str` | YES |
| `value` | `any` | YES |
| `constraint` | `str` | YES |
| `allowed_values` | `list` | NO |
| `min_value` | `number` | NO |
| `max_value` | `number` | NO |

**Kernel mapping**:
- `ValidationError`
- `ValueError` (on params)
- `TypeError` (on params)
- `pydantic.ValidationError`

**Example**:
```json
{
    "type": "ValidationError",
    "code": "VALIDATION_FAILED",
    "message": "Invalid ecutwfc: must be positive",
    "retryable": false,
    "hint": "Provide positive float",
    "context": {
        "field": "ecutwfc",
        "value": -10,
        "constraint": "positive_number",
        "min_value": 0
    }
}
```

---

### 4.5 EDIT_LOCK_HELD

**Type**: `ConflictError`
**Retryable**: `true`

**Context keys**:
| Key | Type | Required |
|-----|------|----------|
| `calc_id` | `str` | YES |
| `holder` | `str` | NO |
| `since` | `str` | NO |
| `lock_file` | `str` | NO |

**NOTE**: `holder` and `since` are optional (may be unavailable).

**Kernel mapping**:
- `EditLockError`
- `ResourceLockError`

**Example**:
```json
{
    "type": "ConflictError",
    "code": "EDIT_LOCK_HELD",
    "message": "Calculation locked for editing",
    "retryable": true,
    "hint": "Wait or use --force",
    "context": {
        "calc_id": "01HX7YPVK8DQNZPMJ4GHAB1234",
        "holder": "daemon@pid:1234",
        "since": "2026-01-21T14:00:00Z"
    }
}
```

---

### 4.6 RUN_LOCK_HELD

**Type**: `ConflictError`
**Retryable**: `true`

**Context keys**:
| Key | Type | Required |
|-----|------|----------|
| `calc_id` | `str` | YES |
| `run_id` | `str` | YES |
| `started_at` | `str` | NO |
| `step_id` | `str` | NO |

**Kernel mapping**:
- `RunLockError`
- `JobInProgressError`

**Example**:
```json
{
    "type": "ConflictError",
    "code": "RUN_LOCK_HELD",
    "message": "Calculation is running",
    "retryable": true,
    "hint": "Wait or cancel job",
    "context": {
        "calc_id": "01HX7YPVK8DQNZPMJ4GHAB1234",
        "run_id": "01HX7YPVK8DQNZPMJ4GHABCDEF"
    }
}
```

---

### 4.7 ENGINE_EXEC_FAILED

**Type**: `EngineError`
**Retryable**: depends (convergence: maybe; segfault: no)

**Context keys**:
| Key | Type | Required |
|-----|------|----------|
| `engine` | `str` | YES |
| `calc_id` | `str` | YES |
| `step_id` | `str` | YES |
| `exit_code` | `int` | YES |
| `log_path` | `str` | NO |
| `error_pattern` | `str` | NO |

**Kernel mapping**:
- `EngineExecutionError`
- `SubprocessError`
- Engine-specific errors (QEExecutionError, etc.)

**Example**:
```json
{
    "type": "EngineError",
    "code": "ENGINE_EXEC_FAILED",
    "message": "QE pw.x failed (exit 1)",
    "retryable": true,
    "hint": "Check log for details",
    "context": {
        "engine": "qe",
        "calc_id": "01HX7YPVK8DQNZPMJ4GHAB1234",
        "step_id": "01HX7YPVK8DQNZPMJ4GHAB9012",
        "exit_code": 1,
        "error_pattern": "convergence NOT achieved"
    }
}
```

---

### 4.8 ENGINE_OUTPUT_PARSE_FAILED

**Type**: `EngineError`
**Retryable**: `false`

**Context keys**:
| Key | Type | Required |
|-----|------|----------|
| `engine` | `str` | YES |
| `calc_id` | `str` | YES |
| `step_id` | `str` | YES |
| `parser` | `str` | YES |
| `file_path` | `str` | NO |
| `parse_error` | `str` | NO |

**Kernel mapping**:
- `OutputParseError`
- `XMLParseError`
- `MalformedOutputError`

---

### 4.9 ENGINE_NOT_AVAILABLE

**Type**: `EngineError`
**Retryable**: `true`

**Context keys**:
| Key | Type | Required |
|-----|------|----------|
| `engine` | `str` | YES |
| `executable` | `str` | YES |
| `search_paths` | `list[str]` | NO |
| `install_hint` | `str` | NO |

**Kernel mapping**:
- `EngineNotFoundError`
- `ExecutableNotFoundError`

---

### 4.10 PROJECT_SSOT_MISSING

**Type**: `ConfigError`
**Retryable**: `false`

**Context keys**:
| Key | Type | Required |
|-----|------|----------|
| `missing_key` | `str` | YES |
| `expected_path` | `str` | YES |
| `required_by` | `str` | NO |

**Kernel mapping**:
- `ProjectConfigError`
- `MissingSpeciesMapError` → `missing_key="species_map"`
- `MissingPotentialMapError` → `missing_key="potential_map"`

---

### 4.11 MODE_MISMATCH

**Type**: `ConfigError`
**Retryable**: `false`

**Context keys**:
| Key | Type | Required |
|-----|------|----------|
| `expected_mode` | `str` | YES |
| `actual_mode` | `str` | YES |
| `calc_id` | `str` | YES |
| `operation` | `str` | NO |

**Kernel mapping**:
- `ModeMismatchError`
- `ProjectModeRequiredError`

---

### 4.12 FILESYSTEM_ERROR

**Type**: `FilesystemError`
**Retryable**: depends (permission: no; disk full: maybe)

**Context keys**:
| Key | Type | Required |
|-----|------|----------|
| `operation` | `str` | YES |
| `path` | `str` | YES |
| `reason` | `str` | YES |
| `errno` | `int` | NO |

**NOTE**: Uses `FilesystemError` (not `IOError`) to avoid Python builtin confusion.

**Kernel mapping**:
- `PermissionError`
- `OSError` (on file ops)
- `IOError`

---

### 4.13 INTERNAL_ERROR

**Type**: `InternalError`
**Retryable**: `false`

**Context keys**:
| Key | Type | Required |
|-----|------|----------|
| `trace_id` | `str` | YES |
| `component` | `str` | NO |

**Kernel mapping**:
- `Exception` (unhandled)
- `AssertionError`
- `RuntimeError` (unexpected)

**Example**:
```json
{
    "type": "InternalError",
    "code": "INTERNAL_ERROR",
    "message": "Unexpected error",
    "retryable": false,
    "hint": "Report with trace_id",
    "context": {
        "trace_id": "tr-20260123-143000-abc123"
    },
    "cause": {
        "origin": "kernel",
        "class": "KeyError",
        "message": "'unexpected_key'",
        "trace_id": "tr-20260123-143000-abc123"
    }
}
```

---

## 5. Exception Mapping

All mapping MUST be centralized in `_mapping/exc_mapping.py`:

```python
import uuid
from datetime import datetime

def map_kernel_exception(exc: Exception) -> APIError:
    """
    Map kernel exception to API error.
    SINGLE SOURCE OF TRUTH.
    """
    trace_id = _generate_trace_id()

    # Resolution errors
    if isinstance(exc, CalculationNotFoundError):
        return NotFoundError(
            message=str(exc),
            context={
                "selector": exc.selector,
                "resource_type": "calculation",
            },
            cause=_make_cause(exc, trace_id)
        )

    # ... more mappings ...

    # Fallback: internal error
    return InternalError(
        message="Unexpected error",
        context={"trace_id": trace_id},
        cause=_make_cause(exc, trace_id)
    )

def _generate_trace_id() -> str:
    ts = datetime.now().strftime("%Y%m%d-%H%M%S")
    return f"tr-{ts}-{uuid.uuid4().hex[:6]}"

def _make_cause(exc: Exception, trace_id: str) -> dict:
    return {
        "origin": "kernel",
        "class": type(exc).__name__,
        "message": str(exc),
        "trace_id": trace_id
    }
```

---

## 6. Frontend Contract

**Agents/Frontends MUST**:
- Use `code` for programmatic decisions
- Use `retryable` for retry logic
- Display `message` and `hint` to users
- Log `cause.trace_id` for debugging

**Agents/Frontends MUST NOT**:
- Parse `message` strings
- Catch kernel exception classes
- Depend on `cause` structure (debug-only)

---

## Changelog

| Version | Date | Changes |
|---------|------|---------|
| 1.0 | 2026-01-22 | Initial taxonomy |
| 2.0 | 2026-01-23 | FilesystemError naming, optional holder/since, run_id in RUN_LOCK_HELD |
