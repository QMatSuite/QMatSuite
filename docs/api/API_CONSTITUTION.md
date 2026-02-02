# QMatSuite API Constitution

**Status**: AUTHORITATIVE LAW
**Version**: 2.0
**Date**: 2026-02-02

---

## 1. Purpose & Governing Idea

### 1.1 Single Governing Principle

**The API MUST be a THIN layer.**

Everything else follows from this: no coarse taxonomies that justify re-export sprawl, no hidden complexity, no shortcuts. Every public entrypoint is individually justified or it does not exist.

### 1.2 Scope

This constitution governs:

| Layer | Packages |
|-------|----------|
| **API** | `quantumvitas.api.*` |
| **Daemon** | `quantumvitas.daemon.*` |
| **CLI** | `quantumvitas.cli.*` |
| **GUI** | `gui/src/**` (TypeScript) |

Everything else (`quantumvitas.core.*`, `quantumvitas.io.*`, `quantumvitas.analysis.*`, `quantumvitas.calculation.*`, `quantumvitas.drivers.*`, `quantumvitas.presets.*`, `quantumvitas.workflow.*`, `quantumvitas.execution.*`, `quantumvitas.project.*`, `quantumvitas.history.*`, `quantumvitas.engine.*`) is **core/runtime**—the internal implementation below the API.

### 1.3 Normative Language

- **MUST / SHALL**: Absolute requirement. Violations are gate failures.
- **MUST NOT / SHALL NOT**: Absolute prohibition. Violations are gate failures.
- **SHOULD**: Strong recommendation. Deviations require documented justification.
- **MAY**: Optional.

---

## 2. Hard Laws

### Law H1: 3-Layer Model (Import Boundary)

Runtime backend code belongs to exactly one of:

1. **Frontends**: daemon, CLI (and later GUI/Jupyter/agent adapters)
2. **API facade**: `quantumvitas.api` (capabilities + DTOs + errors + utils)
3. **Core/runtime**: everything else below API

**Import rule:**

```
ALLOWED for daemon/CLI:
  from quantumvitas.api import ...
  from quantumvitas.api.utils import ...
  from quantumvitas.api.errors import ...

FORBIDDEN for daemon/CLI:
  from quantumvitas.core import ...
  from quantumvitas.io import ...
  from quantumvitas.analysis import ...
  from quantumvitas.calculation import ...
  from quantumvitas.drivers import ...
  from quantumvitas.presets import ...
  from quantumvitas.workflow import ...
  from quantumvitas.execution import ...
  from quantumvitas.project import ...
  from quantumvitas.history import ...
  from quantumvitas.engine import ...
```

**Rationale**: The API layer is the ONLY stable contract. Direct core/runtime imports create coupling that prevents internal refactoring.

**Gate**: `tests/gates/test_import_layering.py`

---

### Law H2: Utils Policy (Case-by-Case, Default Disallow)

**Principle**: Core/runtime functions are NOT automatically "reasonable to reexport."

**Default**: NO reexports in utils.

**Exception**: A utils function MAY be a transparent pass-through proxy to some core function ONLY if:
1. It is truly needed as a helper at the frontend boundary
2. It cannot reasonably live as a QVService capability method
3. It has a docstring justification explaining WHY it must exist
4. It is individually audited and allowlisted

**Utils is for helpers that users do not call directly.** It exists only because daemon/CLI sometimes need tiny helper utilities that they cannot import from core.

#### H2.1 Allowed Utils Categories

| Category | Definition | Example |
|----------|------------|---------|
| **UTILS_PURE** | No core/runtime imports; stdlib-only pure helper | (rare—most should be in stdlib) |
| **UTILS_PROXY_REEXPORT** | Transparent 1:1 proxy with docstring justification | `is_ulid_like`, `validate_ulid` |

#### H2.2 Forbidden in Utils

| Pattern | Violation Type | Remedy |
|---------|---------------|--------|
| Domain reexports (analysis, presets, drivers, etc.) | DOMAIN_REEXPORT | Move to QVService method |
| Service delegation (calls `get_service()`) | SERVICE_DELEGATION | Call service method directly |
| Multi-step orchestration logic | ORCHESTRATION | Service method or internal |
| Class reexports (exposing internal types) | CLASS_EXPORT | Return dicts/DTOs instead |
| Online search functions | DOMAIN_CAPABILITY | `QVService.OnlineSearch.*` |

