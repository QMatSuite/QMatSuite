# API Façade Contract

**Version**: 2.0
**Date**: 2026-01-23
**Status**: CONSTITUTION (binding)
**Audience**: Auto agent, human reviewers

---

## 1. Purpose

This document defines the binding rules for the `quantumvitas.api` module. It serves as the constitution that all implementation work MUST follow.

---

## 2. Goals

| Goal | Description |
|------|-------------|
| G1 | **Single stable surface**: All frontends access QuantumVITAS through `quantumvitas.api` only |
| G2 | **DTO-only returns**: API methods return JSON-friendly DTOs, not kernel objects |
| G3 | **Error contract**: API exposes only API-owned error types with stable codes |
| G4 | **Kernel isolation**: Frontends NEVER import from kernel modules |
| G5 | **Minimal exports**: Top-level `quantumvitas.api` exports ≤30 symbols |
| G6 | **Large data by reference**: No huge arrays embedded in DTOs |

---

## 3. Non-Goals

| Non-Goal | Rationale |
|----------|-----------|
| NG1 | Duplicating full kernel object graph as DTOs |
| NG2 | Breaking kernel internals (kernel continues using its own types) |
| NG3 | Exposing raw kernel objects as default (expert-only, Jupyter-only) |

---

## 4. Hard Decisions (LAW)

### D1: Return Types
API public return types are JSON-friendly DTOs. Default APIs MUST NOT return kernel objects.

### D2: Frontend Isolation
Frontends MUST NEVER instantiate kernel models. They only call capabilities and use DTOs.

### D3: Error Contract
API boundary exposes API-owned errors only. Kernel exceptions must be mapped to structured API errors with stable `code`/`type`/`context`/`retryable`.

---

## 5. Core Principles

### 5.1 Capability→DTO Minimalism

DTOs are defined ONLY for capability inputs/outputs (~20-40 endpoints total).

**Rules**:
- DTOs are "ABI structs" for stable external contract
- CLI + daemon + Jupyter share the SAME DTO shapes
- DTOs MUST NOT contain kernel dataclasses as fields
- DTOs MUST NOT expose kernel internals
- DTO design is additive-only

### 5.2 ULID vs Slug

| Field | Purpose | Example |
|-------|---------|---------|
| `calc_id` | ULID identity | `01HX7YPVK8DQNZPMJ4GHAB1234` |
| `meta.slug` | Human-readable name | `si-scf` |

**Rules**:
- All DTO identity fields MUST be ULIDs
- Slug is separate metadata in `meta.slug`
- APIs accept selectors (slug/ULID/patterns), return ULIDs

### 5.3 Fail-Closed JSON Conversion

**Rules**:
- DTO serialization MUST be fail-closed
- Unknown object types MUST raise `TypeError`
- Only convert strict whitelist: primitives, list, dict, datetime→ISO, Path→str, Enum→str, UUID→str
- NO fallback `str(obj)`
- NaN/Inf MUST raise `ValueError`

### 5.4 Large Data by Reference

**Rules**:
- Analysis/bands/DOS/trajectories MUST NOT be embedded in DTOs
- Use `AnalysisRefDTO` with: artifact_path, format, sha256, size, summary, preview
- Full data loaded via `svc.analysis.load_artifact()` (Jupyter-only)
- Daemon provides artifact download endpoint

### 5.5 Structured Errors

**Required fields**:
| Field | Required | Stable |
|-------|----------|--------|
| `type` | YES | YES |
| `code` | YES | YES |
| `message` | YES | NO |
| `context` | NO | YES (keys per code) |
| `retryable` | YES | YES |
| `hint` | NO | NO |
| `cause` | NO | NO (debug-only) |

---

## 6. Public Surface Organization

### 6.1 Final Export List (≤30)

```python
# quantumvitas.api.__all__
__all__ = [
    # Service
    "QVService",
    # Errors (9)
    "APIError", "NotFoundError", "AmbiguousError", "ValidationError",
    "ConflictError", "EngineError", "ConfigError", "FilesystemError", "InternalError",
    # DTOs (8)
    "ErrorDTO", "MetaDTO", "CalculationDTO", "StepDTO",
    "StructureDTO", "RunResultDTO", "AnalysisRefDTO", "AnalysisSummaryDTO",
    # Error codes (13)
    "NOT_FOUND", "AMBIGUOUS_SELECTOR", "INVALID_SELECTOR", "VALIDATION_FAILED",
    "EDIT_LOCK_HELD", "RUN_LOCK_HELD", "ENGINE_EXEC_FAILED",
    "ENGINE_OUTPUT_PARSE_FAILED", "ENGINE_NOT_AVAILABLE",
    "PROJECT_SSOT_MISSING", "MODE_MISMATCH", "FILESYSTEM_ERROR", "INTERNAL_ERROR",
]
```

### 6.2 QVService Domains

| Domain | Capabilities |
|--------|--------------|
| `svc.calculation` | get, list, create, update_meta, update_step_params, duplicate, delete, add_step, remove_step, get_step, list_steps, get_effective_params |
| `svc.structure` | get, list, get_atoms, visualize |
| `svc.run` | run_calculation, run_step, get_status, cancel, list_runs |
| `svc.analysis` | get_summary, list_properties, get_property_ref, load_artifact |
| `svc.project` | get_config, update_config, get_species_map, get_potential_map, list_calculations |
| `svc.engine` | list, get_info, list_step_types, validate_installation |

---

## 7. Absolute Prohibitions

| Prohibition | Detection |
|-------------|-----------|
| Embedding huge arrays in DTO | Artifact size check |
| Fallback `str(obj)` serialization | Grep; fail-closed test |
| Kernel dataclasses crossing API | Type hints; gate tests |
| Endpoint hand-serialization | Grep `json.dumps` in daemon |
| Frontends constructing kernel models | Gate test |
| Using slug as id | DTO field audit |
| API re-exporting kernel symbols | Gate test |

---

## 8. Testing Requirements

**Command**:
```bash
source .venv/bin/activate
python -m pytest tests/ -v --tb=short -n auto --dist=loadfile
```

**Required tests per DTO**:
1. Schema test (required fields present)
2. JSON-friendly test (`json.dumps(dto.to_dict())`)
3. Fail-closed test (unknown types raise TypeError)

**Required tests per capability**:
1. Round-trip consistency
2. Error mapping to correct code

---

## 9. Success Metrics (KPIs)

| KPI | Target |
|-----|--------|
| K1 | 0 kernel types in API returns |
| K2 | 0 kernel model instantiation in frontends |
| K3 | 0 kernel imports in frontends |
| K4 | ≤30 top-level api exports |
| K5 | 100% daemon endpoints use DTO |
| K6 | 0 embedded arrays in DTO |

---

## 10. Document References

| Document | Purpose |
|----------|---------|
| `API_FACADE_IMPLEMENTATION_PLAN.md` | PR-by-PR execution plan |
| `API_DTO_SCHEMA.md` | DTO field definitions |
| `API_ERROR_TAXONOMY.md` | Error code registry |

---

## Changelog

| Version | Date | Changes |
|---------|------|---------|
| 1.0 | 2026-01-22 | Initial constitution |
| 2.0 | 2026-01-23 | Added ULID, fail-closed, reference pattern, fixed prohibitions |
