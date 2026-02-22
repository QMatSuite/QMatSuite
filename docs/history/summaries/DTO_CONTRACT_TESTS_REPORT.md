# DTO Contract Tests Report

## Summary

This report documents the contract tests added to prevent silent breakage of frontend (CLI/daemon) payload shapes during DTO/API refactors. These tests lock the external contracts that frontends depend on, ensuring that future refactors cannot silently break e2e workflows.

## Background

After introducing DTOs and API slimming (post-0873ebf), frontends (CLI + daemon) historically relied on certain output shapes and status strings. A compatibility patch was added, but we needed explicit contract tests to prevent future regressions.

## Contracts Locked

### 1. DTO Serialization Contracts

**Location**: `tests/api/test_dto_frontend_contracts.py`

#### StructureDTO Contract
- **Compatibility Properties**: `id`, `name`, `slug`, `path`, `n_atoms`
- **Behavior**:
  - When `meta` exists: All compatibility properties are included in `to_dict()`
  - When `meta` is None: `id` falls back to `structure_id`, `n_atoms` is always present
  - `name`, `slug`, `path` are only included if not None (frontends should handle missing keys)
- **Canonical Fields**: `structure_id`, `num_atoms` are always present alongside compatibility properties

#### CalculationDTO Contract
- **Compatibility Properties**: `id`, `name`, `slug`, `path`, `n_steps`
- **Behavior**:
  - When `meta` exists: All compatibility properties are included in `to_dict()`
  - When `meta` is None: `id` falls back to `calc_id`, `n_steps` is always present if `step_count` is set
  - `name`, `slug`, `path` are only included if not None (frontends should handle missing keys)
- **Canonical Fields**: `calc_id`, `step_count` are always present alongside compatibility properties

#### RunResultDTO Contract
- **Compatibility Properties**: `steps` (list of dicts), `io_dir`, `input_file`, `output_file`, legacy status mapping
- **Behavior**:
  - `steps` is always included in `to_dict()` (even if empty list)
  - Each step dict contains: `step_id`, `step_type`, `status`, `message`, `metrics`
  - `io_dir`, `input_file`, `output_file` are included for CLI compatibility
  - **Legacy Status Mapping**: Canonical status is mapped to legacy format:
    - `completed` → `SUCCESS`
    - `failed` → `FAILED`
    - `running` → `RUNNING`
    - `submitted`/`pending` → `PENDING`
    - `cancelled` → `CANCELLED`

### 2. Daemon Handler Payload Contracts

**Location**: `tests/daemon/test_daemon_payload_contracts.py`

#### list_structures Handler Contract
- Returns `{"structures": [...], "count": N}`
- Each structure dict includes compatibility keys: `id`, `slug` (if not None), `path` (if not None), `n_atoms`
- Canonical keys also present: `structure_id`, `num_atoms`

#### list_calculations Handler Contract
- Returns `{"calculations": [...], "count": N}`
- Each calculation dict includes compatibility keys: `id`, `slug` (if not None), `path` (if not None), `n_steps`
- Canonical keys also present: `calc_id`, `step_count`

#### run_calculation / run_step Handler Contract
- Returns dict with legacy-mapped `status` field (e.g., "SUCCESS" not "COMPLETED")
- Returns `steps` as list of dicts with required keys: `step_id`, `step_type`, `status`, `message`, `metrics`

**Note**: Daemon handlers use `dto.to_dict()` for serialization, so they automatically inherit all DTO contracts.

### 3. CLI Output Contracts

**Location**: `tests/cli/test_cli_output_contracts.py`

#### run calculation Output Contract
- Outputs status as "SUCCESS" (not "COMPLETED") when calculation completes
- This contract is enforced by the legacy status mapping in `RunResultDTO.to_dict()`

## Implementation Details

### Status Mapping Implementation

The legacy status mapping is implemented in `RunResultDTO.to_dict()`:

```python
legacy_status_map = {
    "completed": "SUCCESS",
    "failed": "FAILED",
    "running": "RUNNING",
    "submitted": "PENDING",
    "pending": "PENDING",
    "cancelled": "CANCELLED",
}
canonical_status = result.get("status", "").lower()
result["status"] = legacy_status_map.get(canonical_status, result.get("status", "").upper())
```

This ensures that:
1. Internal canonical status remains unchanged (execution engine semantics preserved)
2. Frontend payloads always use legacy status strings
3. CLI/daemon output matches historical expectations

### CLI Integration

The CLI `run_calculation_command` uses `result_dto.to_dict()` to get the legacy-mapped status:

```python
result_dto = svc.run.run_calculation(...)
result_dict = result_dto.to_dict()  # Includes legacy status mapping
status_str = result_dict.get("status", "SUCCESS")  # Already mapped to "SUCCESS"
typer.echo(f"Calculation {calc_selector} status: {status_str.upper()}")
```

### Daemon Integration

Daemon handlers use `dto.to_dict()` for all DTO serialization:

```python
structure_dtos = svc.structure.list()
structures = [dto.to_dict() for dto in structure_dtos]  # Includes all compatibility properties
```

## Test Coverage

### DTO Serialization Tests
- ✅ StructureDTO with meta
- ✅ StructureDTO without meta
- ✅ CalculationDTO with meta
- ✅ CalculationDTO without meta
- ✅ RunResultDTO steps list
- ✅ RunResultDTO io fields
- ✅ RunResultDTO legacy status mapping (all status values)
- ✅ RunResultDTO empty steps handling

### Daemon Handler Tests
- ✅ list_structures payload structure
- ✅ list_calculations payload structure
- ⏸️ run_calculation / run_step (placeholder - requires execution or mocking)

### CLI Output Tests
- ✅ run calculation outputs "SUCCESS" status

## Why These Contracts Matter

1. **Prevents Silent Breakage**: Contract tests fail immediately if DTO refactors break frontend expectations
2. **Documents External API**: Tests serve as living documentation of what frontends depend on
3. **Enables Safe Refactoring**: Developers can refactor DTOs knowing that contract tests will catch breaking changes
4. **Maintains Backward Compatibility**: Ensures that historical CLI/daemon output formats are preserved

## Future Considerations

1. **Expand Daemon Contract Tests**: Add actual execution tests for `run_calculation` and `run_step` handlers (currently placeholders)
2. **Add More CLI Contracts**: Consider adding contracts for other CLI commands that output structured data
3. **Versioning Strategy**: If breaking changes are needed in the future, consider versioning the contracts

## Related Files

- `src/qmatsuite/api/types/structure.py` - StructureDTO implementation
- `src/qmatsuite/api/types/calculation.py` - CalculationDTO implementation
- `src/qmatsuite/api/types/run.py` - RunResultDTO implementation with legacy status mapping
- `src/qmatsuite/cli/main.py` - CLI integration using `to_dict()`
- `src/qmatsuite/daemon/server.py` - Daemon handlers using `to_dict()`
- `tests/api/test_dto_frontend_contracts.py` - DTO contract tests
- `tests/daemon/test_daemon_payload_contracts.py` - Daemon handler contract tests
- `tests/cli/test_cli_output_contracts.py` - CLI output contract tests