#### H2.3 Docstring Justification Requirement

Every utils proxy MUST include a docstring explaining:
1. What core function it proxies
2. Why it cannot be a service method
3. What frontend use case requires it

```python
def is_ulid_like(s: str) -> bool:
    """
    Check if string looks like a ULID.

    JUSTIFICATION: Pure validation helper needed by daemon for request
    parsing before service instantiation. Cannot be service method because
    it's called before project context is available.

    PROXIES: quantumvitas.core.resolution._is_ulid_like
    """
    from quantumvitas.core.resolution import _is_ulid_like
    return _is_ulid_like(s)
```

**Gate**: `tests/gates/test_utils_docstring_justification.py`

---

### Law H3: Online Search is Domain Capability

**Online search/fetch/score/cache behavior is a CAPABILITY, not a utility.**

All online structure search functions MUST be exposed as QVService methods, NOT as utils reexports.

| Forbidden in utils | Required location |
|-------------------|-------------------|
| `search_online_structures` | `QVService.OnlineSearch.search()` |
| `fetch_structure_from_optimade` | `QVService.OnlineSearch.fetch()` |
| `score_candidate` | Internal to search capability |
| `extract_provenance` | Internal to search capability |
| `reduce_formula` | Internal or pure helper |
| `OnlineStructureCache` class | Factory method in QVService |

---

### Law H4: No Conversion Above Kernel

**Upper layers (daemon/CLI/GUI) MUST NOT convert, normalize, or derive.**

They pass through values unchanged. Specifically:

- **No step type conversion**: Daemon/CLI read `step_type_gen` and `step_type_spec` directly from DTOs
- **No selector resolution**: Resolution happens inside QVService, not in daemon/CLI
- **No path canonicalization**: Paths come from DTOs or are passed through

**API MUST NOT surface conversion utilities:**
- No `gen_from()`, `spec_from()`, `prefix_from()` in public API
- No `is_step_type_spec()` style predicates in public API

**Gate**: `tests/gates/test_no_conversion_above.py`

---

### Law H5: DTO Boundary

**All data crossing the API boundary MUST be DTOs or primitive types.**

- DTOs MUST inherit from `BaseDTO`
- DTOs MUST implement `to_json() -> dict` that is JSON-serializable
- DTOs MUST NOT contain core/runtime objects as fields
- Fail-closed: Unknown types raise, not silently stringify

---

### Law H6: Error Taxonomy

All API errors MUST inherit from `APIError`:

```
APIError (base)
├── NotFoundError      # Resource not found
├── AmbiguousError     # Multiple matches
├── ValidationError    # Invalid input
├── ConflictError      # State conflict
├── EngineError        # Execution failure
├── ConfigError        # Configuration error
├── FilesystemError    # File I/O error
└── InternalError      # Unexpected error
```

Daemon/CLI MUST NOT catch or handle core/runtime exceptions directly.

---

### Law H7: Identity Fields (ULID-Only)

- Entity's own identity: `ulid`
- References to other entities: `{kind}_ulid` (e.g., `calc_ulid`, `step_ulid`)
- Banned: bare `id`, `calc_id`, `step_id`, `run_id`, `structure_id`
- Exception: RPC correlation IDs may use `id` (not resource identifiers)

---

### Law H8: Step Type Fields

- Use `step_type_gen` for engine-agnostic (workflow/UI layer)
- Use `step_type_spec` for engine-specific (execution/persistence)
- Banned: bare `step_type`
- DTOs MUST carry BOTH fields to avoid conversion above kernel

---

## 3. Surface Governance Laws

### Law G1: Surface Accounting (Flattening Law)

**Track and govern ALL public entrypoints across the entire `quantumvitas.api` tree:**

- Top-level functions in `api/__init__.py`
- QVService static methods
- QVService nested service methods
- All utils exports
- All DTO classes
- All error classes

**No hiding**: "Import one class but it has 100 methods" is NOT slimming. Surface accounting counts methods.

**Gate**: `tests/gates/test_api_surface_accounting.py`

---

### Law G2: Slimming KPI

**Only deletion or true merging reduces surface.**

| Action | Counts as slimming? |
|--------|-------------------|
| Delete unused function | YES |
| Merge 3 methods into 1 | YES |
| Move utils → service (same function) | NO (structure only) |
| Rename function | NO |
| Add deprecation decorator | NO |

---

### Law G3: Static QVService Methods

**Goal: near-zero static methods.**

Static methods are allowed ONLY for:
1. **Bootstrap/factory**: Operations that create or locate projects (e.g., `init_project`)
2. **Global state with no project context**: E.g., pseudo library management, settings

**Anything with project/calc/step context MUST be a nested capability method.**

Do NOT maintain a detailed allowlist—too easy to loophole. Justify each static method individually.

---

### Law G4: New Entrypoint Gate

**New API entrypoints require explicit justification.**

Adding any of the following triggers gate review:
- New public function in `api/__init__.py`
- New static method on `QVService`
- New export in `api/utils.py`
- New nested service class

---

## 4. Gates Summary

| Gate ID | Name | Checks |
|---------|------|--------|
| G-IMPORT | Import Layering | daemon/CLI import only from quantumvitas.api |
| G-UTILS | Utils Allowlist | Every utils export has docstring justification |
| G-CONVERT | No Conversion Above | No step type / selector conversion in daemon/CLI |
| G-SURFACE | Surface Accounting | Total entrypoints within approved bounds |
| G-STATIC | Static Justification | Static methods have documented justification |
| G-IDENTITY | Identity Fields | No legacy id/calc_id/step_id/step_type |

---

## 5. Baseline (2026-02-02)

### 5.1 Current Surface (Before Slimming)

| Category | Count |
|----------|-------|
| `api/__init__.py` exports | 24 |
| QVService static methods | 38 |
| QVService nested service methods | ~100 |
| Utils exports | 88 |
| DTOs | 13 |
| Errors | 9 |
| **Estimated Total Entrypoints** | **~270** |

### 5.2 Utils Violations (Current State)

| Category | Count | Status |
|----------|-------|--------|
| Functions lacking docstring justification | ~85 | VIOLATION |
| Domain reexports | ~40 | VIOLATION |
| Service delegation | 2 | VIOLATION |
| Online search (should be capability) | 5 | VIOLATION |
| Class reexports | 3 | VIOLATION |

---

## 6. Target State

| Metric | Current | Target |
|--------|---------|--------|
| Utils exports | 88 | <20 |
| Utils violations | ~85 | 0 |
| Static methods | 38 | <15 |
| Total API surface | ~270 | <180 |

---

## 7. Migration Path

1. **Phase 1**: Add docstring justifications to legitimate utils proxies
2. **Phase 2**: Delete unused utils (0 daemon + 0 CLI usage)
3. **Phase 3**: Move online search to QVService capability
4. **Phase 4**: Move domain reexports to service methods
5. **Phase 5**: Deprecate duplicate static methods

---

## Appendix A: Step Type Quick Reference

### A.1 Namespaces

| Namespace | Layer | Format | Examples |
|-----------|-------|--------|----------|
| `step_type_gen` | Workflow/UI | lowercase, no underscores | `scf`, `relax`, `bands` |
| `step_type_spec` | Execution | `{prefix}_{gen}` | `qe_scf`, `vasp_relax` |

### A.2 Derivation

```
step_type_spec = f"{engine_prefix}_{step_type_gen}"
```

No exceptions. No conversion utilities in public API.

---

## Appendix B: Utils Allowlist Template

When auditing utils, each function must fit one of:

```
ALLOWED:
  - UTILS_PURE: No runtime imports, stdlib-only
  - UTILS_PROXY_REEXPORT: Has docstring justification

VIOLATION (requires remediation):
  - DOMAIN_REEXPORT: Move to service method
  - SERVICE_DELEGATION: Remove, use service directly
  - CLASS_EXPORT: Return dict/DTO instead
  - ONLINE_SEARCH: Move to OnlineSearch capability
  - ORCHESTRATION: Move to service method
  - NO_JUSTIFICATION: Add docstring or delete
```

---

**End of API Constitution v2.0**
